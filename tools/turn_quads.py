"""Course quads turned a quarter, so VDP1 draws them in fewer lines.

usage: turn_quads.py <cce extracted dir> <out dir>
  Writes DAYTONA/COURSEn.MDL and COURSEn.TEX under <out dir> for the
  courses tools/turned_quads.json names, and lists them in PATCHED.txt.

VDP1 draws a textured quad as lines from its edge A-D to its edge B-C, one
line a texture row, as many as the longer of those two edges is long on
screen; each line costs a fixed time besides its pixels and texels (about
26 cycles in the calibrated Mednafen, tools/vdp1_lap.py). Many of the
courses' quads lie with A-D across the view, the long way on screen, so
VDP1 runs many short lines across them. Turned, the same quad from B with
its texture turned a quarter under it, the picture is the same and the
lines run the other way: as many as A-B or D-C is long.

Not every quad gains: one in perspective is a trapezoid, and turned, its
lines all start from the narrow edge and pile up there, more pixels than
the lines saved. A texture is turned in place, so every quad drawn with it
is turned: tools/turned_quads.json lists, per course, the textures (by
their place in the course's TEX and their size) whose quads drew faster
turned over a lap with the chase camera (tools/turn_choice.py: a run of
tools/vdp1_lap.py with nothing turned against one with every texture that
can turn turned, frame for frame). A texture a triangle uses stays as it is (a
triangle is three corners, the fourth C again, which no quarter turn
keeps), as does one whose height isn't a multiple of 8 (VDP1's widths are).

A course's model (COURSEn.MDL, loaded whole): a block model at each offset
the table at its end lists, after the texture table at the offset the first
model's header holds (+12): a word count, a zero word, then a record each
of draw mode, colour table, texture (in 8 bytes from the end of the colour
tables) and size (width / 8, height), as CCE's car models have. A block:
vertex count, polygon count, offsets of its vertices and polygons; a
polygon: attribute (bit 0 a triangle, bits 5-8 the draw mode, 2 textured,
bit 5 three more words), a word (a textured polygon's texture record x 8),
its 3 or 4 corners. COURSEn.TEX: the 16-colour tables (to the last record's
table and its 32 bytes), then the 4-bit textures.
"""
import json
import os
import struct
import sys

import numpy as np

CHOICES = os.environ.get('TURNED_QUADS',       # another list, to measure against (an empty one: none turned)
                         os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turned_quads.json'))


def tables(mdl):
    """The texture records (draw mode, colour table, texture, size) and the block models' offsets."""
    tab = struct.unpack_from('>I', mdl, 12)[0]
    n = struct.unpack_from('>H', mdl, tab)[0]
    records = [list(struct.unpack_from('>4H', mdl, tab + 8 + 8 * i)) for i in range(n)]
    end = tab + 8 + 8 * n
    blocks = set()
    for k in range((len(mdl) - end) // 8):
        _, off = struct.unpack_from('>Ii', mdl, end + 8 * k)
        if 0 <= end + off < tab:
            blocks.add(end + off)
    return tab, records, sorted(blocks)


def polygons(mdl, blocks):
    """(offset of the record, attribute, word, corner count) for every polygon."""
    out = []
    for at in blocks:
        _, npoly, _, poff = struct.unpack_from('>HHII', mdl, at)
        o = at + poff
        for _ in range(npoly):
            attr, word = struct.unpack_from('>HH', mdl, o)
            k = 3 if attr & 1 else 4
            out.append((o, attr, word, k))
            o += 4 + 2 * k + (6 if attr & 32 else 0)
    return out


def turn_texture(tex, at, w, h):
    """The 4-bit w x h texture at tex[at:] turned a quarter: texel (u, v) of the turned one (h wide)
    is (w - 1 - v, u) of the old, so a quad drawn from its B corner shows the same picture."""
    raw = np.frombuffer(bytes(tex[at:at + w * h // 2]), np.uint8)
    px = np.empty(w * h, np.uint8)
    px[0::2], px[1::2] = raw >> 4, raw & 15
    old = px.reshape(h, w)
    new = old[:, ::-1].T                 # new[v', u'] = old[u', w - 1 - v']
    flat = new.reshape(-1)
    tex[at:at + w * h // 2] = ((flat[0::2] << 4) | flat[1::2]).astype(np.uint8).tobytes()


def turn_course(mdl, tex, wanted):
    """Turns the wanted textures ((texture, size) pairs) that only quads use, and their quads."""
    mdl, tex = bytearray(mdl), bytearray(tex)
    tab, records, blocks = tables(mdl)
    polys = polygons(mdl, blocks)
    clut_end = max(r[1] for r in records) * 8 + 32
    in_triangles = {(records[w // 8][2], records[w // 8][3]) for o, a, w, k in polys
                    if (a >> 5) & 15 == 2 and k == 3 and w // 8 < len(records)}
    turned = set()
    for srca, size in wanted:
        w, h = (size >> 8) * 8, size & 0xFF
        if (srca, size) in in_triangles or h % 8 or not any(r[2] == srca and r[3] == size for r in records):
            continue
        turn_texture(tex, clut_end + srca * 8, w, h)
        turned.add((srca, size))
    turned_records = set()
    for i, r in enumerate(records):
        if (r[2], r[3]) in turned:
            w, h = (r[3] >> 8) * 8, r[3] & 0xFF
            struct.pack_into('>H', mdl, tab + 8 + 8 * i + 6, ((h // 8) << 8) | w)
            turned_records.add(i)
    quads = 0
    for o, attr, word, k in polys:
        if (attr >> 5) & 15 == 2 and k == 4 and word // 8 in turned_records:
            a, b, c, d = struct.unpack_from('>4H', mdl, o + 4)
            struct.pack_into('>4H', mdl, o + 4, b, c, d, a)
            quads += 1
    return bytes(mdl), bytes(tex), len(turned), quads


def main():
    cce, dst = sys.argv[1], sys.argv[2]
    choices = json.load(open(CHOICES))['courses']
    names = []
    for course, wanted in sorted(choices.items()):
        mdl = open(os.path.join(cce, 'DAYTONA', f'COURSE{course}.MDL'), 'rb').read()
        tex = open(os.path.join(cce, 'DAYTONA', f'COURSE{course}.TEX'), 'rb').read()
        mdl, tex, n_tex, n_quads = turn_course(mdl, tex, [tuple(t) for t in wanted])
        os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
        for ext, data in (('MDL', mdl), ('TEX', tex)):
            open(os.path.join(dst, 'DAYTONA', f'COURSE{course}.{ext}'), 'wb').write(data)
            names.append(f'DAYTONA/COURSE{course}.{ext}')
        print(f'turned quads: course {course}, {n_tex} of {len(wanted)} textures listed, {n_quads} quads')
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in names if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))


if __name__ == '__main__':
    main()
