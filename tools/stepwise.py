"""How VDP1 builds a race frame, command by command: what each draws, what of it
is still there at the end, and what it is (course, our car, other cars, the
HUD). For a study of where VDP1's time goes. After the Tomb Raider project's
tools/stepwise.py, with its page (tools/stepwise.html) and its Mednafen VDP1
code (tools/vdp1lib.py).

    python -I tools/stepwise.py capture NAME "TITLE" --run RUN --course COURSE --log N [--disc CUE]
    python -I tools/stepwise.py page OUT.html NAME ...

capture loads tools/vdp1_lap.py's race state of RUN and COURSE in the
calibrated Mednafen, drives the same lap, stops at log N's frame (N x 10
frames on), and takes the list VDP1 is about to draw: at the next VBlank-OUT
handler (06005652) after the VBlank-IN one has taken a list (06011F99 set),
the copy done, the frame change just ahead. It then draws the list here one
command at a time with the Mednafen fork's own VDP1 code, so pixels are
exact; times are the calibrated Mednafen's (a little pessimistic against a
Saturn). build/stepwise/NAME/ holds the result: frame.json (commands and
what they are), writes.bin (what each command wrote). page puts frames into
one HTML page from tools/stepwise.html.

What a command is, by the texture it reads (found by matching the course's,
its objects' and our car's TEX files in VRAM) or its kind: the course's
quads (near: more than NEAR pixels stepped through), the course's objects,
our car, other cars and anything else textured, the HUD and sprites
(VDP1's normal and scaled sprites), and flat polygons (the shadow is a
mesh). On the page: Rooms = course, Lara = our car, Creatures = the course
near the camera, Static meshes = course objects, Other objects = other
cars, Fills = flat polygons, Sprites = HUD.
"""
import argparse
import base64
import ctypes
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import vdp1_lap                         # noqa: E402
from vdp1lib import Vdp1                # noqa: E402

OUT = os.path.join(ROOT, 'build', 'stepwise')
W, H = 352, 224
MS = 1000 / 28636360
NEAR = 6000
CCE = os.path.join(ROOT, 'build', 'cce_files', 'DAYTONA')
EXTRACTED = os.path.join(ROOT, 'extracted', 'cce', 'DAYTONA')


def capture(name, title, run, course, log, disc):
    out = os.path.join(OUT, name)
    os.makedirs(out, exist_ok=True)
    m = vdp1_lap.Mednafen(disc)
    tmp = os.path.join(out, 'tmp.bin')
    try:
        m.send(f'load_state {os.path.join(vdp1_lap.OUT, f"{run}_states", f"{course}.mcs")}', 'load_state')
        m.send(f'poke_playback_start 06035EE8 {vdp1_lap.PLAYER:08X} 0 -1 hold 7 x:0:32 y:4:32 z:8:32 ang:C:32 '
               f'roll:10:16 trav:38:32 head:3C:32 {os.path.join(vdp1_lap.OUT, f"path_{course}.csv")}', 'poke_playback')
        if log:
            m.frames(log * vdp1_lap.STEP)
        m.send('breakpoint 06005652', 'breakpoint')
        for _ in range(8):
            m.send('run', 'break pc=', 120)
            m.send(f'dump_mem_bin 06011F99 1 {tmp}', 'dump_mem_bin')
            if open(tmp, 'rb').read()[0]:
                break
        m.send('breakpoint_clear', 'breakpoint')
        m.send(f'dump_region vdp1_vram {os.path.join(out, "vram.bin")}', 'dump_region')
        m.frames(4)
        shot = os.path.join(out, 'shot.png')
        if os.path.exists(shot):
            os.remove(shot)
        m.send(f'screenshot {shot}', 'screenshot')
        m.send('poke_playback_stop', 'poke_playback')
    finally:
        m.quit()
    os.remove(tmp)
    json.dump({'title': title, 'run': run, 'course': course, 'log': log}, open(os.path.join(out, 'capture.json'), 'w'))
    analyze(name)


def ranges(vram, course):
    """VRAM ranges of the course's textures, its objects' and our car's, as (start, end)."""
    c = vdp1_lap.COURSES.index(course)

    def find(path):
        if not os.path.exists(path):
            return None
        data = open(path, 'rb').read()
        at = vram.find(data[0x40:0x80])
        return (at - 0x40, at - 0x40 + len(data)) if at >= 0x40 else None

    return {'course': find(os.path.join(CCE, f'COURSE{c}.TEX')) or find(os.path.join(EXTRACTED, f'COURSE{c}.TEX')),
            'objects': find(os.path.join(EXTRACTED, f'CS{c}OBJ.TEX')),
            'car': find(os.path.join(CCE, 'PLCAR09.TEX'))}


def owner_of(c, at):
    """(label, category) of a command (its 16 words)."""
    kind = c[0] & 0xF
    inside = lambda key, a: at[key] and at[key][0] <= a < at[key][1]
    if kind >= 4:
        return ('shadow' if c[2] & 0x100 else 'flat polygons'), 'fill'
    src = c[4] * 8
    size = c[5]
    tex = f'{src:05X} {(size >> 8) * 8}x{size & 0xFF}'
    if kind in (0, 1):
        return 'HUD and sprites', 'sprite'
    if inside('car', src):
        return 'our car', 'lara'
    if inside('course', src):
        return f'course {tex}', 'room'
    if inside('objects', src):
        return f'course object {tex}', 'static'
    return 'other cars and textures', 'object'


def final_frame(commands, runs, run_at, colours, drop, box):
    """What the frame ends as, a colour per pixel and a mask of those written, with the commands in drop left out
    and a rectangle of colour 0 under the rest."""
    col = np.zeros((H, W), np.uint16)
    written = np.zeros((H, W), bool)
    if box:
        written[box[1]:box[3] + 1, box[0]:box[2] + 1] = True
    at = 0
    for i, c in enumerate(commands):
        n = c['written']
        if i not in drop:
            k = at
            for r in range(run_at[i], run_at[i + 1]):
                y, x, m = runs[r * 3], runs[r * 3 + 1], runs[r * 3 + 2]
                col[y, x:x + m] = colours[k:k + m]
                written[y, x:x + m] = True
                k += m
        at += n
    return np.where(col & 0x8000, col & 0x7FFF, 0), written


def analyze(name):
    out = os.path.join(OUT, name)
    cap = json.load(open(os.path.join(out, 'capture.json')))
    raw = open(os.path.join(out, 'vram.bin'), 'rb').read()
    at = ranges(raw, cap['course'])
    v = Vdp1(dll=os.path.join(ROOT, 'tools', 'mednafen', 'vdp1lib.dll'))
    v.load_vram(raw)
    v.reset()
    fb = v.fb
    S1, S2 = 0xFC1F, 0x83E0
    fb[:] = 0
    ret = ctypes.c_int32(-1)
    addr = 0
    commands, owners = [], {}
    runs, run_at, colors = [], [0], []
    last = -np.ones((H, W), np.int32)
    count = np.zeros((H, W), np.int32)
    guard = 0
    while addr >= 0 and guard < 0x10000:
        guard += 1
        word = int(v.vram[addr])
        if word & 0x8000:
            break
        kind = word & 0xF
        before = fb.copy()
        mask = None
        if not word & 0x4000 and kind < 8:
            for sentinel in (S1, S2):
                fb[:] = sentinel
                v.step(addr, ctypes.c_int32(ret.value))
                got = fb[:H, :W] != sentinel
                mask = got if mask is None else mask | got
            fb[:] = before
        nxt, cost = v.step(addr, ret)
        here = addr
        addr = nxt
        if word & 0x4000 or kind >= 8:
            continue
        c = [int(x) for x in v.vram[here:here + 0x10]]
        label, category = owner_of(c, at)
        if category == 'room' and cost.pixels > NEAR:
            category = 'creature'
        n = len(commands)
        written = 0
        ys, xs = np.nonzero(mask)
        if len(ys):
            written = len(ys)
            last[ys, xs] = n
            count[ys, xs] += 1
            colors.append(fb[:H, :W][ys, xs].astype('<u2'))
            start = 0
            for i in range(1, len(ys) + 1):
                if i == len(ys) or ys[i] != ys[start] or xs[i] != xs[i - 1] + 1:
                    runs.extend((int(ys[start]), int(xs[start]), i - start))
                    start = i
        run_at.append(len(runs) // 3)
        corners = [c[6 + i] - 65536 if c[6 + i] & 0x8000 else c[6 + i] for i in range(8)]
        commands.append({'owner': owners.setdefault(label, len(owners)), 'cat': category, 'kind': kind, 'cycles': cost.cycles,
                         'lines': cost.lines, 'plotted': cost.pixels, 'texels': cost.texels, 'written': written, 'corners': corners,
                         'tw': (c[5] >> 8) * 8, 'th': c[5] & 255, 'mode': c[2], 'slot': here * 2 // 32})
    seen = np.bincount(last[last >= 0], minlength=len(commands))
    for i, c in enumerate(commands):
        c['seen'] = int(seen[i])
    labels = sorted(owners, key=owners.get)
    table = [dict(name=n, cat=None, commands=0, written=0, seen=0, cycles=0, plotted=0) for n in labels]
    for c in commands:
        t = table[c['owner']]
        t['cat'] = c['cat'] if t['cat'] in (None, 'room') else t['cat']
        t['commands'] += 1
        t['written'] += c['written']
        t['seen'] += c['seen']
        t['cycles'] += c['cycles']
        t['plotted'] += c['plotted']
    colours = np.concatenate(colors) if colors else np.zeros(0, '<u2')
    open(os.path.join(out, 'writes.bin'), 'wb').write(colours.tobytes())
    open(os.path.join(out, 'runs.bin'), 'wb').write(np.array(runs, '<u2').tobytes())
    open(os.path.join(out, 'run_at.bin'), 'wb').write(np.array(run_at, '<u4').tobytes())
    total = sum(c['cycles'] for c in commands)
    never = int((last < 0).sum())
    hist = np.bincount(count.ravel(), minlength=9).tolist()
    wasted = sum(c['cycles'] * (1 - c['seen'] / c['written']) if c['written'] else c['cycles'] for c in commands)
    gone = sum(c['cycles'] for c in commands if c['written'] and not c['seen'])
    empty = {'drop': [], 'box': None, 'cycles': 0, 'differ': 0, 'never': never}
    frame = {'title': cap['title'], 'name': name, 'width': W, 'height': H, 'commands': commands, 'owners': table, 'never': never,
             'hist': hist, 'cycles': total, 'wasted': wasted, 'gone': gone, 'ms': MS,
             'plottedTotal': sum(c['plotted'] for c in commands), 'black': {'run': empty, 'all': empty}}
    json.dump(frame, open(os.path.join(out, 'frame.json'), 'w'))
    report(frame)


def report(f):
    cmds = f['commands']
    screens = sum(c['written'] for c in cmds) / (W * H)
    frame_cycles = 28636360 / 30
    print(f'{f["title"]}: {len(cmds)} commands, VDP1 {f["cycles"] * MS:.2f} ms = {100 * f["cycles"] / frame_cycles:.0f}% of a 30 fps '
          f'frame, {sum(c["written"] for c in cmds)} pixels written = {screens:.2f} screens, {f["plottedTotal"]} stepped through')
    print(f'  time on pixels gone by the end: {f["wasted"] * MS:.2f} ms ({f["wasted"] * 100 / f["cycles"]:.0f}%); commands wholly '
          f'gone: {sum(1 for c in cmds if c["written"] and not c["seen"])} = {f["gone"] * MS:.2f} ms; drawing nothing on the '
          f'screen: {sum(1 for c in cmds if not c["written"])} = {sum(c["cycles"] for c in cmds if not c["written"]) * MS:.2f} ms')
    names = {'room': 'course', 'creature': 'course near', 'static': 'course objects', 'lara': 'our car', 'object': 'other cars',
             'fill': 'flat polygons', 'sprite': 'HUD, sprites'}
    cats = {}
    for c in cmds:
        s = cats.setdefault(c['cat'], [0, 0, 0, 0, 0])
        s[0] += 1
        s[1] += c['cycles']
        s[2] += c['written']
        s[3] += c['seen']
        s[4] += c['plotted']
    for k, s in sorted(cats.items(), key=lambda a: -a[1][1]):
        print(f'  {names.get(k, k):14s} {s[0]:5d} commands {s[1] * MS:6.2f} ms  stepped {s[4]:7d}  written {s[2]:7d}  '
              f'seen {s[3]:6d} ({s[3] * 100 / max(s[2], 1):3.0f}%)')
    print('  by owner, dearest:')
    for o in sorted(f['owners'], key=lambda o: -o['cycles'])[:14]:
        print(f'    {o["name"][:28]:28s} {o["commands"]:4d} cmds {o["cycles"] * MS:6.2f} ms  stepped {o["plotted"]:7d}  '
              f'written {o["written"]:6d}  seen {o["seen"]:6d}')


def page(out_path, names):
    frames = []
    for name in names:
        d = os.path.join(OUT, name)
        f = json.load(open(os.path.join(d, 'frame.json')))
        for key in ('writes', 'runs', 'run_at'):
            f[key] = base64.b64encode(open(os.path.join(d, f'{key}.bin'), 'rb').read()).decode()
        frames.append(f)
    html = open(os.path.join(ROOT, 'tools', 'stepwise.html'), encoding='utf-8').read()
    html = html.replace('/*FRAMES*/null', json.dumps(frames, separators=(',', ':')))
    with open(out_path, 'w', encoding='utf-8', newline='\n') as o:
        o.write(html)
    print(out_path, os.path.getsize(out_path) >> 10, 'KB')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='what', required=True)
    c = sub.add_parser('capture')
    c.add_argument('name')
    c.add_argument('title')
    c.add_argument('--run', required=True)
    c.add_argument('--course', required=True)
    c.add_argument('--log', type=int, required=True)
    c.add_argument('--disc', default=os.path.join(ROOT, 'build', 'disc', 'cce.cue'))
    a = sub.add_parser('analyze')
    a.add_argument('name')
    p = sub.add_parser('page')
    p.add_argument('out')
    p.add_argument('names', nargs='+')
    args = ap.parse_args()
    if args.what == 'capture':
        capture(args.name, args.title, args.run, args.course, args.log, args.disc)
    elif args.what == 'analyze':
        analyze(args.name)
    else:
        page(args.out, args.names)


if __name__ == '__main__':
    main()
