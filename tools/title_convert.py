"""Put DUSA's title and the attract's scene code into CCE's attract: write
DAYTONA/DEMOTTL.BIN.

usage: title_convert.py <dusa extracted dir> <cce extracted dir> <out dir> <attract.bin> <cars.blk>
  Reads DUSA's SCROLL.BIN and APROG.BIN, and the scene code and cars
  tools/build_attract.py built; writes DEMOTTL.BIN under <out dir>/DAYTONA,
  padded to the original's size, and lists it in PATCHED.txt.

DUSA (docs/attract.md): the title is two 16-colour layers of 8x8 cells.
NBG2 is the white striped background with a pale ghost of the logo,
NBG3 the black logo and PRESS START BUTTON. In SCROLL.BIN, LZSS streams
(tools/dusa_lzss.py): at 0x400 the title's 556 chars (VRAM 0x17700, char
0xBB8 on, the first one blank), at 0x7643 a font (VRAM 0x14F80) whose
chars 0xAC7-0xAF2 are PRESS START BUTTON as 22 x 2 cells, at 0x8F84 the
logo map and at 0x9374 the background map (each 44 x 28 after a width,
height header). The palettes are in APROG.BIN (loaded at 06003000): the
logo's at +0x4542C (CRAM palette 48), the background's at +0x4544C
(palette 1), PRESS START's at +0x458CC (palette 53).

CCE's attract loads DEMOTTL.BIN at its start: a count, then (size,
address) pairs, then the blocks, copied to their addresses. Its own
blocks are its CIRCUIT EDITION title, in VRAM, CRAM and work RAM that
the demo leaves alone. Written here, for patches/title.s:
  VRAM 0x40040  staging: 600 chars (the 556, then PRESS START's 44), the
                background map and the logo map, rows of 64 cells x 28,
                blank past column 44; char 0 is blank. title_start copies
                them to VRAM 0, 0x5E000 and 0x7C000.
  CRAM 0x600    palettes 48-63: 48 the logo, 49 the background, 53 PRESS
                START (NBG2 and NBG3 add palette 48 to the map's)
  LWRAM 2E2780  the scene code (src/attract.c), where CCE kept its title's
                map
  VRAM 0x47000  DUSA's demo cars for the scene code (cars.blk, which
                names its own address), where CCE's title went on
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dusa_lzss import decompress  # noqa: E402

CHARS_AT, FONT_AT, LOGO_AT, BG_AT = 0x400, 0x7643, 0x8F84, 0x9374
FIRST_CHAR = 0xBB8                  # the title chars' first char number
PS_FIRST, PS_CHARS = 0xAC7, 44      # PRESS START BUTTON in the font
FONT_FIRST = 0xA7C                  # the font's first char number
PALETTES = {48: 0x4542C, 49: 0x4544C, 53: 0x458CC}   # CRAM palette: APROG offset
W, H = 44, 28
STAGE, CRAM, CODE = 0x25E40040, 0x25F00600, 0x002E2780
N_CHARS = 600                       # patches/title.s: chars and map sizes
MAP_BYTES = 64 * 2 * H


def title_map(scroll, at, palette):
    data, _ = decompress(scroll, at)
    w, h = struct.unpack_from('>HH', data)
    assert (w, h) == (W, H), (w, h)
    cells = struct.unpack_from(f'>{W * H}H', data, 4)
    out = bytearray(MAP_BYTES)
    for r in range(H):
        for c in range(W):
            v = cells[r * W + c]
            assert v >> 12 == 0 and FIRST_CHAR <= v < FIRST_CHAR + 556, hex(v)
            struct.pack_into('>H', out, r * 128 + c * 2, palette << 12 | v - FIRST_CHAR)
    return bytes(out)


def build(scroll, aprog, code, cars):
    chars, _ = decompress(scroll, CHARS_AT)
    assert len(chars) == 556 * 32 and chars[:32] == bytes(32)
    font, _ = decompress(scroll, FONT_AT)
    ps = font[(PS_FIRST - FONT_FIRST) * 32:(PS_FIRST - FONT_FIRST + PS_CHARS) * 32]
    stage = chars + ps + title_map(scroll, BG_AT, 1) + title_map(scroll, LOGO_AT, 0)
    assert len(stage) == N_CHARS * 32 + 2 * MAP_BYTES
    pals = bytearray(0x200)
    for n, off in PALETTES.items():
        pals[(n - 48) * 32:(n - 47) * 32] = aprog[off:off + 32]
    code += bytes(-len(code) % 4)
    cars_at = struct.unpack_from('>I', cars, 0)[0]
    cars = cars[4:] + bytes(-len(cars[4:]) % 4)
    assert STAGE + len(stage) <= cars_at
    blocks = [(stage, STAGE), (bytes(pals), CRAM), (code, CODE), (cars, cars_at)]
    out = struct.pack('>I', len(blocks)) + b''.join(struct.pack('>II', len(b), a) for b, a in blocks)
    return out + b''.join(b for b, _ in blocks)


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    scroll = open(os.path.join(dusa, 'SCROLL.BIN'), 'rb').read()
    aprog = open(os.path.join(dusa, 'APROG.BIN'), 'rb').read()
    code = open(sys.argv[4], 'rb').read()
    cars = open(sys.argv[5], 'rb').read()
    size = os.path.getsize(os.path.join(cce, 'DAYTONA', 'DEMOTTL.BIN'))
    data = build(scroll, aprog, code, cars)
    assert len(data) <= size
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'DEMOTTL.BIN'), 'wb').write(data + bytes(size - len(data)))
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in ['DAYTONA/DEMOTTL.BIN'] if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'title: DUSA\'s chars ({N_CHARS}), background and logo maps, 3 palettes, the scene code and cars; '
          f'DEMOTTL.BIN {len(data)} of {size} bytes')


if __name__ == '__main__':
    main()
