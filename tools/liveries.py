"""The paint of every car on DUSA's body: DUSA's own Gallop and the '95
liveries of CCE's cars, each in an automatic and a manual version
(docs/liveries.md).

usage: liveries.py <dusa extracted dir> <cce extracted dir> <out png>
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
and paints the art textures afresh at their own size: the Phoenix's drawn
here as shapes in code (polygon emblems, numbers built from rectangles,
lettering from fonts drawn without smoothing), the others' borrowed from
their CCE paint (its logo traced, its wordmark) with a number from a font,
drawn smooth and anti-aliased.
"""
import colorsys
import os
import struct
import sys

import cv2
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


def kmeans(x, k, fixed, iters=30):
    """k centres for points x, deterministic: each new start the point
    farthest from the fixed centres and those chosen, then Lloyd's steps."""
    d = np.linalg.norm(x[:, None] - fixed[None], axis=-1).min(1) if len(fixed) else np.full(len(x), np.inf)
    c = []
    for _ in range(k):
        c.append(x[d.argmax()])
        d = np.minimum(d, np.linalg.norm(x - c[-1], axis=-1))
    c = np.array(c)
    for _ in range(iters):
        near = np.linalg.norm(x[:, None] - c[None], axis=-1).argmin(1)
        c = np.array([x[near == i].mean(0) if (near == i).any() else c[i] for i in range(k)])
    return c


def fit_colours(v, n=16):
    """Pixels' colours in the two liveries (rows of 6, on the Saturn's 5
    bits) brought to n pairs when there are more: the pairs covering at least
    1% of the pixels kept as they are (leaving 4 for edges), the rest of the
    table the k-means of the pixels they don't match."""
    uniq, counts = np.unique(v, axis=0, return_counts=True)
    if len(uniq) <= n:
        return v
    order = np.argsort(-counts, kind='stable')
    kept = uniq[[i for i in order[:n - 4] if counts[i] >= 0.01 * len(v)]]
    rest = v[np.abs(v[:, None] - kept[None]).max(-1).min(1) > 0.5 / 31]
    table = np.concatenate([kept, np.round(kmeans(rest, n - len(kept), kept) * 31) / 31])
    return table[np.linalg.norm(v[:, None] - table[None], axis=-1).argmin(1)]


def assemble(name, texpl, structural, art):
    """A paint from each livery's tables 2-7 (structural: [auto, manual], each
    {DUSA table: 16 words}) and art images (art: [auto, manual], each
    {texture id: h x w x 3 floats}): every art group's pixels numbered by
    the pairs of colours they have in the two liveries, at most 16."""
    pixels = dusa_pixels(texpl)
    tables = [[0x8000] * 16 for _ in range(N_TABLES)]
    for t, src in FIXED.items():
        tables[t] = dusa_table(texpl, src, False)
    for t in STRUCTURAL:
        tables[t] = structural[0][t]
        tables[t + SET_B] = structural[1][t]
    for t, tids in GROUPS.items():
        for tid in tids:
            for img in art:
                if img[tid].shape[:2] != pixels[tid].shape:
                    raise ValueError(f'{name}: texture {tid} is {img[tid].shape[:2]}, DUSA\'s is {pixels[tid].shape}')
        v = np.concatenate([np.concatenate([img[tid].reshape(-1, 3) for img in art], 1) for tid in tids])
        v = fit_colours(np.round(np.clip(v, 0, 1) * 31) / 31)
        pairs, at = {}, 0
        for tid in tids:
            h, w = pixels[tid].shape
            pixels[tid] = np.array([pairs.setdefault((word(p[:3]), word(p[3:])), len(pairs))
                                    for p in v[at:at + h * w]]).reshape(h, w)
            at += h * w
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


# ---------------------------------------------------------------- smooth art

# Borrowed art is drawn as smooth shapes on a grid FINE times finer than the
# texture; each texel takes the share of it its area covers, blended into
# the colours under it (anti-aliasing), and assemble brings each group back
# to 16 colours.
FINE = 8


def disc(r):
    k = 2 * int(np.ceil(r)) + 1
    yy, xx = np.mgrid[:k, :k] - k // 2
    return (np.hypot(xx, yy) <= r + 0.01).astype(np.uint8)


def fine_grown(m, r):
    """A fine mask grown by r fine pixels, round."""
    return cv2.dilate(m.astype(np.uint8), disc(r)).astype(bool)


def coverage(fine):
    """A fine mask -> each texel's share of it."""
    h, w = fine.shape
    return fine.reshape(h // FINE, FINE, w // FINE, FINE).mean((1, 3))


def blend(cv, cover, colour):
    a = cover[..., None]
    cv[:] = cv * (1 - a) + np.array(colour) * a


def fine_place(mask, w, h, x=None, y=None):
    """place() onto the fine grid of a w x h texture, x and y in texels."""
    return place(mask, w * FINE, h * FINE, None if x is None else round(x * FINE),
                 None if y is None else round(y * FINE))


def font_mask(text, font, height, max_width=None):
    """Text in a font, height texels tall on the fine grid, squeezed to
    max_width texels when wider."""
    big = 400
    f = ImageFont.truetype(os.path.join(FONTS, font), big)
    im = Image.new('L', (len(text) * big * 2, big * 3), 0)
    ImageDraw.Draw(im).text((big // 2, big // 2), text, fill=255, font=f)
    im = im.crop(im.getbbox())
    th = round(height * FINE)
    tw = round(im.width * th / im.height)
    if max_width and tw > max_width * FINE:
        tw = round(max_width * FINE)
    return np.asarray(im.resize((tw, th), Image.LANCZOS)) >= 128


def soft_inks(rgb):
    """CCE paint -> each pixel's (dark, red) shares, keeping the smoothing
    CCE drew at their edges."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red = np.clip((r - np.maximum(g, b) - 0.15) / 0.4, 0, 1)
    dark = np.clip((0.6 - rgb.max(-1)) / 0.4, 0, 1) * (1 - red)
    return dark, red


def drawn_up(soft, w=None, h=None):
    """A soft mask of CCE's pixels drawn up to w x h pixels (either kept in
    proportion), smooth: cubic, softened by a third of one of its pixels, its
    edge where it crosses half."""
    sh, sw = soft.shape
    w = w or round(sw * h / sh)
    h = h or round(sh * w / sw)
    big = cv2.resize(np.pad(soft, 2).astype(np.float32), (w + round(4 * w / sw), h + round(4 * h / sh)),
                     interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), w / sw / 3)
    py, px = round(2 * h / sh), round(2 * w / sw)
    return big[py:py + h, px:px + w] > 0.5


def traced(mask, sigma, round_below=0):
    """A mask's shapes traced to outlines, each smoothed along its length
    (sigma pixels) and filled again; those smaller than round_below square
    pixels become ellipses (a logo's holes)."""
    hard = (mask > 0.5).astype(np.uint8)
    contours, hier = cv2.findContours(hard, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    out = np.zeros(mask.shape, np.uint8)
    if hier is None:
        return out.astype(bool)
    hier = hier[0]

    def depth(i):
        n = 0
        while hier[i][3] >= 0:
            i, n = hier[i][3], n + 1
        return n

    k = int(3 * sigma)
    g = np.exp(-np.arange(-k, k + 1) ** 2 / (2 * sigma ** 2))
    g /= g.sum()
    for i in sorted(range(len(contours)), key=depth):
        fill = 1 - depth(i) % 2           # shapes, then their holes
        c = contours[i][:, 0].astype(float)
        if len(c) >= 5 and cv2.contourArea(contours[i]) < round_below:
            cv2.ellipse(out, cv2.fitEllipse(contours[i]), fill, -1)
            continue
        if len(c) > 2 * k + 1:
            ring = np.concatenate([c[-k:], c, c[:k]])
            c = np.stack([np.convolve(ring[:, j], g, 'valid') for j in (0, 1)], 1)
        cv2.fillPoly(out, [np.round(c * 16).astype(np.int32)], fill, shift=4)
    return out.astype(bool)


def mirror_axis(m, near, reach=40):
    """The column (to half a pixel, within reach of near) m is most nearly
    symmetric about."""
    w = m.shape[1]
    best = max(((m * m[:, np.clip(np.round(2 * k - np.arange(w)).astype(int), 0, w - 1)]).sum(), k)
               for k in np.arange(near - reach, near + reach, 0.5))
    return best[1]


def symmetric(m, axis):
    w = m.shape[1]
    return 0.5 * (m + m[:, np.clip(np.round(2 * axis - np.arange(w)).astype(int), 0, w - 1)])


def bilinear(img, col, row):
    """img at fractional (col, row), pixel centres at .5; 0 outside."""
    h, w = img.shape
    c0 = np.clip(np.floor(col - 0.5).astype(int), 0, w - 2)
    r0 = np.clip(np.floor(row - 0.5).astype(int), 0, h - 2)
    fc, fr = np.clip(col - 0.5 - c0, 0, 1), np.clip(row - 0.5 - r0, 0, 1)
    out = img[r0, c0] * (1 - fc) * (1 - fr) + img[r0, c0 + 1] * fc * (1 - fr) + \
        img[r0 + 1, c0] * (1 - fc) * fr + img[r0 + 1, c0 + 1] * fc * fr
    return np.where((col >= 0) & (col < w) & (row >= 0) & (row < h), out, 0)


def world_cover(mask, to_px, world):
    """Each texel's share of a mask laid on the body: world as texel_world
    gives it, to_px(x, z) -> the mask's (col, row)."""
    col, row = to_px(world[..., 0], world[..., 1])
    return (bilinear(mask.astype(float), col, row) > 0.5).mean(-1)


# ---------------------------------------------------------------- borrowed art

class Sources:
    """The files a paint draws on: DUSA's TEX_PL (its body's textures) and
    CCE's car files (their own logos)."""
    def __init__(self, dusa, cce):
        self.texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
        self.dusa, self.cce = dusa, cce


def cce_texture(src, car, entry):
    """Texture entry of CCE's car (from 1) as floats, as its model maps it."""
    import car_sheet as cs
    mdl = open(os.path.join(src.cce, 'DAYTONA', f'PLCAR{car:02d}.MDL'), 'rb').read()
    tex = open(os.path.join(src.cce, 'DAYTONA', f'PLCAR{car:02d}.TEX'), 'rb').read()
    tsym = cs.symbols(tex)
    tables, pixels = tsym[0xB9], tsym[0xBA]
    _, lut, at, size = struct.unpack_from('>4H', mdl, 8 + 8 * entry)
    w, h = (size >> 8) * 8, size & 0xFF
    raw = tex[pixels + 8 * at:pixels + 8 * at + w * h // 2]
    px = np.array([v for b in raw for v in (b >> 4, b & 15)]).reshape(h, w)
    pal = np.array([unword(struct.unpack_from('>H', tex, tables + 8 * lut + 2 * i)[0]) for i in range(16)])
    return pal[px]


TOP_PX = 480                            # pixels a unit of CCE's cars drawn from above
CCE_TEXELS = 83                         # texels a unit across CCE's hood


def cce_top(src, car):
    """CCE's car from above in its textures' own colours, TOP_PX a unit, and
    the world (x, z) of its middle pixel (car_sheet's mirrored frame)."""
    import car_sheet as cs
    mesh = cs.cce_mesh(src.cce, car, '')
    lo, hi = mesh.verts.min(0), mesh.verts.max(0)
    w, h = int((hi[0] - lo[0]) * TOP_PX) + 8, int((hi[2] - lo[2]) * TOP_PX) + 8
    px, ss = cs.PX, cs.SS
    cs.PX, cs.SS = TOP_PX, 1
    try:
        img = np.asarray(cs.render(mesh, 0, 90, w, h, lit_from=None)).astype(float) / 255
    finally:
        cs.PX, cs.SS = px, ss
    return img, ((hi + lo) / 2)[[0, 2]]


class Logo:
    """A CCE logo traced from its car seen from above: its dark and red
    masks, and to_px(x, z, at_z, scale), DUSA world -> their pixels for the
    logo's middle put on the car's middle at z = at_z, scale times its size."""
    def __init__(self, dark, red, to_px):
        self.dark, self.red, self.to_px = dark, red, to_px


def cce_logo(src, car, x0, x1, z0, z1, dark_z0):
    """The logo inside x0..x1, z0..z1 on CCE's car (DUSA's frame), its dark
    parts down to dark_z0 (the Gallop's horseshoe runs on under the nose
    lettering): traced smooth, its small holes made round and the whole made
    symmetric about its own middle, which CCE draws a little off the car's."""
    img, (cx, cz) = cce_top(src, car)
    h, w = img.shape[:2]
    texel = TOP_PX / CCE_TEXELS
    dark, red = (cv2.GaussianBlur(m, (0, 0), texel / 2) for m in soft_inks(img))

    def col(x):
        return w / 2 + TOP_PX * (-x - cx)

    def row(z):
        return h / 2 + TOP_PX * (z - cz)

    def inside(z_from):
        m = np.zeros((h, w))
        c0, c1 = sorted(int(round(col(x))) for x in (x0, x1))
        r0, r1 = sorted(int(round(row(z))) for z in (z_from, z1))
        m[r0:r1, c0:c1] = 1
        return m

    dark, red = dark * inside(dark_z0), red * inside(z0)
    axis = mirror_axis(dark, col(0))
    dark = traced(symmetric(dark, axis), 0.7 * texel, round_below=(7 * texel) ** 2)
    red = traced(symmetric(red, axis), 0.5 * texel)
    mid_x, mid_z = -((axis - w / 2) / TOP_PX + cx), (z0 + z1) / 2

    def to_px(x, z, at_z, scale):
        return col(mid_x + x / scale), row(mid_z + (z - at_z) / scale)
    return Logo(dark, red, to_px)


def cce_wordmark(src, car, entries):
    """CCE's wordmark: the red of texture entries side by side, as soft
    shares, cropped a pixel outside it."""
    _, red = soft_inks(np.concatenate([cce_texture(src, car, e) for e in entries], 1))
    ys, xs = np.nonzero(red > 0.5)
    return np.pad(red, 1)[ys.min():ys.max() + 3, xs.min():xs.max() + 3]


def texel_world(src, tids, ss=FINE):
    """World (x, z) of ss x ss points in every texel of textures tids laid
    side by side (the hood's three), from each one's face in DUSA's body:
    arrays (h, w, ss * ss)."""
    poly = open(os.path.join(src.dusa, 'POLYGON.BIN'), 'rb').read()
    verts, faces = cc.faces(poly, cc.BODY)
    verts = np.array(verts, float) / 65536
    out = []
    for tid in tids:
        attr, idx = next((a, i) for a, t, i in faces if t == tid)
        h, w = cc.TEXTURES[tid][2], cc.TEXTURES[tid][1]
        q = verts[list(idx)][:, [0, 2]]
        off = (np.arange(ss) + 0.5) / ss
        u = ((np.arange(w)[:, None] + off[None]) / w).reshape(-1)
        v = ((np.arange(h)[:, None] + off[None]) / h).reshape(-1)
        if attr & 0x80:
            u = 1 - u
        if attr & 0x40:
            v = 1 - v
        uu, vv = np.meshgrid(u, v)
        p = ((1 - uu) * (1 - vv))[..., None] * q[0] + (uu * (1 - vv))[..., None] * q[1] + \
            (uu * vv)[..., None] * q[2] + ((1 - uu) * vv)[..., None] * q[3]
        p = p.reshape(h, ss, w, ss, 2).transpose(0, 2, 1, 3, 4).reshape(h, w, ss * ss, 2)
        out.append(p)
    return np.concatenate(out, 1)


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


def phoenix(src):
    schemes = (FIREBIRD, EMBER)
    return assemble('Phoenix', src.texpl, [structural_tables(src.texpl, s) for s in schemes],
                    [phoenix_art(src.texpl, s) for s in schemes])


# ---------------------------------------------------------------- the other cars

# Squared racing digits after DUSA's 41: segments of a seven-segment
# figure (top, upper right, lower right, bottom, lower left, upper left,
# middle), the 1 a bar with a flag
SEGMENTS = {'0': 'abcdef', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd', '6': 'afgedc',
            '7': 'abc', '8': 'abcdefg', '9': 'abfgcd'}


def digit(ch, w, h, s):
    """One squared digit, w x h, strokes s wide, outer corners cut."""
    m = blank(w, h)
    mid = h // 2
    lo, hi = mid - s // 2, mid - s // 2 + s
    if ch == '1':
        m[:, w - s - (w - s) // 3:w - (w - s) // 3] = True
        m[:s, w - 2 * s - (w - s) // 3:w - (w - s) // 3] = True
        return m
    rects = {'a': (0, 0, w, s), 'b': (w - s, 0, w, hi), 'c': (w - s, lo, w, h), 'd': (0, h - s, w, h),
             'e': (0, lo, s, h), 'f': (0, 0, s, hi), 'g': (0, lo, w, hi)}
    for seg in SEGMENTS[ch]:
        x0, y0, x1, y1 = rects[seg]
        m[y0:y1, x0:x1] = True
    cut = s // 2 + 1
    for i in range(cut):
        for y, xs in ((i, slice(0, cut - i)), (i, slice(w - cut + i, w)),
                      (h - 1 - i, slice(0, cut - i)), (h - 1 - i, slice(w - cut + i, w))):
            m[y, xs] = False
    return m


def number_mask(text, w, h, dw, dh, s, gap, italic=0.0):
    """A number's digits side by side, centred in w x h, slanted by italic."""
    digits = [digit(ch, dw, dh, s) for ch in text]
    tw = len(digits) * dw + gap * (len(digits) - 1) + int(italic * dh)
    m = blank(tw, dh)
    for k, d in enumerate(digits):
        x = k * (dw + gap)
        for y in range(dh):
            dx = int(italic * (dh - 1 - y))
            m[y, x + dx:x + dx + dw] |= d[y]
    return place(m, w, h)


def u_shape(cx, top, bottom, r_out, r_in, steps=12):
    """A U (a horseshoe): legs from top down to the curve, open at the top."""
    import math
    cy = bottom - r_out
    outer = [(cx - r_out, top)]
    outer += [(cx - r_out * math.cos(math.pi * k / steps), cy + r_out * math.sin(math.pi * k / steps))
              for k in range(steps + 1)]
    outer += [(cx + r_out, top), (cx + r_in, top)]
    inner = [(cx + r_in * math.cos(math.pi * k / steps), cy + r_in * math.sin(math.pi * k / steps))
             for k in range(steps + 1)]
    return outer + inner + [(cx - r_in, top)]


def star(cx, cy, r_out, r_in, points=5):
    import math
    return [(cx + (r_out if k % 2 == 0 else r_in) * math.sin(math.pi * k / points),
             cy - (r_out if k % 2 == 0 else r_in) * math.cos(math.pi * k / points)) for k in range(2 * points)]


class Design:
    """A car's art, the same shapes in every colouring: the hood's emblem
    (polygons in a 100 x 70 design space, details drawn dark on it) over its
    name, or a big name with the emblem behind (word); the number, its
    digits' size and slant; the names on the trunk, quarters and tail."""
    def __init__(self, name, font, number, emblem, details=(), word=False, name_width=60,
                 digits=(19, 40, 7, 3), door_digits=(18, 32, 6, 3), italic=0.0, roof_box=False,
                 trunk_sub='RACING TEAM', name_italic=0.25):
        self.name, self.font, self.number, self.emblem, self.details = name, font, number, emblem, details
        self.word, self.name_width, self.digits, self.door_digits = word, name_width, digits, door_digits
        self.italic, self.roof_box, self.trunk_sub, self.name_italic = italic, roof_box, trunk_sub, name_italic


def standard_art(texpl, s, d):
    """Design d's art textures in scheme s (the Phoenix's layout)."""
    a = s.art
    base = dusa_pixels(texpl)
    out = {}
    name = lambda **k: text_mask(d.name, d.font, italic=d.name_italic, **k)

    hood = canvas(72, 72, s.panel[1])
    if d.word:
        em = place(poly_mask(56, 50, d.emblem, (100, 70)), 72, 72, y=8)
        paint(hood, grow(em), a['emblem_outline'])
        paint(hood, em, place(bands(50, 56, a['emblem']), 72, 72, y=8))
        word = place(name(width=66), 72, 72, y=24)
        outlined(hood, word, a['name'], a['name_outline'])
    else:
        bw, bh, by = 66, 46, 4
        em = place(poly_mask(bw, bh, d.emblem, (100, 70)), 72, 72, y=by)
        paint(hood, grow(em), a['emblem_outline'])
        paint(hood, em, place(bands(bh, bw, a['emblem']), 72, 72, y=by))
        if d.details:
            paint(hood, em & place(poly_mask(bw, bh, d.details, (100, 70)), 72, 72, y=by), a['emblem_detail'])
        word = name(width=d.name_width)
        outlined(hood, place(word, 72, 72, y=min(56, 70 - word.shape[0])), a['name'], a['name_outline'])
    out.update(zip((25, 26, 27), split_cols(hood, (24, 24, 24))))

    roof = canvas(48, 48, s.panel[1])
    if d.roof_box:
        box = blank(48, 48)
        box[3:45, 3:45] = True
        paint(roof, box, a['roof_box'])
    dw, dh, st, gap = d.digits
    num = number_mask(d.number, 48, 48, dw, dh, st, gap, d.italic)
    paint(roof, shift(grow(num, 2), 2, 2), a['shadow'])
    paint(roof, grow(num, 2), a['number_outline'])
    paint(roof, num, bevel(num, *a['number']))
    out[28] = roof

    door = np.concatenate([recoloured(texpl, base, t, s) for t in (37, 38, 39)], 0)
    door[:] = door[:, :2].mean(1, keepdims=True)
    dw, dh, st, gap = d.door_digits
    num = place(number_mask(d.number, 48, dh, dw, dh, st, gap, d.italic), 48, 40, y=3)
    paint(door, shift(grow(num), 2, 1), a['door_shadow'])
    paint(door, grow(num), a['number_outline'])
    paint(door, num, bevel(num, *a['number']))
    out.update(zip((37, 38, 39), split_rows(door, (12, 12, 16))))

    trunk = canvas(80, 40, s.panel[1])
    outlined(trunk, place(name(width=72) if len(d.name) > 3 else name(height=20), 80, 40, y=5),
             a['name'], a['name_outline'])
    paint(trunk, place(text_mask(d.trunk_sub, 'ariblk.ttf', height=6), 80, 40, y=29), a['team'])
    out[29] = trunk

    for tids, widths in (((46, 47, 48), (40, 24, 72)), ((42, 41, 40), (72, 24, 40))):
        cv = canvas(136, 16, s.body[1])
        for y, col in enumerate(a['stripe']):
            cv[y] = col
        outlined(cv, place(name(height=8), 136, 16, y=3), a['side'], a['side_outline'])
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
    outlined(plate, place(name(height=11), 96, 16), a['side'], a['side_outline'])
    out[30], out[31] = spoiler, plate
    return out


def ramp_of(hexstr):
    """A body ramp from its middle colour: a darker and a lighter step."""
    mid = np.array(c(hexstr))
    return (tuple(mid * 0.35), tuple(mid), tuple(np.clip(mid * 0.6 + 0.45, 0, 1)))


def scheme(body, panel, lower, net, emblem, emblem_outline, emblem_detail, name, name_outline,
           number, number_outline, shadow, stripe, side, side_outline, plate, team, roof_box=None,
           door_shadow=None):
    """A colouring, its colours as '#rrggbb' (emblem: bands top to bottom;
    number: fill, light edge, dark edge; stripe: three rows)."""
    cs_ = lambda v: [c(x) for x in v]
    return Scheme(ramp_of(body), ramp_of(panel), ramp_of(lower), c(net),
                  emblem=cs_(emblem), emblem_outline=c(emblem_outline), emblem_detail=c(emblem_detail),
                  name=c(name), name_outline=c(name_outline), number=tuple(cs_(number)),
                  number_outline=c(number_outline), shadow=c(shadow),
                  door_shadow=c(door_shadow or shadow), stripe=cs_(stripe), side=c(side),
                  side_outline=c(side_outline), plate=c(plate), team=c(team),
                  roof_box=c(roof_box or panel))


HORSESHOE = [u_shape(50, 4, 68, 30, 17)]
HORSESHOE_NAILS = [[(x - 2, y - 2), (x + 2, y - 2), (x + 2, y + 2), (x - 2, y + 2)]
                   for x, y in ((26, 18), (25, 34), (74, 18), (75, 34), (34, 56), (66, 56))]
BOLT = [[(58, 0), (24, 40), (46, 40), (34, 70), (78, 26), (56, 26), (72, 0)]]
def ellipse(cx, cy, rx, ry, steps=20):
    import math
    return [(cx + rx * math.cos(2 * math.pi * k / steps), cy + ry * math.sin(2 * math.pi * k / steps))
            for k in range(steps)]


def mirrored(left):
    """A shape symmetric about x = 50 from its left half, top to bottom."""
    return left + [(100 - x, y) for x, y in reversed(left)]


# an oriole perched on a branch, facing right: an orange body, the head
# and wing dark
ORIOLE = [ellipse(48, 40, 26, 15), [(64, 30), (70, 18), (82, 14), (90, 20), (90, 30), (78, 38)],
          [(88, 20), (99, 25), (88, 28)], [(30, 44), (4, 62), (12, 66), (36, 52)],
          [(44, 52), (47, 52), (47, 64), (44, 64)], [(54, 52), (57, 52), (57, 64), (54, 64)],
          [(24, 63), (84, 63), (84, 68), (24, 68)]]
ORIOLE_DETAILS = [[(66, 30), (70, 18), (82, 14), (90, 20), (90, 30), (78, 38)],
                  [(34, 34), (64, 30), (60, 46), (30, 46)], [(30, 44), (4, 62), (12, 66), (36, 52)]]
SHOOTING_STAR = [star(66, 26, 26, 11)] + [
    [(48, 32), (6, 58), (10, 62), (52, 40)], [(52, 40), (16, 70), (22, 70), (56, 46)],
    [(44, 24), (2, 40), (4, 45), (46, 30)]]
# a wolf's head from the front: tall ears, ruffed cheeks, a long muzzle
WOLF = [mirrored([(50, 14), (38, 18), (26, 0), (22, 24), (12, 30), (18, 36), (10, 44), (22, 48), (30, 56),
                  (42, 66), (50, 70)])]
WOLF_DETAILS = [[(28, 30), (44, 36), (42, 40), (30, 37)], [(72, 30), (56, 36), (58, 40), (70, 37)],
                [(44, 60), (56, 60), (50, 68)], [(27, 8), (33, 20), (28, 22)], [(73, 8), (67, 20), (72, 22)],
                [(48, 16), (52, 16), (51, 46), (49, 46)]]
# scales: a stand, a beam, two pans on their cords
SCALES = [[(36, 70), (64, 70), (64, 66), (36, 66)], [(47, 66), (53, 66), (52, 10), (48, 10)],
          [(6, 8), (94, 8), (94, 13), (6, 13)], [(46, 3), (54, 3), (50, 10)],
          [(14, 13), (17, 13), (31, 40), (28, 40)], [(17, 13), (14, 13), (0, 40), (3, 40)],
          [(83, 13), (86, 13), (100, 40), (97, 40)], [(86, 13), (83, 13), (69, 40), (72, 40)],
          [(0, 40), (31, 40), (24, 50), (7, 50)], [(69, 40), (100, 40), (93, 50), (76, 50)]]

DESIGNS = {
    2: Design('GALLOP', 'GILLUBCD.TTF', '27', HORSESHOE, HORSESHOE_NAILS),
    3: Design('MAX', 'impact.ttf', '2', BOLT, word=True, digits=(20, 40, 8, 0), door_digits=(16, 32, 6, 0)),
    5: Design('oriole', 'FORTE.TTF', '16', ORIOLE, ORIOLE_DETAILS, name_width=64, italic=0.2,
              name_italic=0.0, digits=(17, 38, 6, 2), door_digits=(16, 32, 5, 2)),
    6: Design('magic', 'BAUHS93.TTF', '33', SHOOTING_STAR, name_width=58, roof_box=True, name_italic=0.0),
    7: Design('WOLF', 'impact.ttf', '14', WOLF, WOLF_DETAILS, name_width=50, roof_box=True),
    8: Design('Balance', 'ERASBD.TTF', '99', SCALES, name_width=64, italic=0.2, name_italic=0.1,
              digits=(17, 38, 6, 2), door_digits=(16, 32, 5, 2)),
}

# three colourings a car; the user picks two, automatic and manual
CANDIDATES = {
    2: [('Derby: navy, white top, red horseshoe',
         scheme('#102878', '#f0f0f0', '#101830', '#ffffff', ['#ff3030', '#e01010', '#a00000'], '#000000',
                '#202020', '#e01010', '#102878', ['#f0f0f0', '#ffffff', '#a0a0b0'], '#102878', '#e01010',
                ['#ffffff', '#e01010', '#ffffff'], '#ffffff', '#e01010', '#102878', '#102878')),
        ('Silks: white, navy top, gold horseshoe',
         scheme('#f0f0f0', '#102878', '#102878', '#ffd800', ['#fff4a0', '#ffd800', '#c08000'], '#000000',
                '#603000', '#ffd800', '#000000', ['#ffd800', '#fff6a0', '#c08000'], '#000000', '#e01010',
                ['#102878', '#ffd800', '#102878'], '#102878', '#ffd800', '#102878', '#ffd800')),
        ('Rosette: red, white top, navy horseshoe',
         scheme('#c00010', '#f0f0f0', '#101830', '#ffffff', ['#4060d0', '#2040a0', '#102070'], '#000000',
                '#e0e0e0', '#102878', '#ffffff', ['#f0f0f0', '#ffffff', '#a0a0b0'], '#102878', '#102878',
                ['#ffffff', '#102878', '#ffffff'], '#ffffff', '#102878', '#102878', '#c00010'))],
    3: [('Voltage: yellow, white top, red MAX, teal lower',
         scheme('#ffd800', '#f0f0f0', '#00a0a0', '#00c0c0', ['#ffe040', '#ffc000', '#ff8000'], '#000000',
                '#000000', '#e01010', '#000000', ['#202020', '#606060', '#000000'], '#ffd800', '#00a0a0',
                ['#00c0c0', '#ffffff', '#e01010'], '#e01010', '#000000', '#f0f0f0', '#00a0a0')),
        ('Surge: teal, yellow top, red MAX',
         scheme('#00a0a0', '#ffd800', '#101010', '#ffd800', ['#ffffff', '#e0f0ff', '#a0c0e0'], '#000000',
                '#000000', '#e01010', '#000000', ['#ffd800', '#fff6a0', '#c08000'], '#000000', '#000000',
                ['#ffd800', '#e01010', '#ffd800'], '#ffd800', '#000000', '#101010', '#e01010')),
        ('Blackout: black, yellow top, red MAX',
         scheme('#181818', '#ffd800', '#e01010', '#ffd800', ['#ffffff', '#c0f0ff', '#00c0e0'], '#000000',
                '#000000', '#e01010', '#000000', ['#ffd800', '#fff6a0', '#c08000'], '#000000', '#e01010',
                ['#ffd800', '#e01010', '#ffd800'], '#ffd800', '#e01010', '#e01010', '#e01010'))],
    5: [('Songbird: yellow, black lettering, orange bird',
         scheme('#ffd000', '#ffd000', '#ff7000', '#000000', ['#ff9000', '#ff7000', '#e04000'], '#000000',
                '#000000', '#000000', '#ffd000', ['#e01010', '#ff6040', '#900000'], '#000000', '#900000',
                ['#000000', '#ff7000', '#000000'], '#000000', '#ffd000', '#000000', '#e01010')),
        ('Night flight: black, yellow top, orange bird',
         scheme('#181818', '#ffd000', '#ff7000', '#ffd000', ['#ffa000', '#ff7000', '#e04000'], '#000000',
                '#000000', '#000000', '#ffd000', ['#ffd000', '#fff6a0', '#c08000'], '#000000', '#e04000',
                ['#ffd000', '#ff7000', '#ffd000'], '#ffd000', '#000000', '#181818', '#ff7000')),
        ('Sunset: orange, black top, yellow bird',
         scheme('#ff6000', '#181818', '#181818', '#ffd000', ['#fff070', '#ffd000', '#ffa000'], '#000000',
                '#000000', '#ffd000', '#000000', ['#ffd000', '#fff6a0', '#c08000'], '#000000', '#900000',
                ['#ffd000', '#181818', '#ffd000'], '#ffd000', '#000000', '#181818', '#ffd000'))],
    6: [('Spellbook: green top, black sides, fire star',
         scheme('#181818', '#20b020', '#181818', '#20d020', ['#fff070', '#ffb000', '#ff6000', '#e01010'],
                '#000000', '#000000', '#ffffff', '#000000', ['#e01010', '#ff6040', '#900000'], '#ffffff',
                '#000000', ['#20d020', '#ffb000', '#e01010'], '#20d020', '#000000', '#20b020', '#ffffff',
                roof_box='#ffffff')),
        ('Conjurer: purple, green top, gold star',
         scheme('#7020b0', '#20b020', '#301060', '#ffd800', ['#fff4a0', '#ffd800', '#e0a000', '#c06000'],
                '#000000', '#000000', '#ffd800', '#301060', ['#ffd800', '#fff6a0', '#c08000'], '#301060',
                '#000000', ['#ffd800', '#20d020', '#ffd800'], '#ffd800', '#301060', '#7020b0', '#ffd800',
                roof_box='#7020b0')),
        ('Illusion: white, green top, magenta star',
         scheme('#f0f0f0', '#20b020', '#20b020', '#e020a0', ['#ffa0e0', '#ff40c0', '#e020a0', '#a00070'],
                '#000000', '#000000', '#e020a0', '#ffffff', ['#e020a0', '#ff80d0', '#900060'], '#ffffff',
                '#108010', ['#20b020', '#e020a0', '#20b020'], '#e020a0', '#000000', '#20b020', '#ffffff',
                roof_box='#ffffff'))],
    7: [('Pack leader: red, white top, black wolf',
         scheme('#d00010', '#f0f0f0', '#181818', '#ffffff', ['#505058', '#303038', '#181818'], '#000000',
                '#ffffff', '#d00010', '#000000', ['#181818', '#606060', '#000000'], '#d00010', '#606060',
                ['#ffffff', '#181818', '#ffffff'], '#ffffff', '#000000', '#181818', '#d00010',
                roof_box='#ffffff')),
        ('Moonlight: black, red top, silver wolf',
         scheme('#181818', '#d00010', '#d00010', '#e0e0e0', ['#ffffff', '#c0c0c8', '#808088'], '#000000',
                '#d00010', '#ffffff', '#000000', ['#d00010', '#ff6040', '#800000'], '#ffffff', '#000000',
                ['#e0e0e0', '#d00010', '#e0e0e0'], '#e0e0e0', '#000000', '#d00010', '#ffffff',
                roof_box='#181818')),
        ('Timber: grey, red top, black wolf',
         scheme('#9898a0', '#d00010', '#303038', '#d00010', ['#505058', '#303038', '#181818'], '#000000',
                '#ffd800', '#ffffff', '#000000', ['#ffffff', '#ffffff', '#a0a0b0'], '#d00010', '#303038',
                ['#d00010', '#ffffff', '#d00010'], '#d00010', '#000000', '#303038', '#ffffff',
                roof_box='#d00010'))],
    8: [('Scales: white, orange lower, red 99',
         scheme('#f0f0f0', '#f0f0f0', '#ff7000', '#ff7000', ['#ffa040', '#ff7000', '#d04000'], '#000000',
                '#000000', '#000000', '#f0f0f0', ['#e01010', '#ff6040', '#900000'], '#000000', '#a0a0b0',
                ['#ff7000', '#000000', '#ff7000'], '#000000', '#ffffff', '#f0f0f0', '#ff7000')),
        ('Equinox: orange, white top, navy scales',
         scheme('#ff7000', '#f0f0f0', '#102878', '#ffffff', ['#4060d0', '#2040a0', '#102070'], '#000000',
                '#000000', '#102878', '#ffffff', ['#102878', '#4060d0', '#000040'], '#ffffff', '#a0a0b0',
                ['#ffffff', '#102878', '#ffffff'], '#ffffff', '#102878', '#102878', '#102878')),
        ('Counterweight: navy, white top, orange scales',
         scheme('#102878', '#f0f0f0', '#ff7000', '#ff7000', ['#ffa040', '#ff7000', '#d04000'], '#000000',
                '#000000', '#102878', '#ffffff', ['#ff7000', '#ffb070', '#a04000'], '#000000', '#a0a0b0',
                ['#ff7000', '#ffffff', '#ff7000'], '#ff7000', '#000000', '#102878', '#ff7000'))],
}


def candidates(texpl, car):
    """Car's candidate colourings, each a paint with that colouring in
    both liveries (for previews; a car's chosen pair goes in NINETY_FIVE)."""
    d = DESIGNS[car]
    out = []
    for label, s in CANDIDATES[car]:
        out.append(assemble(f'{d.name} {label}', texpl, [structural_tables(texpl, s)] * 2,
                            [standard_art(texpl, s, d)] * 2))
    return out


# ---------------------------------------------------------------- CCE's art, DUSA's numbers

NUMBER_FONT = 'FRAHVIT.TTF'             # Franklin Gothic Heavy Italic, nearest CCE's own numbers
NOSE_PX = 600                           # fine pixels a unit of the lettering across the nose


class Borrowed:
    """A car's art taken from its CCE paint: the hood logo (the part of CCE's
    car from above inside logo = x0, x1, z0, z1, its dark parts down to
    logo_dark_z0) and where it goes on DUSA's hood (its middle's z, and how
    big against CCE's), the wordmark (texture entries side by side), and the
    number, drawn in NUMBER_FONT."""
    def __init__(self, car, number, logo, logo_dark_z0, logo_z, logo_scale, wordmark):
        self.car, self.number, self.logo, self.logo_dark_z0 = car, number, logo, logo_dark_z0
        self.logo_z, self.logo_scale, self.wordmark = logo_z, logo_scale, wordmark


def lettering(cv, m, fill, outline, shadow=None):
    """A fine mask onto texture cv, with a one-texel outline and (shadow) the
    outline's shadow a texel down and right."""
    edge = fine_grown(m, FINE)
    if shadow is not None:
        blend(cv, coverage(shift(edge, FINE, FINE)), shadow)
    blend(cv, coverage(edge), outline)
    blend(cv, coverage(m), fill)


def borrowed_art(src, s, d):
    """Design d's art textures in scheme s: CCE's logo on the hood with CCE's
    wordmark across the nose, the number on the roof (on a glow as DUSA's
    rivals have theirs) and the doors, the wordmark on the trunk, the rear
    quarters and the tail."""
    a = s.art
    base = dusa_pixels(src.texpl)
    out = {}
    logo = cce_logo(src, d.car, *d.logo, d.logo_dark_z0)
    wordmark = cce_wordmark(src, d.car, d.wordmark)

    world = texel_world(src, (25, 26, 27))
    hood = canvas(72, 72, s.panel[1])
    for m, colour in ((logo.dark, a['logo']), (logo.red, a['logo_red'])):
        blend(hood, world_cover(m, lambda x, z: logo.to_px(x, z, d.logo_z, d.logo_scale), world), colour)
    # the wordmark across the nose, 1.1 units wide, read from in front
    edge_w = round(0.022 * NOSE_PX)
    word = np.pad(drawn_up(wordmark, round(1.1 * NOSE_PX)), 3 * edge_w)
    wh, ww = word.shape
    edge = fine_grown(word, edge_w)

    def nose(x, z):
        return x * NOSE_PX + ww / 2, wh / 2 - (z + 2.12) * NOSE_PX
    for m, colour in ((shift(edge, edge_w, edge_w), a['word_shadow']), (edge, a['word_outline']),
                      (word, a['word'])):
        blend(hood, world_cover(m, nose, world), colour)
    out.update(zip((25, 26, 27), split_cols(hood, (24, 24, 24))))

    roof = glow(48, 48, 23.5, 23.5, 32, a['roof'])
    lettering(roof, fine_place(font_mask(d.number, NUMBER_FONT, 30, 42), 48, 48), a['number'], a['number_outline'])
    out[28] = roof

    door = np.concatenate([recoloured(src.texpl, base, t, s) for t in (37, 38, 39)], 0)
    door[:] = door[:, :2].mean(1, keepdims=True)
    lettering(door, fine_place(font_mask(d.number, NUMBER_FONT, 22, 40), 48, 40, y=5), a['number'],
              a['number_outline'], a['door_shadow'])
    out.update(zip((37, 38, 39), split_rows(door, (12, 12, 16))))

    trunk = canvas(80, 40, s.panel[1])
    lettering(trunk, fine_place(drawn_up(wordmark, 72 * FINE), 80, 40, y=6), a['word'], a['word_outline'],
              a['word_shadow'])
    for y, col in enumerate(a['stripe']):
        trunk[30 + 2 * y:32 + 2 * y] = col
    out[29] = trunk

    side = drawn_up(wordmark, h=8 * FINE)
    for tids, widths in (((46, 47, 48), (40, 24, 72)), ((42, 41, 40), (72, 24, 40))):
        cv = canvas(136, 16, s.body[1])
        for y, col in enumerate(a['stripe']):
            cv[y] = col
        lettering(cv, fine_place(side, 136, 16, y=5), a['side'], a['side_outline'])
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
    lettering(plate, fine_place(drawn_up(wordmark, h=11 * FINE), 96, 16), a['side'], a['side_outline'])
    out[30], out[31] = spoiler, plate
    return out


def shades(hexstr, n=6, low=0.62):
    """A glow's steps from the colour at its edge down to low times it at its centre."""
    col = np.array(c(hexstr))
    return [tuple(col * (1 - (1 - low) * k / (n - 1))) for k in range(n)]


def borrowed_scheme(body, panel, lower, net, logo, logo_red, word, word_outline, word_shadow, roof,
                    number, number_outline, door_shadow, stripe, side, side_outline, plate):
    """A colouring of borrowed art, its colours as '#rrggbb' (roof: the glow's
    edge colour; stripe: three rows)."""
    return Scheme(ramp_of(body), ramp_of(panel), ramp_of(lower), c(net),
                  logo=c(logo), logo_red=c(logo_red), word=c(word), word_outline=c(word_outline),
                  word_shadow=c(word_shadow), roof=shades(roof), number=c(number),
                  number_outline=c(number_outline), door_shadow=c(door_shadow),
                  stripe=[c(x) for x in stripe], side=c(side), side_outline=c(side_outline), plate=c(plate))


# CCE's Gallop: the horseshoe and its red bars from the hood, the wordmark
# from the trunk (46, 48, 50)
GALLOP_95 = Borrowed(2, '27', (-0.5, 0.5, -1.97, -1.1), -2.16, -1.48, 1.1, (46, 48, 50))

DERBY = borrowed_scheme('#102878', '#f0f0f0', '#101830', '#ffffff', '#000000', '#e01010', '#e01010',
                        '#000000', '#a0a0b0', '#102878', '#ffffff', '#000000', '#000000',
                        ['#ffffff', '#e01010', '#ffffff'], '#ffffff', '#000000', '#102878')
SILKS = borrowed_scheme('#f0f0f0', '#102878', '#102878', '#ffd800', '#ffd800', '#e01010', '#ffd800',
                        '#000000', '#000830', '#f0f0f0', '#e01010', '#102878', '#a0a0b0',
                        ['#102878', '#ffd800', '#102878'], '#102878', '#ffd800', '#102878')
ROSETTE = borrowed_scheme('#c00010', '#f0f0f0', '#101830', '#ffffff', '#102878', '#e01010', '#102878',
                          '#000000', '#a0a0b0', '#f0f0f0', '#102878', '#ffffff', '#600000',
                          ['#ffffff', '#102878', '#ffffff'], '#ffffff', '#102878', '#102878')

BORROWED_CANDIDATES = {
    2: [('Derby: navy, white top, black horseshoe', DERBY),
        ('Silks: white, navy top, gold horseshoe', SILKS),
        ('Rosette: red, white top, navy horseshoe', ROSETTE)],
}


def borrowed_candidates(src, car):
    out = []
    for label, s in BORROWED_CANDIDATES[car]:
        out.append(assemble(f'Gallop {label}', src.texpl, [structural_tables(src.texpl, s)] * 2,
                            [borrowed_art(src, s, GALLOP_95)] * 2))
    return out


def gallop95(src):
    """The '95 Gallop: Derby automatic, Rosette manual (the user's pick)."""
    schemes = (DERBY, ROSETTE)
    return assemble("Gallop '95", src.texpl, [structural_tables(src.texpl, s) for s in schemes],
                    [borrowed_art(src, s, GALLOP_95) for s in schemes])


# CCE's cars with a '95 livery: car number (from 1) -> its paint
NINETY_FIVE = {2: gallop95, 4: phoenix}


# ---------------------------------------------------------------- preview

def main():
    sys.path.insert(0, os.path.dirname(__file__))
    import car_sheet as cs
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    src = Sources(dusa, cce)
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    _, faces = cc.faces(poly, cc.BODY)
    base = cs.dusa_mesh(dusa, False)
    paints = [gallop(src.texpl)] + [f(src) for f in NINETY_FIVE.values()]
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
