"""DUSA's title on the main menu's press-start page: write DAYTONA/TITLED.BIN
with src/menu_title.c's blob after CCE's own (docs/attract.md, "The menu's
press-start page").

usage: menu_title.py <dusa extracted dir> <cce extracted dir> <out dir>
  Reads DUSA's title from SCROLL.BIN and APROG.BIN (as tools/title_convert.py
  does: the 556 title chars and PRESS START BUTTON's 44, the background and
  logo maps, 44 x 28, and the three palettes), writes them as
  <out dir>/../menu_title/menu_title_data.h, compiles and links
  src/menu_title.c at LWRAM 0x00242300 (src/menu_title.ld) with tools/sh-gcc,
  and appends the blob to CCE's TITLED.BIN, which the menu reads whole to
  0x220000 when it starts (SLCT 06028194): CCE's file ends at 0x2422EC, and
  the blob must end before 0x250000, where the menu reads its other screens.
  patches/menu_title.s points the menu at the blob's entries.
"""
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import title_convert as tc  # noqa: E402
from dusa_lzss import decompress  # noqa: E402

LOAD, BLOB, LIMIT = 0x00220000, 0x00242300, 0x00250000
GCC = os.path.join(os.path.dirname(__file__), 'sh-gcc', 'bin')
PALETTES = (48, 49, 53)         # DUSA's palettes: the logo's, the background's, PRESS START's


def dusa_title(dusa):
    """DUSA's title: chars (600 x 32 bytes), background and logo maps (44 x 28
    cells, palette - 48 in bits 12-15) and the three palettes (16 words each)."""
    scroll = open(os.path.join(dusa, 'SCROLL.BIN'), 'rb').read()
    aprog = open(os.path.join(dusa, 'APROG.BIN'), 'rb').read()
    chars, _ = decompress(scroll, tc.CHARS_AT)
    font, _ = decompress(scroll, tc.FONT_AT)
    chars = chars + font[(tc.PS_FIRST - tc.FONT_FIRST) * 32:(tc.PS_FIRST - tc.FONT_FIRST + tc.PS_CHARS) * 32]
    assert len(chars) == tc.N_CHARS * 32

    def cells(at, palette):
        m = tc.title_map(scroll, at, palette)
        return [struct.unpack_from('>H', m, r * 128 + c * 2)[0] for r in range(tc.H) for c in range(tc.W)]
    pals = b''.join(aprog[tc.PALETTES[n]:tc.PALETTES[n] + 32] for n in PALETTES)
    return chars, cells(tc.BG_AT, 1), cells(tc.LOGO_AT, 0), struct.unpack('>48H', pals)


def header(chars, bg, logo, pals):
    def arr(kind, name, values, per=16):
        rows = [', '.join(f'{v:#x}' for v in values[i:i + per]) for i in range(0, len(values), per)]
        return f'static const {kind} {name}[{len(values)}] = {{\n    ' + ',\n    '.join(rows) + '\n};\n'
    return (f'#define N_CHARS {tc.N_CHARS}\n#define W {tc.W}\n#define H {tc.H}\n'
            + arr('unsigned char', 'chars', list(chars))
            + arr('unsigned short', 'bg_map', bg) + arr('unsigned short', 'logo_map', logo)
            + arr('unsigned short', 'palettes', list(pals)))


def build(dusa, work):
    os.makedirs(work, exist_ok=True)
    open(os.path.join(work, 'menu_title_data.h'), 'w').write(header(*dusa_title(dusa)))
    env = dict(os.environ, PATH=GCC + os.pathsep + os.environ['PATH'])
    src = os.path.join(os.path.dirname(__file__), '..', 'src', 'menu_title.c')
    elf = os.path.join(work, 'menu_title.elf')
    out = os.path.join(work, 'menu_title.bin')
    run = lambda *cmd: subprocess.run(cmd, env=env, check=True)
    run(os.path.join(GCC, 'sh2eb-elf-gcc'), '-m2', '-mb', '-O2', '-fomit-frame-pointer', '-ffreestanding',
        '-nostdlib', '-I', work, '-T', src[:-2] + '.ld', '-Wl,-e,_entries', '-Wl,--no-warn-rwx-segments',
        '-o', elf, src, '-lgcc')
    run(os.path.join(GCC, 'sh2eb-elf-objcopy'), '-O', 'binary', elf, out)
    return open(out, 'rb').read()


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    titled = open(os.path.join(cce, 'DAYTONA', 'TITLED.BIN'), 'rb').read()
    assert LOAD + len(titled) <= BLOB
    blob = build(dusa, os.path.join(dst, '..', 'menu_title'))
    assert BLOB + len(blob) <= LIMIT, f'the blob runs to {BLOB + len(blob):08X}, past {LIMIT:08X}'
    data = titled + bytes(BLOB - LOAD - len(titled)) + blob
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'TITLED.BIN'), 'wb').write(data)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in ['DAYTONA/TITLED.BIN'] if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'menu title: DUSA\'s title on the press-start page, {len(blob)} bytes at {BLOB:08X} '
          f'(room to {LIMIT:08X}); TITLED.BIN {len(data)} bytes (the original {len(titled)})')


if __name__ == '__main__':
    main()
