"""Put DUSA's title and the attract's scene code into CCE's attract: write
DAYTONA/DEMOTTL.BIN.

usage: title_convert.py <dusa extracted dir> <cce extracted dir> <out dir> <attract.bin> <cars.blk>
  Reads DUSA's SCROLL.BIN and APROG.BIN, and the scene code and cars
  tools/build_attract.py built; writes DEMOTTL.BIN under <out dir>/DAYTONA,
  at least the original's size, and lists it in PATCHED.txt.

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
  LWRAM ..2DC000 DUSA's demo cars for the scene code, a piece per course
                (cars.blk, which names its own address)
With the cars the file outgrows the original (tools/mkdisc.py moves it).

Options > Sound > ATTRACT plays this attract (ORIGINAL) or CCE's own (CCE),
so the file holds both, each a block file as above (patches/attract_load.s
reads only the chosen one into work RAM at 0x220000 and copies its blocks
out, so each must end before any block it carries begins):
  sectors 0-55  CCE's attract: CCE's own blocks but its CIRCUIT EDITION
                title's (VRAM 0x40040, LWRAM 2E2780, CRAM 0x600), DUSA's
                title as above in their place, and blocks that put back in
                RACE.BIN its song, its demo's tick and the tick its title
                comes at. The choice is the attract's music and camera:
                either ends on DUSA's title (the user, 2026-10-30).
  sector 56-    ours, and blocks that put our attract's RACE.BIN back.
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
LOAD = 0x00220000                   # where the race start reads the file
N_CHARS = 600                       # patches/title.s: chars and map sizes
MAP_BYTES = 64 * 2 * H
CCE_SECTORS = 56                    # patches/attract_load.s: CCE's half
RACE_AT = 0x06028000
SWITCH = [(0x060294E8, 4),          # the attract's song: track 32 (DUSA's) or 18
          (0x060285AC, 4),          # the demo's tick: src/attract.c's or CCE's (06031DFA)
          (0x06031EB4, 8),          # the title's tick and timeout
          (0x06031ED8, 4),          # CCE's title routines: start (crossfade),
          (0x06031EF8, 4),          # still title,
          (0x06031F04, 4)]          # Press Start's blink
CCE_TITLE_BLOCKS = (STAGE, CODE, CRAM)  # CCE's CIRCUIT EDITION title: chars, map, palettes
CCE_SWITCH = [(0x060294E8, 4),      # CCE's attract: its song (track 18),
              (0x060285AC, 4),      # its demo's tick (06031DFA),
              (0x06031EB4, 4)]      # and its title at its tick 0x906 (77 s, 06031EB6)


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


def block_file(blocks):
    out = struct.pack('>I', len(blocks)) + b''.join(struct.pack('>II', len(b), a) for b, a in blocks)
    out += b''.join(b for b, _ in blocks)
    for b, a in blocks:
        assert b and len(b) % 4 == 0
        assert not LOAD <= a < LOAD + len(out), f'DEMOTTL.BIN, read at {LOAD:08X}, runs into its block at {a:08X}'
    return out


def race_bytes(race, at, n):
    return race[at - RACE_AT:at - RACE_AT + n]


def cce_half(original, vanilla, title):
    """CCE's attract: CCE's own blocks but its title's (CCE_TITLE_BLOCKS), DUSA's
    title (blocks title) in their place, which shows after either attract,
    and blocks that put CCE's song, demo tick and the tick its title comes
    at back in RACE.BIN."""
    count = struct.unpack_from('>I', original, 0)[0]
    pairs = [struct.unpack_from('>II', original, 4 + 8 * k) for k in range(count)]
    blocks, at = list(title), 4 + 8 * count
    for size, addr in pairs:
        if addr not in CCE_TITLE_BLOCKS:
            blocks.append((original[at:at + size], addr))
        at += size
    for addr, n in CCE_SWITCH:
        blocks.append((race_bytes(vanilla, addr, n), addr))
    out = block_file(blocks)
    assert len(out) <= CCE_SECTORS * 2048, f"CCE's half is {len(out)} bytes, more than {CCE_SECTORS} sectors"
    return out + bytes(CCE_SECTORS * 2048 - len(out))


def title_blocks(scroll, aprog):
    """DUSA's title, staged for patches/title.s: chars and maps in VRAM, palettes in CRAM."""
    chars, _ = decompress(scroll, CHARS_AT)
    assert len(chars) == 556 * 32 and chars[:32] == bytes(32)
    font, _ = decompress(scroll, FONT_AT)
    ps = font[(PS_FIRST - FONT_FIRST) * 32:(PS_FIRST - FONT_FIRST + PS_CHARS) * 32]
    stage = chars + ps + title_map(scroll, BG_AT, 1) + title_map(scroll, LOGO_AT, 0)
    assert len(stage) == N_CHARS * 32 + 2 * MAP_BYTES
    pals = bytearray(0x200)
    for n, off in PALETTES.items():
        pals[(n - 48) * 32:(n - 47) * 32] = aprog[off:off + 32]
    return [(stage, STAGE), (bytes(pals), CRAM)]


def build(title, code, cars, ours):
    code += bytes(-len(code) % 4)
    cars_at = struct.unpack_from('>I', cars, 0)[0]
    cars = cars[4:] + bytes(-len(cars[4:]) % 4)
    blocks = title + [(code, CODE), (cars, cars_at)]
    blocks += [(race_bytes(ours, addr, n), addr) for addr, n in SWITCH]
    return block_file(blocks)


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    scroll = open(os.path.join(dusa, 'SCROLL.BIN'), 'rb').read()
    aprog = open(os.path.join(dusa, 'APROG.BIN'), 'rb').read()
    code = open(sys.argv[4], 'rb').read()
    cars = open(sys.argv[5], 'rb').read()
    original = open(os.path.join(cce, 'DAYTONA', 'DEMOTTL.BIN'), 'rb').read()
    size = len(original)
    vanilla = open(os.path.join(cce, 'DAYTONA', 'RACE.BIN'), 'rb').read()
    ours = open(os.path.join(dst, 'DAYTONA', 'RACE.BIN'), 'rb').read()
    title = title_blocks(scroll, aprog)
    data = cce_half(original, vanilla, title) + build(title, code, cars, ours)
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'DEMOTTL.BIN'), 'wb').write(data + bytes(max(0, size - len(data))))
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in ['DAYTONA/DEMOTTL.BIN'] if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'title: DUSA\'s chars ({N_CHARS}), background and logo maps, 3 palettes, the scene code and cars; '
          f'DEMOTTL.BIN {len(data)} bytes (CCE\'s attract in its first {CCE_SECTORS} sectors)')


if __name__ == '__main__':
    main()
