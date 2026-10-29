"""Build the cars on DUSA's body as CCE car files: DUSA's Gallop as the
secret car 9's PLCAR09.MDL/.TEX (1P) and PLCAR29.MDL/.TEX (2P, the
low-detail cars), and each '95 livery of a CCE car n (from 1) as a TEX of
its own, PLCAR3n.TEX (1P) and PLCAR5n.TEX (2P), drawn with car 9's MDL.
The Hornet races the Gallop and a '95 car its own paint when DUSA's body is
chosen in car select (patches/car_choice.s); every car's own PLCARn stays
as CCE shipped it for when CCE's is.

usage: car_convert.py <dusa extracted dir> <cce extracted dir> <out dir>
  Reads DUSA's POLYGON.BIN and TEX_PL.BIN and the paints of
  tools/liveries.py; writes the files under <out dir>/DAYTONA and lists
  them in its PATCHED.txt. Each is laid out in and padded to the size of
  the Hornet's file it was first built for (the loader finds the symbol
  trailer from the end of the file); car 9's originals are smaller, so the
  disc builder moves the grown files, and adds the '95 cars' new ones.

DUSA (docs/car_model.md): body model 0 (142 vertices, 132 faces) and the
damaged body, model 13 (136 vertices, 132 faces), in POLYGON.BIN; 4bpp
textures LZSS-compressed in TEX_PL.BIN with the automatic (red/blue)
livery's 16-colour tables at its start. For 2P the body in every slot,
its texture table grown from 38 to 49 entries (the loader relocates as many
as the count says) and its TEX holding only the textures it uses, the
floor panel at a quarter of its size and the grille at a half
(docs/two_player.md).

CCE file layout written here (PLCAR09; PLCAR29 the same with fewer entries,
and no strip):
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
  TEX +0      29 16-colour tables (tools/liveries.py: 2-14 the automatic
              livery, 16-28 the manual), then the pixels; trailer ids 0xB9
              (tables) and 0xBA (pixels)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import liveries  # noqa: E402

BODY = (0x1E24, 142, 0x24CC, 132)       # POLYGON.BIN: vertices, count, faces, count
DAMAGED = (0x4470, 136, 0x4AD0, 132)
ENTRIES = 49                            # texture table: the body's 48 textures and the glass
FLOOR_TEX = 4                           # 64x60, the floor panel only
GRILLE_TEX = 2                          # 64x16, the dark under-nose grille

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
# DUSA's 16-colour table n <- TEX_PL offset (the automatic livery's; the
# manual one's tables 2-7 are at 0x100-0x1A0)
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


def downsample(data, w, h, k):
    """4bpp pixels (two a byte, high nibble first) at 1/k of the width and height."""
    px = [n for b in data[:w * h // 2] for n in (b >> 4, b & 15)]
    w2, h2 = w // k, h // k
    small = [px[(y * k) * w + x * k] for y in range(h2) for x in range(w2)]
    return bytes(small[i] << 4 | small[i + 1] for i in range(0, len(small), 2)), w2, h2


def nibbles(px):
    """4bpp indices (h x w) -> bytes, two pixels a byte, high nibble first."""
    flat = [int(v) for v in px.reshape(-1)]
    return bytes(flat[i] << 4 | flat[i + 1] for i in range(0, len(flat), 2))


def build(poly, paint, models, slots, textures, entry_count, mdl_size, tex_size, strip=False, shrink=None):
    """One car's MDL and TEX: models (POLYGON.BIN specs, file order), slots
    (the six headers' model, in trailer-id order), paint (tools/liveries.py:
    the textures' pixels and the tables), textures ('all', or only those the
    faces use); strip: the window reflection strip after the vertices;
    shrink: {texture id: factor}, stored at that fraction of its size.
    The MDL depends only on which textures and their sizes, so every paint
    gives the same one. -> (mdl, tex, report)"""
    shrink = shrink or {}
    # TEX: tables, then each texture at an 8-byte boundary
    tables = b''.join(struct.pack('>16H', *t) for t in paint.tables)
    meshes = [faces(poly, m) for m in models]
    used = {tid for _, fl in meshes for _, tid, _ in fl}
    pixels = bytearray()
    place = {}
    sizes = {}
    strip_data = b''
    for tid, (off, w, h, table) in sorted(TEXTURES.items()):
        if textures != 'all' and tid not in used:
            continue
        size = w * h // 2
        data = nibbles(paint.pixels[tid])
        if tid == WINDOW_TEX and strip:
            strip_data = data
        if tid in shrink:
            data, w, h = downsample(data, w, h, shrink[tid])
            size = w * h // 2
        sizes[tid] = (w, h)
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

    polys = []
    for _, flist in meshes:
        out = bytearray()
        for attr, tid, idx in flist:
            transparent = (attr >> 4) & 1
            e = entry(tid, transparent)
            direction = (0, 2, 1, 3)[(attr >> 6) & 3]
            cattr = 0x40 | (SORT[attr & 7] << 1) | (0 if attr & 8 else 0x10) | (direction << 12)
            v0, v1, v2, v3 = idx
            out += struct.pack('>6H', cattr, 8 * e, 16 * v0, 16 * v1, 16 * v2, 16 * v3)
        polys.append(out)
    if len(order) + 1 > entry_count:
        sys.exit(f'{len(order)} textures and the glass entry need more than {entry_count} entries')

    table = bytearray(struct.pack('>HHHH', entry_count, 0, 0, 0))
    by_index = {i: k for k, i in entries.items()}
    for i in range(entry_count):
        if i in by_index:
            tid, transparent = by_index[i]
            tnum = liveries.table_of(tid)
            w, h = sizes[tid]
            table += struct.pack('>4H', 0x1488 if transparent else 0x14C8, 4 * tnum, place[tid],
                                 (w // 8) << 8 | h)
        else:
            table += struct.pack('>4H', 0x14C8, 0, 0, 0x0108)

    def vblock(verts):
        return b''.join(struct.pack('>3h', *(round(c / 64) for c in v)) for v in verts)

    headers_at = len(table)
    polys_at = [headers_at + 6 * 20]
    for p in polys[:-1]:
        polys_at.append(polys_at[-1] + len(p))
    verts_at = [polys_at[-1] + len(polys[-1])]
    for v, _ in meshes[:-1]:
        verts_at.append(verts_at[-1] + 6 * len(v))
    strip_at = verts_at[-1] + 6 * len(meshes[-1][0])
    # trailer ids 0x29..0x2E name the headers in file order; CCE's damage
    # states take 0x2C (undamaged), 0x2A, 0x2B, 0x29; 0x2D/0x2E are the
    # low-detail slots
    out_blocks = b''
    for k, m in enumerate(slots):
        h = headers_at + 20 * k
        v, f = meshes[m]
        out_blocks += struct.pack('>HHiiii', len(v), len(f), verts_at[m] - h, polys_at[m] - h, -h, 0)
    mdl = table + out_blocks + b''.join(polys) + b''.join(vblock(v) for v, _ in meshes) + strip_data
    used_bytes = len(mdl)
    trailer_at = mdl_size - 8 * len(TRAILER_IDS) - 4
    if trailer_at < len(mdl):
        sys.exit(f'the MDL needs {len(mdl) - trailer_at} more bytes than the original')
    mdl += bytes(trailer_at - len(mdl))
    targets = [0, 8 + 8 * GLASS_ENTRY] + [headers_at + 20 * k for k in range(6)]
    for sid, t in zip(TRAILER_IDS, targets):
        mdl += struct.pack('>Ii', sid, t - trailer_at)
    mdl += struct.pack('>I', len(TRAILER_IDS))

    tex = tables + pixels
    tex_trailer = tex_size - 2 * 8 - 4
    if len(tex) > tex_trailer:
        sys.exit(f'the TEX is {len(tex) - tex_trailer} bytes too big')
    tex += bytes(tex_trailer - len(tex))
    tex += struct.pack('>IiIiI', 0xB9, -tex_trailer, 0xBA, len(tables) - tex_trailer, 2)
    report = (f'MDL {used_bytes} bytes used of {mdl_size} ({len(order)} textures), '
              f'TEX {len(tables) + len(pixels)} of {tex_size}; window texture entry {entries.get((WINDOW_TEX, 0))}'
              + (f', strip at +0x{strip_at:X}' if strip else ''))
    return mdl, tex, report


def check_bodies(choice_s='patches/car_choice.s'):
    """patches/car_choice.s's table of bodies has a choice (1) for the
    Hornet and exactly the cars given a '95 paint."""
    text = open(choice_s).read()
    words = text[text.index('\nbodies:'):].split('\n.org')[0]
    table = b''.join(int(w, 16).to_bytes(2, 'big') for w in
                     (line.split()[1] for line in words.splitlines() if line.strip().startswith('.word')))
    chosen = {car + 1 for car, kind in enumerate(table) if kind == 1}
    if chosen != {1} | set(liveries.NINETY_FIVE):
        sys.exit(f'{choice_s}: cars {sorted(chosen)} have a choice of body, '
                 f'tools/liveries.py paints {sorted(liveries.NINETY_FIVE)} and the Hornet')


def main():
    src, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    check_bodies()
    poly = open(os.path.join(src, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(src, 'TEX_PL.BIN'), 'rb').read()
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    names = []
    paints = [(9, liveries.gallop(texpl))]
    sources = liveries.Sources(src, cce)
    paints += [(30 + car, f(sources)) for car, f in liveries.NINETY_FIVE.items()]
    # 1P: the body, and the damaged body in damage states 1-3
    # 2P: the body in every slot; its floor panel at a quarter size and the
    # grille at a half to fit
    # each padded to the size of the Hornet's file of its kind; every
    # paint gives the same MDL, so only the Gallop's is written
    for base, sized_as, models, slots, textures, strip, shrink in (
            (0, 'PLCAR01', (BODY, DAMAGED), (1, 1, 1, 0, 0, 0), 'all', True, None),
            (20, 'PLCAR21', (BODY,), (0, 0, 0, 0, 0, 0), 'used', False, {FLOOR_TEX: 4, GRILLE_TEX: 2})):
        orig = open(os.path.join(cce, 'DAYTONA', sized_as + '.MDL'), 'rb').read()
        gallop_mdl = None
        for number, paint in paints:
            name = f'PLCAR{base + number:02d}'
            mdl, tex, report = build(poly, paint, models, slots, textures,
                                     max(struct.unpack_from('>H', orig, 0)[0], ENTRIES), len(orig),
                                     os.path.getsize(os.path.join(cce, 'DAYTONA', sized_as + '.TEX')), strip, shrink)
            files = [('TEX', tex)]
            if gallop_mdl is None:
                gallop_mdl = mdl
                files.append(('MDL', mdl))
            elif mdl != gallop_mdl:
                sys.exit(f"{name}: its MDL differs from the Gallop's")
            for ext, data in files:
                open(os.path.join(dst, 'DAYTONA', f'{name}.{ext}'), 'wb').write(data)
                names.append(f'DAYTONA/{name}.{ext}')
            print(f'{name} ({paint.name}): {report}')
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in names if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))


if __name__ == '__main__':
    main()
