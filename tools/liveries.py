"""The paint of every car on DUSA's body: DUSA's own Gallop and the '95
liveries of CCE's cars, each in an automatic and a manual version
(docs/liveries.md).

usage: liveries.py <dusa extracted dir> <out png>
  Renders every car here in both liveries, from the textures and tables
  tools/car_convert.py builds into the car files.

A paint is the DUSA body's textures as 4bpp pixels and 29 16-colour
tables (LAYOUT). The two liveries share the pixels and differ in tables
2-14, the automatic set; tables 16-28 hold the manual set in the same
order, which patches/livery.s copies over 2-14 for a manual car. Tables 2-7
are DUSA's own (the body's panels, pillars, lights, decals: each texture
keeps its DUSA table and pixels); the textures that carry a livery's art
(hood, roof and door numbers, trunk, side lettering, tail) have a table
each, 8-14, so a new livery can repaint them. Tables 0, 1 and 15 are
DUSA's unchanged (the dark under-body details and the window strip).

The Gallop's paint is DUSA's textures and tables as they are, the art
textures' pixels renumbered onto their new tables. A '95 livery recolours
DUSA's manual (red and yellow) tables 2-7 by role: reds to the body
colour, yellows to the panel colour (hood, roof and trunk), the light greys
of table 3 to the lower body's, each colour keeping its step of brightness;
and paints the art textures afresh, drawn here as shapes in code: polygon
emblems, numbers built from rectangles, lettering from fonts drawn without
smoothing, all at the textures' own size.
"""
import colorsys
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import car_convert as cc  # noqa: E402
from dusa_lzss import decompress  # noqa: E402

FONTS = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
BLACK = (0.0, 0.0, 0.0)

# table layout of every DUSA-body car file
N_TABLES = 29
FIXED = {0: 0, 1: 1, 15: 15}            # file table <- DUSA table, the same in both liveries
STRUCTURAL = range(2, 8)                # DUSA's tables 2-7, at their own numbers
SET_B = 16 - 2                          # manual set = automatic set's table + 14
GROUPS = {                              # art texture groups: their table
    8: (25, 26, 27),                    # hood, three strips side by side
    9: (28,),                           # roof number
    10: (29,),                          # trunk
    11: (37, 38),                       # door number, top rows
    12: (39,),                          # door number, bottom rows (the lower body)
    13: (40, 41, 42, 43, 46, 47, 48, 49),   # rear quarter lettering, both sides
    14: (30, 31),                       # tail: spoiler face and plate
}
ART_TABLE = {tid: t for t, tids in GROUPS.items() for tid in tids}


def table_of(tid):
    """The file table a texture uses."""
    return ART_TABLE.get(tid, cc.TEXTURES[tid][3])


# ---------------------------------------------------------------- DUSA's textures

def dusa_pixels(texpl):
    """Texture id -> 4bpp indices (h x w), as DUSA stores them."""
    out = {}
    for tid, (off, w, h, _) in cc.TEXTURES.items():
        n = 80 * 80 // 2 if tid == cc.WINDOW_TEX else w * h // 2
        data, _ = decompress(texpl, off, n)
        out[tid] = np.array([v for b in data[:n] for v in (b >> 4, b & 15)]).reshape(-1, w)
    return out


def dusa_table(texpl, n, manual):
    off = 0x100 + 32 * (n - 2) if manual and 2 <= n <= 7 else cc.TABLES[n]
    return list(struct.unpack_from('>16H', texpl, off))


def word(rgb):
    """Float RGB (0-1) -> a 15-bit colour word as DUSA's tables hold them."""
    r, g, b = (int(round(float(np.clip(v, 0, 1)) * 31)) for v in rgb)
    return 0x8000 | b << 10 | g << 5 | r


def unword(w):
    return np.array([w & 31, (w >> 5) & 31, (w >> 10) & 31], float) / 31


class Paint:
    """pixels: texture id -> 4bpp indices; tables: N_TABLES x 16 colour words."""
    def __init__(self, name, pixels, tables):
        self.name, self.pixels, self.tables = name, pixels, tables

    def rgb(self, tid, manual):
        """A texture in one livery, as floats, for previews."""
        t = table_of(tid)
        if manual and 2 <= t <= 14:
            t += SET_B
        pal = np.array([unword(w) for w in self.tables[t]])
        return pal[self.pixels[tid]]


def assemble(name, texpl, structural, art):
    """A paint from each livery's tables 2-7 (structural: [auto, manual], each
    {DUSA table: 16 words}) and art images (art: [auto, manual], each
    {texture id: h x w x 3 floats}): every art group's pixels numbered by
    the pairs of colours they have in the two liveries."""
    pixels = dusa_pixels(texpl)
    tables = [[0x8000] * 16 for _ in range(N_TABLES)]
    for t, src in FIXED.items():
        tables[t] = dusa_table(texpl, src, False)
    for t in STRUCTURAL:
        tables[t] = structural[0][t]
        tables[t + SET_B] = structural[1][t]
    for t, tids in GROUPS.items():
        pairs = {}
        for tid in tids:
            a, m = (np.array([[word(p) for p in row] for row in img[tid]]) for img in art)
            h, w = pixels[tid].shape
            if a.shape != (h, w) or m.shape != (h, w):
                raise ValueError(f'{name}: texture {tid} is {a.shape}, DUSA\'s is {(h, w)}')
            idx = np.zeros((h, w), int)
            for y in range(h):
                for x in range(w):
                    idx[y, x] = pairs.setdefault((a[y, x], m[y, x]), len(pairs))
            pixels[tid] = idx
        if len(pairs) > 16:
            raise ValueError(f'{name}: textures {tids} have {len(pairs)} colour pairs, the table holds 16')
        for (wa, wm), i in pairs.items():
            tables[t][i] = wa
            tables[t + SET_B][i] = wm
    return Paint(name, pixels, tables)


def dusa_rgb(texpl, pixels, tid, manual):
    pal = np.array([unword(w) for w in dusa_table(texpl, cc.TEXTURES[tid][3], manual)])
    return pal[pixels[tid]]


def gallop(texpl):
    """DUSA's own car: automatic red and blue, manual yellow and red."""
    pixels = dusa_pixels(texpl)
    structural = [{t: dusa_table(texpl, t, manual) for t in STRUCTURAL} for manual in (False, True)]
    art = [{tid: dusa_rgb(texpl, pixels, tid, manual) for tid in ART_TABLE} for manual in (False, True)]
    return assemble('Gallop', texpl, structural, art)


# ---------------------------------------------------------------- '95 recolouring

class Scheme:
    """A '95 livery's colours: body (the sides), panel (hood, roof, trunk),
    lower (below the door line), each a (dark, mid, light) ramp; net, the
    side window's net; and its art colours (named, used by the car's art)."""
    def __init__(self, body, panel, lower, net, **art):
        self.body, self.panel, self.lower, self.net, self.art = body, panel, lower, net, art


def ramp(t, dark, mid, light):
    t = float(t)
    if t <= 1:
        return np.array(dark) + (np.array(mid) - dark) * max(0.0, t)
    return np.array(mid) + (np.array(light) - mid) * min(1.0, t - 1)


def role(rgb, s, lower_ok):
    """One of DUSA's manual-livery colours in the scheme: its reds on the
    body ramp, its yellows on the panel's, (lower_ok) its greys on the
    lower body's, each by its brightness against DUSA's middle step."""
    r, g, b = rgb
    h, sat, v = colorsys.rgb_to_hsv(r, g, b)
    if v < 0.02:
        return np.array(rgb)
    if sat > 0.5 and (h < 0.04 or h > 0.93):
        return ramp(v / 0.74 if v <= 0.74 else 1 + (v - 0.74) / 0.26, *s.body)
    if sat > 0.5 and 0.06 < h < 0.2:
        return ramp(v / 0.95 if v <= 0.95 else 1 + (v - 0.95) / 0.05, *s.panel)
    if lower_ok and sat < 0.12:
        return ramp(v / 0.42 if v <= 0.42 else 1 + (v - 0.42) / 0.58, *s.lower)
    return np.array(rgb)


LOWER_TABLE = 3                         # sills and the decals' panels: greys are the lower body
NET_TEX, TAIL_LIGHTS = 24, 22


def structural_tables(texpl, s):
    """DUSA's manual tables 2-7 in the scheme. The tail lights keep their
    colours and the window net takes the scheme's."""
    pixels = dusa_pixels(texpl)
    out = {}
    for t in STRUCTURAL:
        users = [tid for tid in cc.TEXTURES if table_of(tid) == t]
        keep = set(np.unique(pixels[TAIL_LIGHTS])) if TAIL_LIGHTS in users else set()
        net = set(np.unique(pixels[NET_TEX])) if NET_TEX in users else set()
        for tid in users:
            if tid not in (TAIL_LIGHTS, NET_TEX):
                used = set(np.unique(pixels[tid]))
                keep -= used
                net -= used
        src = dusa_table(texpl, t, True)
        row = []
        for i, w in enumerate(src):
            if i in keep:
                row.append(w)
            elif i in net:
                row.append(word(np.array(s.net) * (0.55 + 0.45 * unword(w).max())))
            else:
                row.append(word(role(unword(w), s, t == LOWER_TABLE)))
        out[t] = row
    return out


def recoloured(texpl, pixels, tid, s):
    """A DUSA texture (manual livery) in the scheme, as floats."""
    pal = np.array([role(unword(w), s, cc.TEXTURES[tid][3] == LOWER_TABLE)
                    for w in dusa_table(texpl, cc.TEXTURES[tid][3], True)])
    return pal[pixels[tid]]


# ---------------------------------------------------------------- drawing

def c(hexstr):
    """'#rrggbb' -> floats on the Saturn's 5 bits a channel."""
    return tuple(round(int(hexstr[i:i + 2], 16) / 255 * 31) / 31 for i in (1, 3, 5))


def blank(w, h):
    return np.zeros((h, w), bool)


def canvas(w, h, colour):
    out = np.zeros((h, w, 3))
    out[:] = colour
    return out


def text_mask(text, font, width=None, height=None, italic=0.0):
    """Text drawn without smoothing, cropped, squeezed to width and/or
    height, slanted by italic (pixels of shift per pixel of height)."""
    big = 96
    f = ImageFont.truetype(os.path.join(FONTS, font), big)
    im = Image.new('L', (len(text) * big * 2, big * 3), 0)
    ImageDraw.Draw(im).text((big, big // 2), text, fill=255, font=f)
    im = im.crop(im.getbbox())
    if italic:
        w, h = im.size
        sh = int(italic * h)
        im = im.transform((w + sh, h), Image.AFFINE, (1, italic, -sh, 0, 1, 0), Image.BILINEAR)
    w, h = im.size
    if width and height:
        tw, th = width, height
    elif width:
        tw, th = width, max(1, round(h * width / w))
    else:
        tw, th = max(1, round(w * height / h)), height
    return np.asarray(im.resize((tw, th), Image.BOX)) >= 112


def poly_mask(w, h, shapes, box, ss=8):
    """Shapes in design units (box = width, height) drawn into w x h, each
    pixel set when more than half of it is covered. A shape of two points
    is a circle (centre, a point on its right)."""
    bw, bh = box
    im = Image.new('L', (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    for pts in shapes:
        p = [(x / bw * w * ss, y / bh * h * ss) for x, y in pts]
        if len(p) == 2:
            (cx, cy), (rx, _) = p
            r = abs(rx - cx)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        else:
            d.polygon(p, fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)) >= 128


def grow(m, r=1):
    out = m.copy()
    for _ in range(r):
        g = out.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                g |= shift(out, dx, dy)
        out = g
    return out


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape[:2]
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = \
        m[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


def place(mask, w, h, x=None, y=None):
    """A mask or image put into a w x h frame, centred unless placed."""
    mh, mw = mask.shape[:2]
    out = np.zeros((h, w) + mask.shape[2:], mask.dtype)
    x = (w - mw) // 2 if x is None else x
    y = (h - mh) // 2 if y is None else y
    out[y:y + mh, x:x + mw] = mask
    return out


def bands(h, w, colours):
    """Hard bands from top to bottom, DUSA's way of shading in steps."""
    out = np.zeros((h, w, 3))
    for y in range(h):
        out[y] = colours[min(len(colours) - 1, y * len(colours) // h)]
    return out


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32


def glow(w, h, cx, cy, r, colours):
    """A round glow from colours[-1] at the centre out to colours[0], in
    steps blended with a 4 x 4 ordered dither."""
    yy, xx = np.mgrid[0:h, 0:w]
    t = 1 - np.clip(np.hypot(xx - cx, yy - cy) / r, 0, 1)
    n = len(colours) - 1
    v = t * n
    lo = np.floor(v).astype(int)
    th = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    return np.array(colours)[np.clip(lo + (v - lo > th), 0, n)]


def paint(cv, mask, colour):
    cv[mask] = colour if np.ndim(colour) == 1 or isinstance(colour, tuple) else colour[mask]


def outlined(cv, mask, fill, outline=BLACK, width=1):
    paint(cv, grow(mask, width), outline)
    paint(cv, mask, fill)


def bevel(mask, fill, light, dark):
    """A number's shading as DUSA draws its 41: light edges top-left, dark bottom-right."""
    out = np.zeros(mask.shape + (3,))
    out[:] = fill
    out[mask & ~(shift(mask, -1, 0) & shift(mask, 0, -1))] = dark
    out[mask & ~(shift(mask, 1, 0) & shift(mask, 0, 1))] = light
    return out


def digit8(w, h, stroke):
    """A squared 8 with cut corners and a notched waist, after DUSA's 41."""
    s = stroke
    m = np.ones((h, w), bool)
    ch = s // 2 + 1
    for i in range(ch):
        m[i, :ch - i] = m[i, w - ch + i:] = False
        m[h - 1 - i, :ch - i] = m[h - 1 - i, w - ch + i:] = False
    mid = h // 2
    m[s:mid - s // 2, s:w - s] = False
    m[mid + s // 2 + h % 2:h - s, s:w - s] = False
    notch = max(1, s // 3)
    m[mid - 1:mid + 1, :notch] = False
    m[mid - 1:mid + 1, w - notch:] = False
    return m


def split_cols(img, widths):
    xs = np.cumsum((0,) + tuple(widths))
    return [img[:, a:b] for a, b in zip(xs, xs[1:])]


def split_rows(img, heights):
    ys = np.cumsum((0,) + tuple(heights))
    return [img[a:b] for a, b in zip(ys, ys[1:])]


# ---------------------------------------------------------------- the Phoenix

# design space 100 x 70: wings raised, a crested head looking right, a
# tail of three flames
PHOENIX = [
    [(46, 30), (30, 16), (6, 2), (12, 14), (2, 13), (14, 23), (5, 26), (20, 32), (12, 37), (30, 38), (42, 44)],
    [(54, 30), (70, 16), (94, 2), (88, 14), (98, 13), (86, 23), (95, 26), (80, 32), (88, 37), (70, 38), (58, 44)],
    [(43, 26), (57, 26), (60, 42), (50, 54), (40, 42)],
    [(50, 22), (55.5, 22)],
    [(54, 19), (63, 23), (54, 26)],
    [(46, 19), (40, 8), (48, 15), (49, 4), (53, 15), (58, 9), (54, 19)],
    [(42, 48), (34, 68), (45, 57), (50, 70), (55, 57), (66, 68), (58, 48)],
]
PHOENIX_FEATHERS = [
    [(40, 33), (16, 12), (18, 11), (42, 31)],
    [(41, 37), (12, 22), (13, 20), (43, 35)],
    [(60, 33), (84, 12), (82, 11), (58, 31)],
    [(59, 37), (88, 22), (87, 20), (57, 35)],
    [(48, 52), (46, 62), (48, 61), (50, 53)],
    [(52, 52), (54, 62), (52, 61), (50, 53)],
]
PHOENIX_EYE = [[(52.5, 21.5), (53.8, 21.5)]]


def phoenix_art(texpl, s):
    """The Phoenix's art textures in scheme s: the bird on a glow over the
    hood with PHOENIX under it, the 8 on the roof and doors, PHOENIX RACING
    TEAM on the trunk and the tail, PHOENIX along the rear quarters under
    a stripe. Every scheme draws the same shapes, so the two liveries share
    their pixels."""
    a = s.art
    base = dusa_pixels(texpl)
    out = {}

    hood = glow(72, 72, 36, 28, 40, [s.panel[1]] + a['glow'])
    bw, bh, by = 70, 48, 3
    bird = place(poly_mask(bw, bh, PHOENIX, (100, 70)), 72, 72, y=by)
    fill = place(bands(bh, bw, a['bird']), 72, 72, y=by)
    paint(hood, grow(bird), a['bird_outline'])
    paint(hood, bird, fill)
    paint(hood, bird & place(poly_mask(bw, bh, PHOENIX_FEATHERS, (100, 70)), 72, 72, y=by), a['feathers'])
    paint(hood, bird & place(poly_mask(bw, bh, PHOENIX_EYE, (100, 70)), 72, 72, y=by), a['eye'])
    outlined(hood, place(text_mask('PHOENIX', 'impact.ttf', width=60, italic=0.25), 72, 72, y=57),
             a['name'], a['name_outline'])
    out.update(zip((25, 26, 27), split_cols(hood, (24, 24, 24))))

    roof = canvas(48, 48, s.panel[1])
    d = place(digit8(30, 42, 8), 48, 48)
    paint(roof, shift(grow(d, 2), 2, 2), a['shadow'])
    paint(roof, grow(d, 2), a['number_outline'])
    paint(roof, d, bevel(d, *a['number']))
    out[28] = roof

    # the door: DUSA's rows of body, its shade and the lower body, the
    # number painted over them
    door = np.concatenate([recoloured(texpl, base, t, s) for t in (37, 38, 39)], 0)
    door[:] = door[:, :2].mean(1, keepdims=True)
    d = place(digit8(22, 34, 6), 48, 40, y=3)
    paint(door, shift(grow(d), 2, 1), a['door_shadow'])
    paint(door, grow(d), a['number_outline'])
    paint(door, d, bevel(d, *a['number']))
    out.update(zip((37, 38, 39), split_rows(door, (12, 12, 16))))

    trunk = canvas(80, 40, s.panel[1])
    outlined(trunk, place(text_mask('PHOENIX', 'impact.ttf', width=72, italic=0.25), 80, 40, y=6),
             a['name'], a['name_outline'])
    paint(trunk, place(text_mask('RACING TEAM', 'ariblk.ttf', height=6), 80, 40, y=28), a['team'])
    out[29] = trunk

    # rear quarters, read front to back on the left (46|47|48) and on the
    # right (42|41|40); their top rows line up
    for tids, widths in (((46, 47, 48), (40, 24, 72)), ((42, 41, 40), (72, 24, 40))):
        cv = canvas(136, 16, s.body[1])
        for y, col in enumerate(a['stripe']):
            cv[y] = col
        outlined(cv, place(text_mask('PHOENIX', 'impact.ttf', height=8, italic=0.25), 136, 16, y=3),
                 a['side'], a['side_outline'])
        for tid, part in zip(tids, split_cols(cv, widths)):
            out[tid] = part[:base[tid].shape[0]]
    for tid in (43, 49):
        cv = canvas(64, 12, s.body[1])
        for y, col in enumerate(a['stripe']):
            cv[y] = col
        out[tid] = cv

    spoiler = canvas(96, 8, s.body[1])
    spoiler[2:4] = a['stripe'][1]
    plate = canvas(96, 16, a['plate'])
    outlined(plate, place(text_mask('PHOENIX', 'impact.ttf', height=11, italic=0.2), 96, 16),
             a['side'], a['side_outline'])
    out[30], out[31] = spoiler, plate
    return out


BLACK_RAMP = (c('#000000'), c('#141418'), c('#40404c'))
RED_RAMP = (c('#300000'), c('#c00010'), c('#ff5040'))

# Firebird (automatic): black, a fire phoenix on an ember glow, yellow 8
FIREBIRD = Scheme(
    BLACK_RAMP, BLACK_RAMP, (c('#300000'), c('#a00808'), c('#f04020')), c('#ffd800'),
    glow=[c('#500800'), c('#a01800'), c('#e04000'), c('#ff8000')],
    bird=[c('#fff070'), c('#ffd000'), c('#ff9000'), c('#f05000'), c('#c01800')],
    bird_outline=BLACK, feathers=c('#a01000'), eye=BLACK,
    name=c('#ff2010'), name_outline=c('#ffd000'),
    number=(c('#ffd800'), c('#fff6a0'), c('#d08000')), number_outline=BLACK,
    shadow=c('#a01000'), door_shadow=c('#a01000'), team=c('#ffd000'),
    stripe=[c('#ffd000'), c('#ff8000'), c('#e02000')], side=c('#ffd000'), side_outline=c('#a01000'),
    plate=c('#141418'))

# Ember (manual): red sides, a black top, a gold phoenix and 8
EMBER = Scheme(
    RED_RAMP, BLACK_RAMP, BLACK_RAMP, c('#ffd800'),
    glow=[c('#141418')] * 4,
    bird=[c('#fff4a0'), c('#ffe040'), c('#ffd000'), c('#f0a000'), c('#c06800')],
    bird_outline=c('#c00010'), feathers=c('#a06000'), eye=BLACK,
    name=c('#ffd800'), name_outline=c('#c00010'),
    number=(c('#ffd800'), c('#fff6a0'), c('#d08000')), number_outline=c('#c00010'),
    shadow=c('#141418'), door_shadow=c('#500000'), team=c('#ff3020'),
    stripe=[c('#ffd000'), c('#c00010'), c('#ffd000')], side=c('#ffd800'), side_outline=BLACK,
    plate=c('#101010'))


def phoenix(texpl):
    schemes = (FIREBIRD, EMBER)
    return assemble('Phoenix', texpl, [structural_tables(texpl, s) for s in schemes],
                    [phoenix_art(texpl, s) for s in schemes])


# CCE's cars with a '95 livery: car number (from 1) -> its paint
NINETY_FIVE = {4: phoenix}


# ---------------------------------------------------------------- preview

def main():
    sys.path.insert(0, os.path.dirname(__file__))
    import car_sheet as cs
    dusa, dst = sys.argv[1], sys.argv[2]
    texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    _, faces = cc.faces(poly, cc.BODY)
    base = cs.dusa_mesh(dusa, False)
    paints = [gallop(texpl)] + [f(texpl) for f in NINETY_FIVE.values()]
    views = (('top', 0, 90, 130, 270), ('left', 0, 0, 270, 95), ('front 3/4', 50, 25, 260, 150),
             ('rear 3/4', 230, 25, 260, 150))
    pad, label = 10, 24
    row_h = 270 + label + pad
    out = Image.new('RGB', (sum(v[3] + pad for v in views) + pad, row_h * 2 * len(paints)), cs.BG)
    d = ImageDraw.Draw(out)
    cs.PX = 48
    r = 0
    for p in paints:
        for manual in (False, True):
            quads = []
            for (idx, _, px, tr, hf, vf, gl), (_, tid, _) in zip(base.quads, faces):
                img = p.rgb(tid, manual)[:px.shape[0]]
                quads.append((idx, img, p.pixels[tid][:px.shape[0]], tr, hf, vf, gl))
            mesh = cs.Mesh('', base.verts, quads, '')
            y = r * row_h
            d.text((pad, y + 4), f"{p.name}, {'manual' if manual else 'automatic'}", fill=(235, 235, 235))
            x = pad
            for _, az, el, w, h in views:
                out.paste(cs.render(mesh, az, el, w, h), (x, y + label))
                x += w + pad
            r += 1
    out.save(dst)
    print('wrote', dst)


if __name__ == '__main__':
    main()
