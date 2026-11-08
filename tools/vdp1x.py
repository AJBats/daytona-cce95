"""Race-time VDP1 work on the course's quads: src/vdp1x.c built into a block of
SCREEN.BIN (docs/performance.md, "Race-time quads").

usage: vdp1x.py <cce extracted dir> <out dir>
  Writes DAYTONA/SCREEN.BIN under <out dir> (CCE's, with one more block) and
  lists it in PATCHED.txt. Run after tools/turn_quads.py: the textures' sums
  are taken from the course TEX files in <out dir>.

SCREEN.BIN is a block file: a count, a (size, address) pair a block, then the
blocks one after another; CCE's loader (06007D94, from the race start at
0602927C, read to 0x220000) copies each block to its address. The new block
goes to work RAM 06015140 (16 KB there stay zero through races; the attract
loads other files): src/vdp1x.ld.

The block's tables come from tools/vdp1x_choices.json (tools/vdp1x_eval.py
choose): per course, the textures given strips, by texture record. Each
texture's strips get their place here in the course's free VDP1 VRAM
(vdp1x_eval.FREE, the first 8 bytes a sign), and each texture its place in
VRAM as the race loads the course (the course's TEX at 0x10100, its colour
tables first) and the sum of its words, which the block checks before
copying it.
"""
import json
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turn_quads                       # noqa: E402
from vdp1x_eval import BAND, CHOICES, FREE, place, strip_width  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCC = os.path.join(ROOT, 'tools', 'sh-gcc', 'bin')
BLOCK_AT = 0x06015140
BLOCK_ROOM = 0x4000             # zero through races from BLOCK_AT
MAGIC = 0x5658
MIN_CUT = 50000                 # a quad estimated dearer than this (cycles) may be cut (tools/vdp1x_eval.py)
MAX_PIECES = 64


def course_table(out, course, wanted):
    """Rows (srca, size, strips, strip width, sum) sorted by srca, in VRAM's 8 bytes."""
    mdl = open(os.path.join(out, 'DAYTONA', f'COURSE{course}.MDL'), 'rb').read()
    tex = open(os.path.join(out, 'DAYTONA', f'COURSE{course}.TEX'), 'rb').read()
    _, records, _ = turn_quads.tables(mdl)
    clut_end = max(r[1] for r in records) * 8 + 32
    base = (0x10100 + clut_end) // 8
    wanted = [e for e in wanted if e['kind'] == 'cut']
    sizes = [(e['size'] >> 8) * 8 * (e['size'] & 0xFF) // 2 for e in wanted]
    at = place(sizes, course)
    if at is None:
        raise SystemExit(f'vdp1x: course {course}: the strips do not fit in its free VRAM')
    rows = []
    for e, n, a in zip(wanted, sizes, at):
        _, _, rel, size = records[e['record']]
        assert size == e['size'] and base + rel == e['srca'], (course, e)
        w, h = (size >> 8) * 8, size & 0xFF
        data = tex[clut_end + rel * 8:clut_end + rel * 8 + n]
        rows.append([base + rel, size, a // 8, strip_width(w, h), sum(struct.unpack(f'>{n // 2}H', data)) & 0xFFFF])
        assert rows[-1][3]
    return sorted(rows)


def header(tables):
    rows = [r for t in tables for r in t]
    first = [0]
    for t in tables:
        first.append(first[-1] + len(t))
    free = [[x for a, n in FREE[c] + [(0, 0)] * (2 - len(FREE[c])) for x in (a, n)] for c in range(len(tables))]
    lines = ['/* tools/vdp1x.py from tools/vdp1x_choices.json */',
             f'#define VX_COURSES {len(tables)}',
             f'#define VX_MAX_TEX {max(len(t) for t in tables)}',
             f'#define VX_BUF {max((r[1] >> 8) * 8 * (r[1] & 0xFF) // 2 for r in rows)}  /* the largest texture */',
             f'#define VX_BAND {BAND}',
             f'#define VX_MIN_CUT {MIN_CUT}',
             f'#define VX_MAX_PIECES {MAX_PIECES}',
             '/* by course, sorted by texture: texture, size, turned copy, strips (in 8 bytes, 0 none),',
             '   strip width, sum of the texture\'s words */',
             'static const unsigned short vx_list[] = {']
    lines += ['    ' + ', '.join(f'0x{x:04X}' for x in r) + ',' for r in rows]
    lines += ['};',
              'static const unsigned short vx_first[] = {' + ', '.join(map(str, first)) + '};',
              '/* by course, its free VDP1 VRAM: two (address, bytes) runs, the first 8 bytes the sign */',
              'static const unsigned int vx_free[][4] = {']
    lines += ['    {' + ', '.join(f'0x{x:05X}' for x in f) + '},' for f in free]
    lines += ['};', '']
    return '\n'.join(lines)


def build(out):
    work = os.path.join(ROOT, 'build', 'vdp1x')
    os.makedirs(work, exist_ok=True)
    choices = json.load(open(CHOICES))['courses']
    tables = [course_table(out, c, choices.get(str(c), [])) for c in range(5)]
    open(os.path.join(work, 'vdp1x_data.h'), 'w').write(header(tables))
    env = dict(os.environ, PATH=GCC + os.pathsep + os.environ['PATH'])
    src = os.path.join(ROOT, 'src', 'vdp1x.c')
    elf, binf = os.path.join(work, 'vdp1x.elf'), os.path.join(work, 'vdp1x.bin')
    run = lambda *cmd: subprocess.run(cmd, env=env, check=True)
    run(os.path.join(GCC, 'sh2eb-elf-gcc'), '-m2', '-mb', '-O2', '-fomit-frame-pointer', '-ffreestanding',
        '-fno-zero-initialized-in-bss', '-nostdlib', '-I', work, '-T', src[:-2] + '.ld', '-Wl,-e,_vx_block',
        '-Wl,--no-warn-rwx-segments', '-Wl,-Map,' + os.path.join(work, 'vdp1x.map'), '-o', elf, src, '-lgcc')
    run(os.path.join(GCC, 'sh2eb-elf-objcopy'), '-O', 'binary', '-j', '.blob', elf, binf)
    block = open(binf, 'rb').read()
    nm = subprocess.run([os.path.join(GCC, 'sh2eb-elf-nm'), elf], env=env, check=True, capture_output=True,
                        text=True).stdout
    syms = {s: int(a, 16) for a, _, s in (line.split() for line in nm.splitlines() if len(line.split()) == 3)}
    end = max(a for s, a in syms.items() if s.startswith('_')) if syms else 0
    assert struct.unpack_from('>H', block)[0] == MAGIC and syms['_vx_block'] == BLOCK_AT
    work_end = max(syms.get('_end', 0), end)
    assert len(block) % 4 == 0 and work_end <= BLOCK_AT + BLOCK_ROOM, hex(work_end)
    return block, tables, work_end


def main():
    cce, out = sys.argv[1], sys.argv[2]
    block, tables, work_end = build(out)
    screen = open(os.path.join(cce, 'DAYTONA', 'SCREEN.BIN'), 'rb').read()
    n = struct.unpack_from('>I', screen)[0]
    pairs = screen[4:4 + 8 * n]
    new = struct.pack('>I', n + 1) + pairs + struct.pack('>II', len(block), BLOCK_AT) + screen[4 + 8 * n:] + block
    open(os.path.join(out, 'DAYTONA', 'SCREEN.BIN'), 'wb').write(new)
    listing = os.path.join(out, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    if 'DAYTONA/SCREEN.BIN' not in have:
        have.append('DAYTONA/SCREEN.BIN')
    open(listing, 'w').write(''.join(x + '\n' for x in sorted(have)))
    print(f'vdp1x: block of {len(block)} bytes at {BLOCK_AT:08X} (work areas to {work_end:08X}); textures '
          + ', '.join(f'course {c} {len(t)}' for c, t in enumerate(tables)))


if __name__ == '__main__':
    main()
