"""The race-time VDP1 work (src/vdp1x_core.c, built here for the PC) run over
lap logs, and the per-course texture choices it needs.

usage: vdp1x_eval.py data [RUN]   every textured course quad of RUN's lap logs
                                  (tools/vdp1_lap.py, build/vdp1cost/RUN_<course>,
                                  default final) costed as drawn, turned, and cut:
                                  build/vdp1x/quads.npz
       vdp1x_eval.py choose       the textures given strips in each course's
                                  free VDP1 VRAM, most frame time saved first:
                                  tools/vdp1x_choices.json

The turned costs measure drawing each quad turned whichever way is cheaper
(src/vdp1x_core.c's vx_turn, with copies of textures turned a quarter):
choose(kinds=('cut', 'turn')) weighs those copies too. The race doesn't
turn quads (src/vdp1x.c: the CPU time isn't worth it).

Costs are each command's alone, with the race's clip window and local
coordinates set (they match the in-list costs exactly), with the Tomb
Raider project's calibrated Mednafen VDP1 code (tools/vdp1lib.py). A
command's cost doesn't depend on its texels, so turned and cut ones draw
from anywhere. A log with over 1300 commands is a frame VDP1 didn't finish
running on into the next (tools/vdp1_lap.py) and is left out.
"""
import csv
import ctypes
import glob
import json
import os
import struct
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from vdp1lib import Vdp1        # noqa: E402
import turn_quads              # noqa: E402

OUT = os.path.join(ROOT, 'build', 'vdp1x')
COURSES = ('t7', 'dino', 'sea', 'np', 'desert')
SCREEN = (-176, -135, 175, 88)  # the race's clip window from its local origin (176, 135)
BAND = 32                       # rows a cut quad's band
F = 28636360 / 30
BUDGET = 0.927
CHOICES = os.path.join(ROOT, 'tools', 'vdp1x_choices.json')

# free VDP1 VRAM in races, by course (byte address, length): the zero tail of the player car's
# texture file (CARn.TEX loads after the course's textures), and on National Park a run after that
FREE = {0: [(0x577A0, 19288)], 1: [(0x5C760, 19288)], 2: [(0x5A320, 19288)],
        3: [(0x482C0, 19288), (0x589F8, 14592)], 4: [(0x63560, 19288)]}


class Piece(ctypes.Structure):
    _fields_ = [('c', ctypes.c_short * 8), ('strip', ctypes.c_ushort), ('row', ctypes.c_ushort),
                ('rows', ctypes.c_ushort), ('pad', ctypes.c_ushort)]


class Cutting(ctypes.Structure):
    _fields_ = [('nu', ctypes.c_short), ('nv', ctypes.c_short), ('band', ctypes.c_short), ('h', ctypes.c_short),
                ('u', ctypes.c_short * 17), ('v', ctypes.c_short * 17)]


def build_dll():
    os.makedirs(OUT, exist_ok=True)
    dll = os.path.join(OUT, 'vx.dll')
    src = os.path.join(ROOT, 'src', 'vdp1x_core.c')
    if os.path.exists(dll) and os.path.getmtime(dll) > os.path.getmtime(src):
        return dll
    vcvars = sorted(glob.glob(r'C:\Program Files\Microsoft Visual Studio\*\*\VC\Auxiliary\Build\vcvars64.bat'))[-1]
    bat = os.path.join(OUT, 'build_vx.bat')
    open(bat, 'w').write(f'@call "{vcvars}" >nul\r\n'
                         f'@cl /nologo /O2 /LD /DVX_API=__declspec(dllexport) "{src}" /Fevx.dll\r\n')
    subprocess.run(['cmd', '/c', bat], check=True, cwd=OUT)
    return dll


class Core:
    def __init__(self):
        self.lib = ctypes.CDLL(build_dll())
        self.screen = (ctypes.c_short * 4)(*SCREEN)
        self.out = (Piece * 256)()

    def turn(self, pts):
        return self.lib.vx_turn((ctypes.c_short * 8)(*[x for p in pts for x in p]))

    def estimate(self, pts):
        return self.lib.vx_estimate((ctypes.c_short * 8)(*[x for p in pts for x in p]))

    def grid(self, pts, w, h, flips, sw):
        """The pieces (corners, strip, first row, rows) with no threshold, or None."""
        t = Cutting()
        if not self.lib.vx_cutting_of(ctypes.byref(t), w, h, sw, BAND):
            return None
        n = self.lib.vx_grid((ctypes.c_short * 8)(*[x for p in pts for x in p]), ctypes.byref(t), flips,
                             self.screen, 0, self.out, 256)
        if n < 0:
            return None
        return [([(q.c[2 * i], q.c[2 * i + 1]) for i in range(4)], q.strip, q.row, q.rows)
                for q in self.out[:n]]


class Coster:
    LOCAL = [0x000A, 0, 0, 0, 0, 0, -SCREEN[0], -SCREEN[1], 0, 0, 0, 0, 0, 0, 0, 0]
    SYSCLIP = [0x0009, 0, 0, 0, 0, 0, 0, 0, 0, 0, 351, 223, 0, 0, 0, 0]
    USERCLIP = [0x0008, 0, 0, 0, 0, 0, 0, 0, 0, 0, 351, 223, 0, 0, 0, 0]
    AT = 0x1000

    def __init__(self):
        self.v = Vdp1(dll=os.path.join(ROOT, 'tools', 'mednafen', 'vdp1lib.dll'))
        self.v.vram[:] = 0x1111
        for i, x in enumerate((self.SYSCLIP, self.USERCLIP, self.LOCAL)):
            self.v.vram[self.AT + 16 * i:self.AT + 16 * i + 16] = x
        self.v.vram[self.AT + 64] = 0x8000

    def cost(self, ctrl, pmod, size, pts):
        c = [ctrl & 0x0FFF, 0, pmod, 0x0400, 0x2000, size] + [x & 0xFFFF for p in pts for x in p] + [0, 0]
        self.v.vram[self.AT + 48:self.AT + 64] = c
        self.v.reset()
        ret, addr = ctypes.c_int32(-1), self.AT
        for _ in range(3):
            addr = self.v.step(addr, ret)[0]
        return self.v.step(addr, ret)[1].cycles


def place(sizes, course):
    """Places in the course's free VRAM (bytes, 8-aligned) for copies of these sizes, largest first, after
    the 8 bytes of the sign; None when they don't fit."""
    regions = [[a + (8 if i == 0 else 0), a + n] for i, (a, n) in enumerate(FREE[course])]
    at = [None] * len(sizes)
    for i in sorted(range(len(sizes)), key=lambda i: -sizes[i]):
        n = (sizes[i] + 7) & ~7
        for r in regions:
            if r[1] - r[0] >= n:
                at[i], r[0] = r[0], r[0] + n
                break
        else:
            return None
    return at


def strip_width(w, h):
    """The width of a texture's strips: 16, or 8 for one 8 wide in 16s plus 8 (then its height even)."""
    if w % 16 == 0:
        return 16
    return 8 if h % 2 == 0 else 0


def data(run):
    core, coster = Core(), Coster()
    quads, frames = [], []
    for ci, course in enumerate(COURSES):
        rn = run if os.path.isdir(os.path.join(ROOT, 'build', 'vdp1cost', f'{run}_{course}')) else run + '2'
        for p in sorted(glob.glob(os.path.join(ROOT, 'build', 'vdp1cost', f'{rn}_{course}', 'f*.csv'))):
            recs = list(csv.DictReader(open(p)))
            if len(recs) > 1300:
                continue
            fi = len(frames)
            frames.append((ci, int(os.path.basename(p)[1:4]), sum(int(r['cycles']) for r in recs)))
            local = False
            for r in recs:
                ctrl, pmod = int(r['ctrl']), int(r['pmod'])
                if ctrl & 0xF == 10:
                    local = int(r['xa']) == -SCREEN[0]
                if ctrl & 0xF != 2 or ctrl & 0x4000 or not local or pmod & 4 or (pmod >> 3) & 7 not in (0, 1):
                    continue
                size = int(r['size'])
                w, h = (size >> 8) * 8, size & 0xFF
                if not w or not h:
                    continue
                pts = [(int(r['x' + k]), int(r['y' + k])) for k in 'abcd']
                flips = (ctrl >> 4) & 3
                k0 = coster.cost(ctrl, pmod, size, pts)
                k1 = kg = -1
                if h % 8 == 0:
                    tflips = ((flips & 1) << 1) | (flips >> 1)
                    tctrl = (ctrl & ~0x30) | (tflips << 4)
                    k1 = coster.cost(tctrl, pmod, ((h // 8) << 8) | w, pts[1:] + pts[:1])
                sw = strip_width(w, h)
                pieces = core.grid(pts, w, h, flips, sw) if sw else None
                est_parts = n_pieces = -1
                if pieces is not None:
                    kg = sum(coster.cost(ctrl, pmod, ((sw // 8) << 8) | rows, c) for c, _, _, rows in pieces)
                    est_parts = sum(core.estimate(c) for c, _, _, _ in pieces)
                    n_pieces = len(pieces)
                quads.append((fi, ci, int(r['srca']), size, flips, k0, k1, kg, core.turn(pts),
                              core.estimate(pts), est_parts, n_pieces, int(r['cycles'])))
        print(f'{course}: {sum(1 for f in frames if f[0] == ci)} frames, {sum(1 for q in quads if q[1] == ci)} quads',
              flush=True)
    names = ('frame', 'course', 'srca', 'size', 'flips', 'k0', 'k1', 'kg', 'turn', 'est', 'est_parts', 'pieces', 'logged')
    q = np.array(quads, np.int64)
    np.savez(os.path.join(OUT, 'quads.npz'), frames=np.array(frames, np.int64),
             **{n: q[:, i] for i, n in enumerate(names)})


def records(course):
    """The course's texture records (VRAM texture in 8 bytes, size) by index, as the race relocates them."""
    mdl = open(os.path.join(ROOT, 'build', 'cce_files', 'DAYTONA', f'COURSE{course}.MDL'), 'rb').read()
    _, recs, _ = turn_quads.tables(mdl)
    base = (0x10100 + max(r[1] for r in recs) * 8 + 32) // 8
    return [(base + r[2], r[3]) for r in recs]


def choose(min_cut=50000, kinds=('cut',)):
    d = np.load(os.path.join(OUT, 'quads.npz'))
    frames = d['frames']
    out = {}
    for ci, course in enumerate(COURSES):
        m = d['course'] == ci
        fr = np.flatnonzero(frames[:, 0] == ci)
        total = frames[fr, 2].astype(float)
        fidx = {f: i for i, f in enumerate(fr)}
        q = {k: d[k][m] for k in d.files if k != 'frames'}
        cut = (q['pieces'] >= 0) & (q['est'] >= min_cut)
        turn = (q['k1'] >= 0) & (q['turn'] == 1)
        fi = np.array([fidx[f] for f in q['frame']])
        recs = records(ci)

        def saved(t, kinds):
            """Frame time saved, by frame, by a texture's quads given these kinds of copies (a cut first)."""
            g = np.zeros(len(fr))
            c = t & cut if 'cut' in kinds else np.zeros_like(t)
            u = t & turn & ~c if 'turn' in kinds else np.zeros_like(t)
            np.add.at(g, fi[c], (q['k0'] - q['kg'])[c])
            np.add.at(g, fi[u], (q['k0'] - q['k1'])[u])
            return g

        texs = {}
        for s, z in sorted(set(zip(q['srca'].tolist(), q['size'].tolist()))):
            if (s, z) in recs:
                texs[(s, z)] = (q['srca'] == s) & (q['size'] == z)
        # greedy: most frame time over 85% saved a byte, then most saved a byte
        state = {k: () for k in texs}
        chosen, used, cur = [], 0, total.copy()
        while True:
            best, best_v = None, 0
            for (s, z), t in texs.items():
                nbytes = ((z >> 8) * 8 * (z & 0xFF) // 2 + 7) & ~7
                if place([c[3] for c in chosen] + [nbytes], ci) is None:
                    continue
                for kind in kinds:
                    if kind in state[(s, z)] or (kind == 'turn' and (z & 0xFF) % 8) or (kind == 'cut' and not strip_width((z >> 8) * 8, z & 0xFF)):
                        continue
                    g = saved(t, state[(s, z)] + (kind,)) - saved(t, state[(s, z)])
                    over = np.maximum(cur - 0.85 * F, 0).sum() - np.maximum(cur - g - 0.85 * F, 0).sum()
                    v = (over * 10 + g.sum()) / nbytes
                    if v > best_v:
                        best, best_v = (kind, s, z, nbytes, g), v
            if best is None:
                break
            kind, s, z, nbytes, g = best
            state[(s, z)] += (kind,)
            chosen.append(best)
            used += nbytes
            cur -= g
        over0 = (total > BUDGET * F).sum()
        over1 = (cur > BUDGET * F).sum()
        print(f'{course}: {len(chosen)} textures ({sum(1 for c in chosen if c[0] == "cut")} cut) in {used} bytes; '
              f'mean {100 * total.mean() / F:.1f}% -> {100 * cur.mean() / F:.1f}%, '
              f'max {100 * total.max() / F:.1f}% -> {100 * cur.max() / F:.1f}%, over {over0} -> {over1} of {len(fr)}')
        out[str(ci)] = [{'record': recs.index((s, z)), 'srca': s, 'size': z, 'kind': kind} for kind, s, z, _, _ in chosen]
    return out


def main():
    if sys.argv[1] == 'data':
        data(sys.argv[2] if len(sys.argv) > 2 else 'final')
    elif sys.argv[1] == 'choose':
        out = choose()
        json.dump({'note': 'tools/vdp1x_eval.py choose: textures given a turned copy or strips at race start',
                   'courses': out}, open(CHOICES, 'w'), indent=1)


if __name__ == '__main__':
    main()
