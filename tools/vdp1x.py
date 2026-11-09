"""Race-time VDP1 work on the course's quads: src/vdp1x.c built into a block of
SCREEN.BIN (docs/performance.md, "Race-time quads").

usage: vdp1x.py <cce extracted dir> <out dir>
  Writes DAYTONA/SCREEN.BIN under <out dir> (CCE's, with one more block) and
  the course and car effects models with their polygons marked, and lists
  them in PATCHED.txt. Run after tools/turn_quads.py: the textures' sums are taken
  from the course TEX files in <out dir>, the models marked there.

SCREEN.BIN is a block file: a count, a (size, address) pair a block, then the
blocks one after another; CCE's loader (06007D94, from the race start at
0602927C, read to 0x220000) copies each block to its address. The new block
goes to work RAM 06015140 (06015140-06019A20 stays untouched through races; the
attract loads other files): src/vdp1x.ld.

The block's tables come from tools/vdp1x_choices.json (tools/vdp1x_eval.py
choose): per course, the textures given strips, by texture record. Each
texture's strips get their place here in the course's free VDP1 VRAM
(vdp1x_eval.FREE, the first 8 bytes a sign), and each texture its place in
VRAM as the race loads the course (the course's TEX at 0x10100, its colour
tables first) and the sum of its words, which the block checks before
copying it.

The block cuts quads as CCE builds them, polygon by polygon, but only the
course's polygons drawn with a texture that has strips come to it
(patches/vdp1x.s): those get bit 14 of their attribute set here (MARK), a
bit no course polygon has and CCE masks off wherever it reads the
attribute. The car effects' smoke and sparks polygons (CAREFC.MDL) get bit
15 (FX_MARK), so the block can draw them last.
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
BLOCK_AT = 0x06015140            # the block and its work areas, up to BLOCK_END (untouched through races)
BLOCK_END = 0x06019A20
MAGIC = 0x5658
EMIT_AT = BLOCK_AT + 28         # the block's way in from CCE's polygon tail (patches/vdp1x.s)
MARK = 0x4000                   # attribute bit 14: the polygon's texture has strips
FX_MARK = 0x8000                # attribute bit 15: a car effect's polygon
MIN_CUT = 50000                # a quad estimated dearer than this (cycles) may be cut (tools/vdp1x_eval.py)
MAX_PIECES = 64
EXTRACTED = os.path.join(ROOT, 'extracted', 'cce', 'DAYTONA')
# The car effects the block draws last, as (offset in CAREFC.TEX, width, height): the tire smoke and the
# three frames of the sparks. Not the file's other pictures (the cars' wheels among them).
EFFECTS = [(0x3340, 32, 32), (0x09C0, 48, 48), (0x0E40, 48, 48), (0x12C0, 48, 48)]


def course_table(out, course, wanted):
    """Rows (srca, size, strips, sum) sorted by srca, in VRAM's 8 bytes."""
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
        assert strip_width(w, h) == (8 if w % 16 else 16)    # src/vdp1x.c works the width out the same way
        rows.append([base + rel, size, a // 8, sum(struct.unpack(f'>{n // 2}H', data)) & 0xFFFF])
    return sorted(rows)


def mark_course(mdl, wanted):
    """The course's model with MARK on its textured polygons drawn with a texture given strips (from any of
    the texture records for that texture and size), and how many."""
    mdl = bytearray(mdl)
    _, records, blocks = turn_quads.tables(mdl)
    keys = {tuple(records[e['record']][2:]) for e in wanted if e['kind'] == 'cut'}
    every = bool(os.environ.get('VX_MARK_ALL'))     # test builds only: every textured polygon (with -DVX_POLYID)
    marked = 0
    for o, attr, word, k in turn_quads.polygons(mdl, blocks):
        assert not attr & MARK
        if (attr >> 5) & 15 == 2 and word // 8 < len(records) and (every or tuple(records[word // 8][2:]) in keys):
            struct.pack_into('>H', mdl, o, attr | MARK)
            marked += 1
    return bytes(mdl), marked


def mark_effects(mdl):
    """CAREFC.MDL with FX_MARK on the polygons drawn with one of EFFECTS, and how many. The file: the texture
    table first (a word count, a zero word, then the records as the course models have them), then its
    block models one after another, each on 4 bytes: a header of vertex count, polygon count and the offsets
    of its vertices, polygons (20, just after the header) and the texture table (back to the start), then
    its polygons (as the course models'); the vertices after the last block."""
    mdl = bytearray(mdl)
    n = struct.unpack_from('>H', mdl, 0)[0]
    records = [struct.unpack_from('>4H', mdl, 8 + 8 * i) for i in range(n)]
    clut_end = max(r[1] for r in records) * 8 + 32
    wanted = {i for i, r in enumerate(records) if any(r[2] * 8 + clut_end == off for off, _, _ in EFFECTS)}
    at, vertices, marked = 8 + 8 * n, len(mdl), 0
    while at < vertices:
        _, npoly, voff, poff, toff = struct.unpack_from('>HHIIi', mdl, at)
        assert poff == 20 and at + toff == 0, hex(at)
        vertices = min(vertices, at + voff)
        o = at + poff
        for _ in range(npoly):
            attr, word = struct.unpack_from('>HH', mdl, o)
            assert not attr & (MARK | FX_MARK)
            if (attr >> 5) & 15 == 2 and word // 8 in wanted:
                struct.pack_into('>H', mdl, o, attr | FX_MARK)
                marked += 1
            o += 4 + 2 * (3 if attr & 1 else 4) + (6 if attr & 32 else 0)
        at = (o + 3) & ~3
    assert at == vertices
    return bytes(mdl), marked


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
             '/* by course, sorted by texture: texture, size, strips (in 8 bytes), sum of the texture words */',
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
    extra = os.environ.get('VDP1X_CFLAGS', '').split()     # test builds only, e.g. -DVX_LATEST=4000
    run(os.path.join(GCC, 'sh2eb-elf-gcc'), '-m2', '-mb', '-O2', '-fomit-frame-pointer', '-ffreestanding',
        '-fno-zero-initialized-in-bss', '-nostdlib', '-I', work, *extra, '-T', src[:-2] + '.ld', '-Wl,-e,_vx_block',
        '-Wl,--no-warn-rwx-segments', '-Wl,-Map,' + os.path.join(work, 'vdp1x.map'), '-o', elf, src, '-lgcc')
    run(os.path.join(GCC, 'sh2eb-elf-objcopy'), '-O', 'binary', '-j', '.blob', elf, binf)
    block = open(binf, 'rb').read()
    heads = subprocess.run([os.path.join(GCC, 'sh2eb-elf-objdump'), '-h', elf], env=env, check=True,
                           capture_output=True, text=True).stdout
    sect = {p[1]: (int(p[3], 16), int(p[2], 16)) for p in (line.split() for line in heads.splitlines())
            if len(p) >= 7 and p[0].isdigit()}
    assert struct.unpack_from('>H', block)[0] == MAGIC and sect['.blob'][0] == BLOCK_AT and len(block) % 4 == 0
    syms = subprocess.run([os.path.join(GCC, 'sh2eb-elf-nm'), elf], env=env, check=True, capture_output=True,
                          text=True).stdout
    entry = {p[2]: int(p[0], 16) for p in (line.split() for line in syms.splitlines()) if len(p) == 3}
    assert entry['_vx_emit_entry'] == EMIT_AT, hex(entry['_vx_emit_entry'])
    work_end = sect['.work'][0] + sect['.work'][1]
    assert work_end <= BLOCK_END, hex(work_end)
    return block, tables, work_end


def main():
    cce, out = sys.argv[1], sys.argv[2]
    block, tables, work_end = build(out)
    screen = open(os.path.join(cce, 'DAYTONA', 'SCREEN.BIN'), 'rb').read()
    n = struct.unpack_from('>I', screen)[0]
    pairs = screen[4:4 + 8 * n]
    new = struct.pack('>I', n + 1) + pairs + struct.pack('>II', len(block), BLOCK_AT) + screen[4 + 8 * n:] + block
    open(os.path.join(out, 'DAYTONA', 'SCREEN.BIN'), 'wb').write(new)
    names = ['DAYTONA/SCREEN.BIN']
    choices = json.load(open(CHOICES))['courses']
    marked = []
    for c in range(5):
        path = os.path.join(out, 'DAYTONA', f'COURSE{c}.MDL')
        mdl, k = mark_course(open(path, 'rb').read(), choices.get(str(c), []))
        open(path, 'wb').write(mdl)
        names.append(f'DAYTONA/COURSE{c}.MDL')
        marked.append(k)
    efc, fx_marked = mark_effects(open(os.path.join(EXTRACTED, 'CAREFC.MDL'), 'rb').read())
    open(os.path.join(out, 'DAYTONA', 'CAREFC.MDL'), 'wb').write(efc)
    names.append('DAYTONA/CAREFC.MDL')
    listing = os.path.join(out, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [x for x in names if x not in have]
    open(listing, 'w').write(''.join(x + '\n' for x in sorted(have)))
    print(f'vdp1x: block of {len(block)} bytes at {BLOCK_AT:08X} (work areas to {work_end:08X}), SCREEN.BIN '
          f'{len(new)} bytes; textures ' + ', '.join(f'course {c} {len(t)}' for c, t in enumerate(tables))
          + '; polygons marked ' + ', '.join(map(str, marked)) + f', car effects {fx_marked}')


if __name__ == '__main__':
    main()
