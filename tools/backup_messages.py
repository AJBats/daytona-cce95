"""The backup-memory messages in English.

usage: backup_messages.py <extracted cce> <out dir> [--sheet <png>]

Before the title, BKUP.BIN checks the console's and the cartridge's backup
memory and can show one of 20 messages (docs/backup_messages.md): MESn.DAT,
each a picture of Japanese text, with Yes and No under the questions from
MES_BG.DAT. This draws them in English and writes them to <out dir>/DAYTONA,
listed in PATCHED.txt. --sheet also saves all of them, as drawn, in one
picture.

A picture is 8 x 8 chars of 256 colours (the index is the brightness: the
messages' colours are a grey ramp), then a long holding the chars' size in
bytes, then a map of one word a cell (the char x 2), the box's width in
cells by its height. BKUP.BIN's code holds each message's box size and the
chars' size, so ours keep both: the same box, and the chars padded to the
Japanese picture's count. A line of text is 24 lines tall, one every 40.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = 'C:/Windows/Fonts/segoeui.ttf'
SIZE = 24                 # pixels a em: capitals 17 tall, as the Japanese text's latin letters
LINE, PITCH = 24, 40
SS = 4                    # drawn this many times finer, then averaged
STROKE = 1                # in the finer drawing: a quarter pixel heavier, the Japanese lettering's weight

# By message number: the Japanese box (cells wide, cells tall) and the English.
MESSAGES = {
    1: ((74, 15), ['System Memory is not ready for saving.',
                   'All files in System Memory will be cleared.',
                   'Is that OK?']),
    2: ((72, 8), ['Please clear all files using',
                  'the Sega Saturn\'s Memory Manager.']),
    3: ((54, 3), ['System Memory has been cleared.']),
    4: ((72, 8), ['System Memory could not be cleared.']),
    5: ((72, 18), ['Cartridge Memory is not ready for saving.',
                   'All files in Cartridge Memory will be cleared.',
                   'Is that OK?']),
    6: ((67, 3), ['Cartridge Memory has been cleared.']),
    7: ((72, 8), ['Cartridge Memory could not be cleared.']),
    8: ((72, 8), ['The save in System Memory could not be read.']),
    9: ((72, 13), ['If you start the game now,',
                   'your records will not be saved.',
                   'Start the game?']),
    10: ((72, 28), ['This game needs 64 free blocks to save.',
                    'Please clear other games\' files using the',
                    'Sega Saturn\'s Memory Manager, or use a',
                    'Cartridge Memory with at least 64 free blocks.']),
    11: ((72, 18), ['Cartridge Memory is too full,',
                    'so System Memory will be used.',
                    'Ghosts will not be saved.',
                    'Start the game?']),
    12: ((72, 18), ['If you start the game now,',
                    'your records will not be saved,',
                    'and neither will ghosts.',
                    'Start the game?']),
    13: ((72, 33), ['This game needs 64 free blocks to save,',
                    'and 965 free blocks of Cartridge Memory',
                    'to save ghosts.',
                    'Please clear other games\' files using the',
                    'Sega Saturn\'s Memory Manager,',
                    'or use another Cartridge Memory.']),
    14: ((72, 13), ['If you start the game now,',
                    'ghosts will not be saved.',
                    'Start the game?']),
    15: ((73, 24), ['Saving ghosts needs 965 free blocks',
                    'of Cartridge Memory.',
                    'Please clear other games\' files using the',
                    'Sega Saturn\'s Memory Manager,',
                    'or use another Cartridge Memory.']),
    16: ((72, 8), ['The save in Cartridge Memory could not be read.']),
    17: ((72, 8), ['The saves in System Memory and',
                   'Cartridge Memory could not be read.']),
    18: ((72, 13), ['The save in Cartridge Memory could not be read.',
                    'The save in System Memory will be used.']),
    19: ((73, 13), ['This game\'s files could not be cleared.',
                    'Please clear them using the',
                    'Sega Saturn\'s Memory Manager.']),
    20: ((72, 18), ['This game\'s save could not be read.',
                    'Please clear this game\'s files in',
                    'Cartridge Memory using the',
                    'Sega Saturn\'s Memory Manager.']),
}

# MES_BG.DAT: the two choices under a question, each its own run of map
# cells (from the map's start), the box in cells, and its chars. The
# map and the colours after it stay; only the chars are redrawn.
CHOICES = (('Yes', 0, (7, 3)), ('No', 21, (10, 3)))


def split(data):
    """(chars as n x 8 x 8, map words) of a picture file."""
    at = [m for m in range(64, len(data) - 4, 64) if struct.unpack_from('>I', data, m)[0] == m]
    # the chars' size is the last long that equals its own place and leaves a whole map
    m = at[-1]
    n = (len(data) - m - 4) // 2
    chars = np.frombuffer(data[:m], np.uint8).reshape(-1, 8, 8)
    return chars, list(struct.unpack_from('>%dH' % n, data, m + 4))


def text_picture(lines, w, h):
    """The lines drawn left-aligned, the block centred in the box, a line every 40."""
    font = ImageFont.truetype(FONT, SIZE * SS)
    widths = [(font.getlength(t) + 2 * STROKE) / SS for t in lines]
    block = max(widths)
    tall = LINE + PITCH * (len(lines) - 1)
    if block > w:
        raise ValueError(f'{lines[widths.index(block)]!r} is {block:.0f} wide, the box {w}')
    if tall > h:
        raise ValueError(f'{len(lines)} lines don\'t fit {h} lines')
    # the baseline as low as the descenders allow
    bottom = font.getbbox('gjpqy', anchor='ls', stroke_width=STROKE)[3]
    base = LINE * SS - bottom
    left, top = (w - block) / 2, (h - tall) // 2
    img = Image.new('L', (w * SS, h * SS), 0)
    d = ImageDraw.Draw(img)
    for k, t in enumerate(lines):
        d.text((round(left * SS) + STROKE, (top + PITCH * k) * SS + base), t, font=font, fill=255,
               anchor='ls', stroke_width=STROKE, stroke_fill=255)
    a = np.asarray(img, np.float32).reshape(h, SS, w, SS).mean((1, 3))
    return np.round(a).astype(np.uint8)


def to_chars(img):
    """(chars, map) of a picture: char 0 blank, identical cells share a char."""
    h, w = img.shape[0] // 8, img.shape[1] // 8
    chars = [bytes(64)]
    index = {chars[0]: 0}
    words = []
    for r in range(h):
        for c in range(w):
            cell = img[r * 8:r * 8 + 8, c * 8:c * 8 + 8].tobytes()
            if cell not in index:
                index[cell] = len(chars)
                chars.append(cell)
            words.append(index[cell] * 2)
    return chars, words


def message(jp, lines, box):
    w, h = box
    jp_chars, jp_map = split(jp)
    if len(jp_map) != w * h:
        raise ValueError(f'the Japanese map has {len(jp_map)} cells, not {w} x {h}')
    img = text_picture(lines, w * 8, h * 8)
    chars, words = to_chars(img)
    if len(chars) > len(jp_chars):
        raise ValueError(f'{len(chars)} chars, the Japanese picture {len(jp_chars)}')
    chars += [bytes(64)] * (len(jp_chars) - len(chars))
    size = len(chars) * 64
    return b''.join(chars) + struct.pack('>I', size) + struct.pack('>%dH' % len(words), *words), img


def choices(jp):
    chars, words = split(jp)
    chars = chars.copy()
    size = len(chars) * 64
    # the picked choice's colour bank only has the brightnesses the Japanese choices use
    levels = np.unique(chars)
    pictures = []
    for text, start, (w, h) in CHOICES:
        img = text_picture([text], w * 8, h * 8)
        img = levels[np.abs(img[..., None].astype(int) - levels.astype(int)).argmin(-1)]
        for k in range(w * h):
            r, c = divmod(k, w)
            cell = img[r * 8:r * 8 + 8, c * 8:c * 8 + 8]
            ch = words[start + k] // 2
            if ch:
                chars[ch] = cell
            elif cell.any():
                raise ValueError(f'{text!r} reaches a blank cell of its box')
        pictures.append(img)
    return chars.tobytes() + jp[size:], pictures


def main():
    args = sys.argv[1:]
    sheet = None
    if '--sheet' in args:
        i = args.index('--sheet')
        sheet = args[i + 1]
        del args[i:i + 2]
    src, dst = args
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    names, shown = [], []
    for n, (box, lines) in MESSAGES.items():
        jp = open(os.path.join(src, 'DAYTONA', f'MES{n}.DAT'), 'rb').read()
        try:
            data, img = message(jp, lines, box)
        except ValueError as e:
            sys.exit(f'error: MES{n}.DAT: {e}')
        open(os.path.join(dst, 'DAYTONA', f'MES{n}.DAT'), 'wb').write(data)
        names.append(f'DAYTONA/MES{n}.DAT')
        shown.append((f'MES{n}', img))
    jp = open(os.path.join(src, 'DAYTONA', 'MES_BG.DAT'), 'rb').read()
    try:
        data, imgs = choices(jp)
    except ValueError as e:
        sys.exit(f'error: MES_BG.DAT: {e}')
    open(os.path.join(dst, 'DAYTONA', 'MES_BG.DAT'), 'wb').write(data)
    names.append('DAYTONA/MES_BG.DAT')
    shown += [('MES_BG', img) for img in imgs]

    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in names if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'backup messages: {len(names)} files in English')

    if sheet:
        width = max(img.shape[1] for _, img in shown)
        height = sum(img.shape[0] + 24 for _, img in shown)
        out = Image.new('L', (width, height), 48)
        d = ImageDraw.Draw(out)
        y = 0
        for name, img in shown:
            d.text((2, y + 4), name, fill=200)
            out.paste(Image.fromarray(img), (0, y + 20))
            y += img.shape[0] + 24
        out.save(sheet)


if __name__ == '__main__':
    main()
