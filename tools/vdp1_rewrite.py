"""What changes to a frame's VDP1 list would save, measured offline: a list taken
by tools/stepwise.py, rewritten as new drawing code would write it, and drawn
again with the Mednafen fork's VDP1 code (tools/vdp1lib.py, calibrated).

usage: vdp1_rewrite.py NAME [NAME ...]

For each frame, these lists (each against the list as captured):
  oracle   every textured quad drawn whichever way round is cheaper, turned
           (its corners from B, its texture turned a quarter) or not: the
           bound for turning quads as they're drawn
  rule     turned when an estimate from the corners says so (RULE below):
           what the drawing code would get
  bands    quads dearer than BAND_CYCLES cut into bands of
           texture rows (along A-D), bands wholly off the screen left out
  both     rule and bands together (a quad turned first, then cut)

A turned texture's copy goes into VRAM that the frame doesn't use (zero
runs after the course's textures), as the game would hold it. Costs don't
depend on what's already drawn, so each command is costed alone too.
"""
import ctypes
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from vdp1lib import Vdp1        # noqa: E402

STEPWISE = os.path.join(ROOT, 'build', 'stepwise')
SCREEN = (-176, -135, 175, 88)  # the local coordinates the race sets: x, y from the centre
BAND_CYCLES = 15000            # a quad dearer than this (alone) is cut into bands
BAND_ROWS = 8                   # texture rows a band, at most
F = 28636360 / 30


def load(name):
    raw = open(os.path.join(STEPWISE, name, 'vram.bin'), 'rb').read()
    v = Vdp1(dll=os.path.join(ROOT, 'tools', 'mednafen', 'vdp1lib.dll'))
    v.load_vram(raw)
    cmds = []
    addr, ret, guard = 0, ctypes.c_int32(-1), 0
    v.reset()
    while addr >= 0 and guard < 0x10000:
        guard += 1
        word = int(v.vram[addr])
        if word & 0x8000:
            break
        c = [int(x) for x in v.vram[addr:addr + 0x10]]
        nxt, cost = v.step(addr, ret)
        if not word & 0x4000:
            cmds.append(c)
        addr = nxt
    return v, raw, cmds


def corners(c):
    return [(c[6 + 2 * i] - 65536 if c[6 + 2 * i] & 0x8000 else c[6 + 2 * i],
             c[7 + 2 * i] - 65536 if c[7 + 2 * i] & 0x8000 else c[7 + 2 * i]) for i in range(4)]


def set_corners(c, pts):
    c = list(c)
    for i, (x, y) in enumerate(pts):
        c[6 + 2 * i], c[7 + 2 * i] = x & 0xFFFF, y & 0xFFFF
    return c


def cheb(p, q):
    return max(abs(p[0] - q[0]), abs(p[1] - q[1]))


class Space:
    """Free VRAM for turned copies: zero runs past the course's textures."""

    def __init__(self, raw):
        z = np.frombuffer(raw, np.uint8) == 0
        self.runs = []
        i = 0x10100
        while i < len(z):
            if z[i]:
                j = i
                while j < len(z) and z[j]:
                    j += 1
                if j - i >= 256:
                    self.runs.append([(i + 7) & ~7, j & ~7])
                i = j
            else:
                i += 1
        self.used = 0

    def take(self, n):
        for r in self.runs:
            if r[1] - r[0] >= n:
                at = r[0]
                r[0] += (n + 7) & ~7
                self.used += n
                return at
        return None


def turned_texture(v, src, w, h):
    """The 4-bit w x h texture at byte src turned a quarter (h wide): its bytes."""
    words = v.vram[src // 2:src // 2 + w * h // 4].astype('>u2').tobytes()
    raw = np.frombuffer(words, np.uint8)
    px = np.empty(w * h, np.uint8)
    px[0::2], px[1::2] = raw >> 4, raw & 15
    new = px.reshape(h, w)[:, ::-1].T.reshape(-1)
    return ((new[0::2] << 4) | new[1::2]).astype(np.uint8).tobytes()


class Frame:
    def __init__(self, name):
        self.name = name
        self.v, self.raw, self.cmds = load(name)
        self.space = Space(self.raw)
        self.copies = {}            # (src, size) -> (src', size') of a turned copy
        self.setup = {}             # the clip and local-coordinate commands in force, by kind

    def turnable(self, c):
        kind, mode = c[0] & 0xF, c[2]
        size = c[5]
        w, h = (size >> 8) * 8, size & 0xFF
        return kind == 2 and not c[0] & 0x30 and (mode >> 3) & 7 in (0, 1) and h % 8 == 0 and h > 0 and w > 0

    def copy_of(self, c):
        key = (c[4], c[5])
        if key not in self.copies:
            w, h = (c[5] >> 8) * 8, c[5] & 0xFF
            data = turned_texture(self.v, c[4] * 8, w, h)
            at = self.space.take(len(data))
            if at is None:
                self.copies[key] = None
            else:
                self.v.vram[at // 2:at // 2 + len(data) // 2] = np.frombuffer(data, '>u2')
                self.copies[key] = (at // 8, ((h // 8) << 8) | w)
        return self.copies[key]

    def turned(self, c):
        cp = self.copy_of(c)
        if cp is None:
            return None
        a, b, cc, d = corners(c)
        t = set_corners(c, [b, cc, d, a])
        t[4], t[5] = cp
        return t

    def cost(self, c):
        """One command's cycles, drawn alone at a scratch place after the clip and local coordinates in force."""
        at = 0x7C00             # words (byte 0xF800): the command area's end, past any list
        seq = [self.setup[k] for k in sorted(self.setup)] + [c]
        for i, x in enumerate(seq):
            x = list(x)
            x[0] &= 0x0FFF
            self.v.vram[at + 16 * i:at + 16 * i + 16] = x
        self.v.vram[at + 16 * len(seq)] = 0x8000
        self.v.reset()
        ret, addr = ctypes.c_int32(-1), at
        for _ in range(len(seq) - 1):
            addr = self.v.step(addr, ret)[0]
        return self.v.step(addr, ret)[1].cycles

    def plot(self, cmds):
        at = 0                  # the list's own place: up to 0xF800
        for i, c in enumerate(cmds):
            c = list(c)
            c[0] &= 0x0FFF      # jump: none, the next
            self.v.vram[at + 16 * i:at + 16 * i + 16] = c
        self.v.vram[at + 16 * len(cmds)] = 0x8000
        self.v.reset()
        ret, addr, total = ctypes.c_int32(-1), at, 0
        while addr >= 0:
            if int(self.v.vram[addr]) & 0x8000:
                break
            addr, cost = self.v.step(addr, ret)
            total += cost.cycles
        return total


def rule(c):
    """Turn? An estimate of both ways' cost from the corners alone: lines (a fixed cost each) and the pixels
    the lines step through (each line as long as the two edges it runs between, on average)."""
    a, b, cc, d = corners(c)
    lines_now = max(cheb(a, d), cheb(b, cc)) + 1
    lines_turn = max(cheb(a, b), cheb(d, cc)) + 1
    px_now = lines_now * (cheb(a, b) + cheb(d, cc) + 2) / 2
    px_turn = lines_turn * (cheb(a, d) + cheb(b, cc) + 2) / 2
    return lines_turn * 16 + px_turn * 1.0 < (lines_now * 16 + px_now * 1.0) * 0.95


def off_screen(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return max(xs) < SCREEN[0] or min(xs) > SCREEN[2] or max(ys) < SCREEN[1] or min(ys) > SCREEN[3]


def bands(c):
    """A quad cut into bands of texture rows along A-D (B-C): the bands not wholly off the screen."""
    a, b, cc, d = corners(c)
    w, h = (c[5] >> 8) * 8, c[5] & 0xFF
    row_bytes = w // 2
    step = BAND_ROWS
    while step > 1 and (step * row_bytes) % 8:
        step -= 1
    if (step * row_bytes) % 8:
        return [c]
    out = []
    lerp = lambda p, q, t: (round(p[0] + (q[0] - p[0]) * t), round(p[1] + (q[1] - p[1]) * t))
    for r0 in range(0, h, step):
        r1 = min(h, r0 + step)
        t0, t1 = r0 / h, r1 / h
        pts = [lerp(a, d, t0), lerp(b, cc, t0), lerp(b, cc, t1), lerp(a, d, t1)]
        if off_screen(pts):
            continue
        n = set_corners(c, pts)
        n[4] = c[4] + r0 * row_bytes // 8
        n[5] = ((w // 8) << 8) | (r1 - r0)
        out.append(n)
    return out


def main():
    for name in sys.argv[1:]:
        f = Frame(name)
        base = f.plot(f.cmds)
        oracle, ruled, banded, both = [], [], [], []
        agree = total_turnable = 0
        for c in f.cmds:
            if c[0] & 0xF >= 8:
                f.setup[c[0] & 0xF] = c
            k = f.cost(c)
            best = pick = c
            if f.turnable(c):
                t = f.turned(c)
                if t is not None:
                    kt = f.cost(t)
                    total_turnable += 1
                    best = t if kt < k else c
                    pick = t if rule(c) else c
                    agree += (pick is best) or kt == k
            oracle.append(best)
            ruled.append(pick)
            banded.extend(bands(c) if c[0] & 0xF == 2 and k > BAND_CYCLES else [c])
            kp = k if pick is c else f.cost(pick)
            both.extend(bands(pick) if pick[0] & 0xF == 2 and kp > BAND_CYCLES else [pick])
        res = {k: f.plot(v) for k, v in (('oracle', oracle), ('rule', ruled), ('bands', banded), ('both', both))}
        print(f'{name}: {len(f.cmds)} commands, {100 * base / F:.1f}% of a frame; turned copies {f.space.used // 1024} KB; '
              f'rule agrees with the oracle on {agree} of {total_turnable} turnable quads')
        for k, v in res.items():
            print(f'  {k:7s} {100 * v / F:5.1f}%  ({100 * (v - base) / F:+.1f})')


if __name__ == '__main__':
    main()
