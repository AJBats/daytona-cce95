"""Chooses the course textures tools/turn_quads.py turns, by what turning them
saved VDP1 over a lap of each course, and writes tools/turned_quads.json.

usage: turn_choice.py <cce extracted dir> <base run> <trial run>
  The runs are tools/vdp1_lap.py's (build/vdp1cost/<run>_<course>): base of
  a disc with nothing turned, trial of one with every texture that can turn
  turned (TURNED_QUADS naming a list of them all, turn_choice.py --all
  writes it).
usage: turn_choice.py <cce extracted dir> --all <list.json>

Both runs' races start on the same frame and the game's state doesn't
depend on what VDP1 draws, so frame for frame the logs hold the same
commands, a turned texture's quads drawn the other way in the trial. A
texture is chosen when its quads took fewer cycles turned, summed over the
lap's frames that both runs finished (a frame VDP1 didn't finish has its log
run on into the next plots).

Turning saves lines, a fixed time each, when a quad's lines run across its
short side; but a quad in perspective is a trapezoid, and turned its lines
all start from the narrow edge and pile up there, so it can draw more
pixels than it saves lines. Estimates from the edges alone chose textures
that cost more turned (2026-11-07, docs/performance.md); hence measuring.
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turn_quads  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = 28636360 // 30          # VDP1 cycles in a 30 fps frame
NAMES = ['t7', 'dino', 'sea', 'np', 'desert']
SINGLE = 1300               # a log longer than this ran into the next plot


def turnable(cce, c):
    mdl = open(os.path.join(cce, 'DAYTONA', f'COURSE{c}.MDL'), 'rb').read()
    _, records, blocks = turn_quads.tables(mdl)
    quads, tris = set(), set()
    for o, a, w, k in turn_quads.polygons(mdl, blocks):
        if (a >> 5) & 15 == 2 and w // 8 < len(records):
            (tris if k == 3 else quads).add((records[w // 8][2], records[w // 8][3]))
    return records, sorted(t for t in quads - tris if (t[1] & 0xFF) % 8 == 0)


def per_texture(path, tex_vram, clut_end, turned):
    """Cycles by (texture, size as unturned) in one log, or None for a log that ran on."""
    rows = list(csv.DictReader(open(path)))
    if len(rows) > SINGLE:
        return None
    out = defaultdict(int)
    for r in rows:
        if int(r['ctrl']) & 0xF != 2:
            continue
        at = int(r['srca']) * 8 - tex_vram - clut_end
        if at < 0 or at % 8:
            continue
        size = int(r['size'])
        if turned:      # back to the unturned size: w' = h, h' = w
            size = ((size & 0xFF) // 8 << 8) | (size >> 8) * 8
        out[(at // 8, size)] += int(r['cycles'])
    return out


def main():
    cce = sys.argv[1]
    if sys.argv[2] == '--all':
        out = {'courses': {str(c): [list(t) for t in turnable(cce, c)[1]] for c in range(5)}}
        json.dump(out, open(sys.argv[3], 'w'))
        return
    base, trial = sys.argv[2], sys.argv[3]
    out = {'note': 'tools/turn_choice.py: the textures tools/turn_quads.py turns, by course: '
                   '[texture (8-byte units past the colour tables), size (width / 8 << 8 | height)]',
           'courses': {}}
    for c, name in enumerate(NAMES):
        dirs = [os.path.join(ROOT, 'build', 'vdp1cost', f'{run}_{name}') for run in (base, trial)]
        if not all(glob.glob(os.path.join(d, 'f*.csv')) for d in dirs):
            print(f'course {c}: no logs')
            continue
        records, can = turnable(cce, c)
        clut_end = max(r[1] for r in records) * 8 + 32
        tex = open(os.path.join(cce, 'DAYTONA', f'COURSE{c}.TEX'), 'rb').read()
        tex_vram = open(os.path.join(dirs[0], 'vram.bin'), 'rb').read().find(tex[:0x400])
        before, after = defaultdict(int), defaultdict(int)
        frames = 0
        for path in sorted(glob.glob(os.path.join(dirs[0], 'f*.csv'))):
            other = os.path.join(dirs[1], os.path.basename(path))
            if not os.path.exists(other):
                continue
            b = per_texture(path, tex_vram, clut_end, False)
            t = per_texture(other, tex_vram, clut_end, True)
            if b is None or t is None:
                continue
            frames += 1
            for k, v in b.items():
                before[k] += v
            for k, v in t.items():
                after[k] += v
        chosen = sorted(k for k in can if after.get(k, 0) < before.get(k, 0))
        saved = sum(before[k] - after[k] for k in chosen)
        all_turned = sum(before[k] - after.get(k, 0) for k in can if k in before)
        out['courses'][str(c)] = [list(k) for k in chosen]
        print(f'course {c}: {frames} frames both runs finished; {len(chosen)} of {len(can)} textures save '
              f'{100 * saved / frames / F:.1f}% of a frame on average (all turned: {100 * all_turned / frames / F:+.1f}%)')
    path = os.path.join(ROOT, 'tools', 'turned_quads.json')
    json.dump(out, open(path, 'w'), indent=1)
    print(path)


if __name__ == '__main__':
    main()
