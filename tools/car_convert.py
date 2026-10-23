"""Build CCE's player car files (PLCAR01.MDL/.TEX) from DUSA's Gallop.

usage: car_convert.py <dusa extracted dir> <cce extracted dir> <out dir>
  Reads DUSA's POLYGON.BIN and TEX_PL.BIN; writes DAYTONA/PLCAR01.MDL and
  .TEX under <out dir> and lists them in its PATCHED.txt. Both are padded to
  the original files' sizes: the disc keeps the original directory entries,
  so the game reads that many bytes, and the loader finds the symbol
  trailer from the end of the file.

DUSA (docs/car_model.md): body model 0 (142 vertices, 132 faces) and the
damaged body, model 13 (136 vertices, 132 faces), in POLYGON.BIN; 4bpp
textures LZSS-compressed in TEX_PL.BIN with the automatic (red/blue)
livery's 16-colour tables at its start.

CCE file layout written here:
  MDL +0      texture table: count (65), 3 zero words, 65 x 8-byte entries
              (CMDPMOD, table offset / 8, pixel offset / 8, CMDSIZE);
              entry 9 is left for the loader's glass texture
  MDL +0x210  six model headers (vertex count, polygon count, offsets from
              the header to vertices, polygons and the texture table): four
              damage states (0 = DUSA body, 1-3 = DUSA damaged body) and two
              low-detail slots (DUSA body), in the loader's id order
              polygons and vertices of both DUSA models
              window reflection strip (80 x 80 4bpp)
              symbol trailer read by the loader: (id, offset from the
              trailer start) x 8, then the count
  TEX +0      64 16-colour tables, +0x800 pixels; trailer ids 0xB9 (tables)
              and 0xBA (pixels)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dusa_lzss import decompress  # noqa: E402

BODY = (0x1E24, 142, 0x24CC, 132)       # POLYGON.BIN: vertices, count, faces, count
DAMAGED = (0x4470, 136, 0x4AD0, 132)

# DUSA texture id -> (TEX_PL offset, width, height, 16-colour table)
TEXTURES = {
    1: (0x299B, 8, 8, 0), 2: (0x29A3, 64, 16, 0), 3: (0x2A53, 40, 18, 0),
    4: (0x2B27, 64, 60, 0), 5: (0x2E73, 40, 25, 0), 6: (0x2F93, 64, 15, 0),
    10: (0x3457, 80, 40, 15),           # rear/side windows: the reflection strip
    16: (0x0640, 16, 40, 2), 17: (0x06AC, 32, 40, 2), 18: (0x074C, 32, 24, 2),
    19: (0x07E4, 64, 32, 2), 20: (0x09B4, 40, 24, 2), 21: (0x0A34, 40, 24, 2),
    22: (0x0AA4, 40, 8, 3), 23: (0x0AD8, 104, 16, 2), 24: (0x0C14, 32, 28, 7),
    25: (0x0D7C, 24, 72, 4), 26: (0x0F58, 24, 72, 4), 27: (0x1140, 24, 72, 4),
    28: (0x12F8, 48, 48, 7), 29: (0x1484, 80, 40, 4), 30: (0x1890, 96, 8, 6),
    31: (0x1908, 96, 16, 6), 32: (0x1AC4, 24, 8, 3), 33: (0x1B04, 32, 16, 3),
    34: (0x1B9C, 24, 8, 3), 35: (0x1BC8, 24, 8, 3), 36: (0x1C04, 32, 16, 3),
    37: (0x1CC8, 48, 12, 5), 38: (0x1D2C, 48, 12, 5), 39: (0x1D84, 48, 16, 3),
    40: (0x1E20, 40, 16, 5), 41: (0x1E8C, 24, 16, 5), 42: (0x1EFC, 72, 12, 5),
    43: (0x1FC8, 64, 12, 5), 44: (0x2060, 8, 16, 3), 45: (0x2080, 8, 16, 3),
    46: (0x20A0, 40, 16, 5), 47: (0x211C, 24, 16, 5), 48: (0x2194, 72, 12, 5),
    49: (0x225C, 64, 12, 5), 50: (0x22F4, 8, 8, 5), 51: (0x22FC, 8, 8, 5),
    52: (0x2304, 8, 8, 5), 53: (0x230C, 8, 8, 5), 54: (0x2314, 8, 8, 4),
    55: (0x231C, 8, 8, 7), 56: (0x2324, 8, 8, 2), 57: (0x232C, 8, 8, 4),
}
# CCE 16-colour table n <- TEX_PL offset (automatic livery)
TABLES = {0: 0x000, 1: 0x020, 2: 0x040, 3: 0x060, 4: 0x080, 5: 0x0A0, 6: 0x0C0,
          7: 0x0E0, 14: 0x1C0, 15: 0x1E0}
WINDOW_TEX = 10
GLASS_ENTRY = 9           # the loader overwrites this entry with CCE's glass
SORT = {0: 0, 1: 1, 2: 2, 3: 3, 4: 3}   # DUSA depth-sort mode -> CCE's
TRAILER_IDS = (0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E)


def faces(poly, model):
    vo, nv, fo, nf = model
    verts = [struct.unpack_from('>iii', poly, vo + 12 * i) for i in range(nv)]
    out = []
    for i in range(nf):
        f = struct.unpack_from('>iiiHHHHHH', poly, fo + 24 * i)
        out.append((f[3], f[4], f[5:9]))
    return verts, out


def main():
    src, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    mdl_size = os.path.getsize(os.path.join(cce, 'DAYTONA', 'PLCAR01.MDL'))
    tex_size = os.path.getsize(os.path.join(cce, 'DAYTONA', 'PLCAR01.TEX'))
    poly = open(os.path.join(src, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(src, 'TEX_PL.BIN'), 'rb').read()

    # TEX: tables, then each texture at an 8-byte boundary
    tables = bytearray(0x800)
    for n, off in TABLES.items():
        tables[32 * n:32 * n + 32] = texpl[off:off + 32]
    pixels = bytearray()
    place = {}
    strip = None
    for tid, (off, w, h, table) in sorted(TEXTURES.items()):
        size = w * h // 2
        data, _ = decompress(texpl, off, 80 * 80 // 2 if tid == WINDOW_TEX else size)
        if tid == WINDOW_TEX:
            strip = data
        place[tid] = len(pixels) // 8
        pixels += data[:size] + bytes(-size % 8)

    # texture table entries, one per (texture, transparency) used
    entries = {}
    order = []

    def entry(tid, transparent):
        key = (tid, transparent)
        if key not in entries:
            index = len(order) + (1 if len(order) >= GLASS_ENTRY else 0)
            entries[key] = index
            order.append(key)
        return entries[key]

    vb, fb = faces(poly, BODY)
    vd, fd = faces(poly, DAMAGED)
    polys = []
    for flist in (fb, fd):
        out = bytearray()
        for attr, tid, idx in flist:
            transparent = (attr >> 4) & 1
            e = entry(tid, transparent)
            direction = (0, 2, 1, 3)[(attr >> 6) & 3]
            cattr = 0x40 | (SORT[attr & 7] << 1) | (0 if attr & 8 else 0x10) | (direction << 12)
            v0, v1, v2, v3 = idx
            out += struct.pack('>6H', cattr, 8 * e, 16 * v0, 16 * v1, 16 * v2, 16 * v3)
        polys.append(out)

    table = bytearray(struct.pack('>HHHH', 65, 0, 0, 0))
    by_index = {i: k for k, i in entries.items()}
    for i in range(65):
        if i in by_index:
            tid, transparent = by_index[i]
            off, w, h, tnum = TEXTURES[tid]
            table += struct.pack('>4H', 0x1488 if transparent else 0x14C8, 4 * tnum, place[tid],
                                 (w // 8) << 8 | h)
        else:
            table += struct.pack('>4H', 0x14C8, 0, 0, 0x0108)

    def vblock(verts):
        return b''.join(struct.pack('>3h', *(round(c / 64) for c in v)) for v in verts)

    headers_at = len(table)
    body_polys = headers_at + 6 * 20
    dmg_polys = body_polys + len(polys[0])
    body_verts = dmg_polys + len(polys[1])
    dmg_verts = body_verts + 6 * len(vb)
    strip_at = dmg_verts + 6 * len(vd)
    trailer_at = strip_at + len(strip)
    # trailer ids 0x29..0x2E name the headers in file order; CCE's damage
    # states take 0x2C (undamaged), 0x2A, 0x2B, 0x29; 0x2D/0x2E are the
    # low-detail slots
    body = (len(vb), len(fb), body_verts, body_polys)
    damaged = (len(vd), len(fd), dmg_verts, dmg_polys)
    out_blocks = b''
    for k, (nv, np_, vo, po) in enumerate((damaged, damaged, damaged, body, body, body)):
        h = headers_at + 20 * k
        out_blocks += struct.pack('>HHiiii', nv, np_, vo - h, po - h, -h, 0)
    mdl = table + out_blocks + polys[0] + polys[1] + vblock(vb) + vblock(vd) + strip
    assert len(mdl) == trailer_at
    trailer_at = mdl_size - 8 * len(TRAILER_IDS) - 4
    if trailer_at < len(mdl):
        sys.exit(f'PLCAR01.MDL needs {len(mdl) - trailer_at} more bytes than the original')
    mdl += bytes(trailer_at - len(mdl))
    targets = [0, 8 + 8 * GLASS_ENTRY] + [headers_at + 20 * k for k in range(6)]
    for sid, t in zip(TRAILER_IDS, targets):
        mdl += struct.pack('>Ii', sid, t - trailer_at)
    mdl += struct.pack('>I', len(TRAILER_IDS))

    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'PLCAR01.MDL'), 'wb').write(mdl)
    tex = tables + pixels
    tex_trailer = tex_size - 2 * 8 - 4
    if len(tex) > tex_trailer:
        sys.exit(f'PLCAR01.TEX is {len(tex) - tex_trailer} bytes too big')
    tex += bytes(tex_trailer - len(tex))
    tex += struct.pack('>IiIiI', 0xB9, -tex_trailer, 0xBA, 0x800 - tex_trailer, 2)
    open(os.path.join(dst, 'DAYTONA', 'PLCAR01.TEX'), 'wb').write(tex)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    for name in ('DAYTONA/PLCAR01.MDL', 'DAYTONA/PLCAR01.TEX'):
        if name not in have:
            have.append(name)
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'PLCAR01.MDL {trailer_at} bytes used of {mdl_size} ({len(order)} textures), PLCAR01.TEX {len(tables) + len(pixels)} bytes; '
          f'window texture entry {entries.get((WINDOW_TEX, 0))}, strip at +0x{strip_at:X}')


if __name__ == '__main__':
    main()
