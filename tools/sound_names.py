"""The Sound page's new name pictures, in CCE's own lettering: DUSA's titles
for the '95 jingles and David Goes To Victory Lane (docs/music.md, "The
sound test"). tools/options_sound.py puts them on the page.

CCE's 30 names are pictures (OPT.DAT's Sound chars, 3 cells high): yellow
ink, palette 1-7, on a dark plate. They were drawn in two styles: the remix
names and Lack of Speed on a plain plate (A, D, E, F), the arcade originals
and the rest with a graded edge (8 to F). The new names are put together
from them:

- The letters are cut from names whose darkest ink (1-3, or 1-5 for The
  Noisy Roars of Wilderness) falls into exactly as many column runs as the
  name has letters: each letter's own ink only, the ink joined to its run.
  Let's Go Away gives the apostrophe, G and w by hand.
- Five letters CCE never shows are made from others: I from High's H, its
  left stem and serifs; V from DAYTONA's A upside down, its bar out, with
  the lowercase v's point, mirrored so the heavy stroke is on the left; F
  drawn on Pounding's P; ! an l cut short over an i's dot; ? an S's top half
  mirrored over a stem and the dot.
- Spacing as CCE's plain names have it: one empty column between letters,
  five between words, seven before a bracket.
- The plate is CCE's own way of drawing it: for every pixel that isn't ink,
  the ink around it (which neighbours are ink, in a 7x7, 5x5 and 3x3
  window) and the value CCE gave each such pixel in its plain-style names
  are counted; a new pixel takes the value of the widest window seen at
  least twice, else the value most often at its nearest ink's offset.
  Rebuilding Lack of Speed from its own ink this way (the rules learnt
  without it) gives 76% of its plate pixels as CCE drew them, against 52%
  for a uniform band round the ink.
"""
import struct
from collections import Counter

import numpy as np

OPT_AT = 0x250000
SOUND_CHARS = 0x1C8FA
SLCT_AT, NAMES = 0x06028000, 0x0603F860

TEXT = ["The King of Speed (remix)", "Let's Go Away (remix)", "Sky High (remix)", "The Noisy Roars of Wilderness",
        "Pounding Pavement (remix)", "DAYTONA USA Medley", "The King of Speed(original)", "Let's Go Away(original)",
        "Sky High(original)", "The King of Speed (goal)", "Let's Go Away (goal)", "Sky High (goal)",
        "The Noisy Roars of Wilderness(goal)", "Pounding Pavement (goal)", "The King of Speed(goal-original)",
        "Let's Go Away(goal-original)", "Sky High(goal-original)", "The King of Speed (ending)",
        "Let's Go Away (ending)", "Sky High (ending)", "The Noisy Roars of Wilderness(ending)",
        "Pounding Pavement (ending)", "The King of Speed(ending-original)", "Let's Go Away(ending-original)",
        "Sky High(ending-original)", "Sons of Angels", "The American Dream", "Lack of Speed",
        "Sunset on the DAYTONA Beach", "Crash & Burrn"]
PLAIN = [0, 1, 2, 4, 9, 10, 11, 13, 17, 18, 19, 21, 27]     # the plain-plate names
# names whose darkest ink splits into their letters: (name, ink level)
SOURCES = ((0, 3), (2, 3), (4, 3), (27, 3), (29, 3), (28, 3), (25, 3), (3, 5), (5, 3))
RADII, MIN_SEEN = (3, 2, 1), 2
HX = {v: k for k, v in enumerate('.123456789ABCDEF')}


def name_entry(slct, i):
    """CCE's name table entry i: (cells address, width in cells)."""
    return struct.unpack_from('>IH', slct, NAMES - SLCT_AT + 8 * i)


def cells_of(opt, at, w):
    return np.array(struct.unpack_from(f'>{3 * w}H', opt, at - OPT_AT)).reshape(3, w)


def render(opt, cells):
    img = np.zeros((24, 8 * cells.shape[1]), np.uint8)
    for r in range(3):
        for c in range(cells.shape[1]):
            t = np.frombuffer(opt, np.uint8, 32, SOUND_CHARS + 32 * int(cells[r, c]))
            img[8 * r:8 * r + 8, 8 * c:8 * c + 8] = np.stack([t >> 4, t & 15], 1).reshape(8, 8)
    return img


def picture(opt, slct, i):
    """CCE's name picture i, as palette indices."""
    return render(opt, cells_of(opt, *name_entry(slct, i)))


def ink_mask(img):
    return (img > 0) & (img < 8)


def bare_cut(img):
    """The first column of the gap before a name's last word: where the plate of the word
    before it ends."""
    used = img.any(0)
    x = len(used) - 1
    while not used[x]:
        x -= 1                          # the plate's empty end
    while used[x]:
        x -= 1                          # the last word
    while not used[x - 1]:
        x -= 1                          # the gap before it
    return x


def trim(img):
    """Cut to the plate, 5 empty columns before it as CCE's pictures have, padded to whole cells."""
    used = np.where(img.any(0))[0]
    img = np.pad(img[:, used[0]:used[-1] + 1], ((0, 0), (5, 0)))
    return np.pad(img, ((0, 0), (0, -img.shape[1] % 8)))


# --- letters ---

def runs_of(img, level):
    ink = ((img > 0) & (img <= level)).any(0)
    out, x = [], 0
    while x < len(ink):
        if ink[x]:
            a = x
            while x < len(ink) and ink[x]:
                x += 1
            out.append((a, x))
        else:
            x += 1
    return out


def ink_of(img, a, b):
    """The letter whose darkest ink is columns a to b: its ink only, a column either side."""
    s = img[:, a - 1:b + 1]
    ink = ink_mask(s)
    keep = np.zeros_like(ink)
    stack = [(r, c) for r in range(24) for c in range(1, s.shape[1] - 1) if ink[r, c]]
    for p in stack:
        keep[p] = True
    while stack:
        r, c = stack.pop()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < 24 and 0 <= cc < s.shape[1] and ink[rr, cc] and not keep[rr, cc]:
                    keep[rr, cc] = True
                    stack.append((rr, cc))
    return np.where(keep, s, 0).astype(np.uint8)


def ink_only(a):
    return np.where(ink_mask(a), a, 0).astype(np.uint8)


def grid(rows):
    return np.array([[HX[c] for c in r] for r in rows], np.uint8)


def letters(opt, slct):
    """char -> its ink, 24 rows high."""
    pic = {i: picture(opt, slct, i) for i in range(30)}
    lt = {}
    for i, level in SOURCES:
        runs = runs_of(pic[i], level)
        chars = TEXT[i].replace(' ', '')
        if len(runs) == len(chars):
            for ch, (a, b) in zip(chars, runs):
                lt.setdefault(ch, ink_of(pic[i], a, b))
    lt["'"] = ink_of(pic[1], 38, 40)                # Let's Go Away: the apostrophe, G, and w (from Aw)
    lt['G'] = ink_of(pic[1], 55, 63)
    w = ink_of(pic[1], 88, 98)
    w[:, 0] = 0
    lt['w'] = w

    I = ink_only(pic[2][:, 40:46])                  # I: High's H, its left stem and serifs
    I[7:12, 4:6] = 0                                # where the crossbar began
    I[:, 5] = 0
    lt['I'] = I
    a = ink_only(pic[28][:, 135:146])               # V: DAYTONA's A upside down, its bar out
    a[:, 0] = 0
    a[11:13, 4:6] = 0
    v = a.copy()
    v[3:17] = a[3:17][::-1]
    v[13:17] = grid(["...71316...", "....311....", "....515....", "....717...."])   # the v's point
    lt['V'] = v[:, ::-1].copy()                     # the heavy stroke on the left
    lt['F'] = grid([                                # F: drawn on Pounding's P, its stem and serifs
        "........", "........", "........",
        ".3111117", ".1111111", ".711771.", "..11..7.", "..11....", "..117.7.", "..11111.",
        "..11117.", "..11....", "..11....", "..11....", ".7116...", "11115...", "31116...",
        "........", "........", "........", "........", "........", "........", "........"])
    dot = lt['i'][1:6].copy()                       # the i's dot, cropped to its ink
    cols = np.where(dot.any(0))[0]
    dot = dot[:, cols[0]:cols[-1] + 1]

    def put_dot(dst, row):
        x = (dst.shape[1] - dot.shape[1]) // 2
        part = dst[row:row + 5, x:x + dot.shape[1]]
        dst[row:row + 5, x:x + dot.shape[1]] = np.where(dot > 0, dot, part)

    ex = lt['l'].copy()                             # !: an l cut short, the dot below
    ex[12:] = 0
    put_dot(ex, 13)
    lt['!'] = ex
    s = lt['S']                                     # ?: an S's top half mirrored, a stem, the dot
    q = np.zeros_like(s)
    q[2:10] = s[2:10, ::-1]
    c = q.shape[1] // 2
    q[10:12, c - 1:c + 1] = HX['1']
    put_dot(q, 13)
    lt['?'] = q
    return lt


def ink_line(text, lt):
    """The letters' ink with CCE's spacing, 4 empty columns either end."""
    inks = []
    for k, word in enumerate(text.split(' ')):
        if k:
            inks.append(np.zeros((24, 7 if word.startswith('(') else 5), np.uint8))
        for j, ch in enumerate(word):
            piece = lt[ch]
            cols = np.where(piece.any(0))[0]
            if j:
                inks.append(np.zeros((24, 1), np.uint8))
            inks.append(piece[:, cols[0]:cols[-1] + 1])
    return np.pad(np.concatenate(inks, 1), ((0, 0), (4, 4)))


# --- the plate ---

OFFSETS = sorted((dr * dr + dc * dc, dr, dc) for dr in range(-3, 4) for dc in range(-3, 4))


def window_codes(m, R):
    """For each pixel, which pixels of the (2R+1)^2 window round it are ink, as bits."""
    h, w = m.shape
    p = np.pad(m, R).astype(np.int64)
    code = np.zeros((h, w), np.int64)
    k = 0
    for dr in range(2 * R + 1):
        for dc in range(2 * R + 1):
            code |= p[dr:dr + h, dc:dc + w] << k
            k += 1
    return code


def nearest(m):
    """For each pixel, the offset of the nearest ink within 3 (-1: none)."""
    h, w = m.shape
    p = np.pad(m, 3)
    key = np.full((h, w), -1)
    for _, dr, dc in OFFSETS:
        hit = p[3 + dr:3 + dr + h, 3 + dc:3 + dc + w] & (key < 0)
        key[hit] = (dr + 3) * 7 + dc + 3
    return key


def learn(pictures):
    tables = {R: {} for R in RADII}
    by_offset = {}
    for img in pictures:
        m = ink_mask(img)
        codes = {R: window_codes(m, R) for R in RADII}
        key = nearest(m)
        for r, c in zip(*np.nonzero(~m)):
            v = int(img[r, c])
            for R in RADII:
                tables[R].setdefault(int(codes[R][r, c]), Counter())[v] += 1
            by_offset.setdefault(int(key[r, c]), Counter())[v] += 1
    return tables, by_offset


def outline(ink, rules):
    tables, by_offset = rules
    m = ink > 0
    codes = {R: window_codes(m, R) for R in RADII}
    key = nearest(m)
    out = ink.copy()
    for r, c in zip(*np.nonzero(~m)):
        for R in RADII:
            seen = tables[R].get(int(codes[R][r, c]))
            if seen and sum(seen.values()) >= MIN_SEEN:
                out[r, c] = seen.most_common(1)[0][0]
                break
        else:
            out[r, c] = by_offset[int(key[r, c])].most_common(1)[0][0]
    return out


class Lettering:
    """CCE's letters and plate rules, read from its own names."""

    def __init__(self, opt, slct):
        self.opt, self.slct = opt, slct
        self.lt = letters(opt, slct)
        self.rules = learn([picture(opt, slct, i) for i in PLAIN])

    def name(self, text):
        """A new name picture, cut to its plate and padded to whole cells."""
        return trim(outline(ink_line(text, self.lt), self.rules))

    def renamed(self, i, last_word):
        """CCE's name picture i with its last word replaced: CCE's own pixels up to where
        the word before it ends, the new word seven columns from that word's ink."""
        base = picture(self.opt, self.slct, i)
        x = bare_cut(base)
        last_ink = np.where(ink_mask(base[:, :x]).any(0))[0][-1]
        word = outline(ink_line(last_word, self.lt), self.rules)
        first_ink = np.where(ink_mask(word).any(0))[0][0]
        at = last_ink + 8 - first_ink              # where the word's picture starts
        used = np.where(word.any(0))[0]
        out = np.zeros((24, at + used[-1] + 1), np.uint8)
        out[:, :x] = base[:, :x]
        assert at + used[0] >= x, 'the new word overlaps the plate before it'
        out[:, at + used[0]:] = word[:, used[0]:used[-1] + 1]
        return np.pad(out, ((0, 0), (0, -out.shape[1] % 8)))
