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
and paints the art textures afresh at their own size, borrowed from the
car's CCE paint (its logo traced, its wordmark) with a number from a font,
drawn smooth and anti-aliased.
"""
import colorsys
import functools
import math
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


def canvas(w, h, colour):
    out = np.zeros((h, w, 3))
    out[:] = colour
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


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32


def glow(w, h, cx, cy, r, colours):
    """A round glow from colours[-1] at the centre out to colours[0], in
    steps blended with a 4 x 4 ordered dither."""
    yy, xx = np.mgrid[0:h, 0:w]
    return steps(1 - np.clip(np.hypot(xx - cx, yy - cy) / r, 0, 1), colours)


def steps(t, colours):
    """t (h x w, 0-1) through colours in steps, blended with a 4 x 4
    ordered dither."""
    h, w = t.shape
    n = len(colours) - 1
    v = t * n
    lo = np.floor(v).astype(int)
    th = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    return np.array(colours)[np.clip(lo + (v - lo > th), 0, n)]


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


def coverage(fine, k=1):
    """A fine mask -> each texel's share of it (k: each of k x k parts of a
    texel's, for art drawn k times finer)."""
    h, w = fine.shape
    n = FINE // k
    return fine.reshape(h // n, n, w // n, n).mean((1, 3))


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


def traced(mask, sigma, round_below=0, drop_below=0):
    """A mask's shapes traced to outlines, each smoothed along its length
    (sigma pixels) and filled again; those smaller than round_below square
    pixels become ellipses (a logo's holes), and shapes (not holes) smaller
    than drop_below are left out (specks cut off at the logo's edge)."""
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
        if fill and cv2.contourArea(contours[i]) < drop_below:
            continue
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
    """A CCE logo traced from its car seen from above: inks, masks in the
    order drawn, each by the scheme colour it takes; or (a glow) its shape,
    filled with a glow from core, its brightest middle, out to reach pixels;
    and to_px(x, z, at_z, scale), DUSA world -> their pixels for the logo's
    middle put on the car's middle at z = at_z, scale times its size."""
    def __init__(self, to_px, inks=(), shape=None, core=None, reach=None):
        self.to_px, self.inks, self.shape, self.core, self.reach = to_px, inks, shape, core, reach


def cce_logo(src, car, d):
    """Design d's logo, inside d.logo = x0, x1, z0, z1 on CCE's car (DUSA's
    frame), as d.logo_kind takes it: 'dark red', its dark and red inks, the
    dark down to d.logo_dark_z0 (the Gallop's horseshoe runs on under the
    nose lettering); 'glow', its shape, all it draws lit on a black hood (the
    Phoenix's fireball); 'match', its pixels nearest each of d.logo_inks
    ((CCE colour, scheme colour) pairs) rather than d.logo_ground; 'vector',
    d.logo_inks as (outline, scheme colour) pairs, each outline (x, z)
    points on CCE's car, drawn in order. Traced
    smooth, small holes made round and, when d.symmetric, made symmetric
    about its own middle, which CCE draws a little off the car's."""
    x0, x1, z0, z1 = d.logo
    img, (cx, cz) = cce_top(src, car)
    h, w = img.shape[:2]
    texel = TOP_PX / CCE_TEXELS

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

    def smooth(m):
        return cv2.GaussianBlur(m, (0, 0), texel / 2)

    def mirror(m, axis):
        return symmetric(m, axis) if d.symmetric else m

    out = {}
    if d.logo_kind == 'glow':
        lit = smooth(np.clip((img.max(-1) - 0.2) / 0.2, 0, 1)) * inside(z0)
        axis = mirror_axis(lit, col(0))
        out['shape'] = traced(mirror(lit, axis), 0.7 * texel, drop_below=(4 * texel) ** 2)
        rows, _ = np.nonzero((img.max(-1) > 0.9) & (img[..., 2] > 0.4) & (inside(z0) > 0))
        out['core'] = (axis, rows.mean())
        # its steps reach out to its widest, so its narrow end is the edge colour
        out['reach'] = np.nonzero(out['shape'].any(0))[0].max() - axis
    elif d.logo_kind == 'vector':
        axis = col(0)
        out['inks'] = []
        for outline, key in d.logo_inks:
            m = np.zeros((h, w), np.uint8)
            pts = np.array([(col(x), row(z)) for x, z in outline])
            cv2.fillPoly(m, [np.round(pts * 16).astype(np.int32)], 1, shift=4)
            out['inks'].append((m.astype(bool), key))
    elif d.logo_kind == 'match':
        refs = np.array([c(x) for x, _ in d.logo_inks] + [c(x) for x in d.logo_ground])
        near = np.linalg.norm(img[..., None, :] - refs, axis=-1).argmin(-1)
        masks = [smooth((near == k).astype(float)) * inside(z0) for k in range(len(d.logo_inks))]
        axis = mirror_axis(sum(masks), col(0)) if d.symmetric else col(0)
        out['inks'] = [(traced(mirror(m, axis), 0.6 * texel, drop_below=(3 * texel) ** 2), key)
                       for m, (_, key) in zip(masks, d.logo_inks)]
    else:
        dark, red = (smooth(m) for m in soft_inks(img))
        dark, red = dark * inside(d.logo_dark_z0), red * inside(z0)
        axis = mirror_axis(dark, col(0))
        out['inks'] = [(traced(mirror(dark, axis), 0.7 * texel, round_below=(7 * texel) ** 2), 'logo'),
                       (traced(mirror(red, axis), 0.5 * texel), 'logo_red')]
    mid_x, mid_z = -((axis - w / 2) / TOP_PX + cx), (z0 + z1) / 2

    def to_px(x, z, at_z, scale):
        return col(mid_x + x / scale), row(mid_z + (z - at_z) / scale)
    return Logo(to_px, **out)


HOOD_PX = 2 * CCE_TEXELS                # pixels a unit of a wordmark taken from CCE's hood


def cce_wordmark(src, car, where, ink='red'):
    """CCE's wordmark as soft shares, cropped a pixel outside it, from rows
    of texture entries side by side; or (where = ('hood', x0, x1, z0, z1))
    the part of its car from above inside that rectangle, turned to read
    from in front of the car and smoothed as cce_logo does, at HOOD_PX, less
    the bits of other paint its edges cut; or (('font', text, font file))
    lettering in a font, for a wordmark CCE draws too broken to take. Its
    ink: its red; every coloured pixel ('colour', for letters shaded in
    pinks inside a white outline, the Phoenix's); its dark ('dark') or its
    whites and light greys ('light')."""
    if where[0] == 'font':
        _, text, font = where
        big = 200
        f = ImageFont.truetype(os.path.join(FONTS, font), big)
        im = Image.new('L', (len(text) * big * 2, big * 3), 0)
        ImageDraw.Draw(im).text((big // 2, big // 2), text, fill=255, font=f)
        return np.pad(np.asarray(im.crop(im.getbbox())).astype(float) / 255, 1)
    if where[0] == 'hood':
        _, x0, x1, z0, z1 = where
        img, (cx, cz) = cce_top(src, car)
        h, w = img.shape[:2]
        c0, c1 = sorted(int(round(w / 2 + TOP_PX * (-x - cx))) for x in (x0, x1))
        r0, r1 = sorted(int(round(h / 2 + TOP_PX * (z - cz))) for z in (z0, z1))
        part = cv2.GaussianBlur(img, (0, 0), TOP_PX / CCE_TEXELS / 2)[r0:r1, c0:c1][::-1, ::-1]
        rgb = cv2.resize(part, (round((c1 - c0) * HOOD_PX / TOP_PX), round((r1 - r0) * HOOD_PX / TOP_PX)),
                         interpolation=cv2.INTER_AREA)
    else:
        rgb = np.concatenate([np.concatenate([cce_texture(src, car, e) for e in row], 1) for row in where])
    v, lo = rgb.max(-1), rgb.min(-1)
    sat = (v - lo) / np.maximum(v, 1e-6)
    if ink == 'red':
        _, m = soft_inks(rgb)
    elif ink == 'colour':
        m = np.clip((v - 0.25) / 0.2, 0, 1) * np.clip((sat - 0.15) / 0.1, 0, 1)
    elif ink == 'dark':
        m = np.clip((0.4 - v) / 0.2, 0, 1)
    else:
        m = np.clip((v - 0.45) / 0.2, 0, 1) * np.clip((0.35 - sat) / 0.15, 0, 1)
    if where[0] == 'hood':
        n, labels, stats, _ = cv2.connectedComponentsWithStats((m > 0.5).astype(np.uint8))
        biggest = stats[1:, cv2.CC_STAT_AREA].max()
        for k in range(1, n):
            x, y, bw, bh, area = stats[k]
            if area < biggest / 20 and (x == 0 or y == 0 or x + bw == m.shape[1] or y + bh == m.shape[0]):
                m[labels == k] = 0
    ys, xs = np.nonzero(m > 0.5)
    return np.pad(m, 1)[ys.min():ys.max() + 3, xs.min():xs.max() + 3]


def fitted(soft, w, h):
    """drawn_up as big as fits in w x h texels, in proportion."""
    sh, sw = soft.shape
    return drawn_up(soft, w * FINE) if sh * w / sw <= h else drawn_up(soft, h=h * FINE)


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


# ---------------------------------------------------------------- CCE's art, DUSA's numbers

NUMBER_FONT = 'FRAHVIT.TTF'             # Franklin Gothic Heavy Italic, nearest CCE's own numbers
NOSE_PX = 600                           # fine pixels a unit of the lettering across the nose


class Borrowed:
    """A car's art taken from its CCE paint: the number (in NUMBER_FONT);
    the wordmark (where and ink as cce_wordmark takes them),
    its width and middle's z across the hood (nose), and the lettering for
    the rear quarters and the plate when the wordmark won't read that small
    (small: (text, font), else the wordmark); and the hood logo, if any: the
    part of CCE's car from above inside logo = x0, x1, z0, z1, taken as
    cce_logo does by logo_kind, put on DUSA's hood with its middle at z =
    logo_z, logo_scale times its size."""
    def __init__(self, car, number, wordmark, wordmark_ink='red', nose=(1.1, -2.12), small=None,
                 logo=None, logo_z=-1.48, logo_scale=1.1, logo_kind='dark red', logo_dark_z0=None,
                 logo_inks=(), logo_ground=(), symmetric=True):
        self.car, self.number, self.wordmark, self.wordmark_ink = car, number, wordmark, wordmark_ink
        self.nose, self.small, self.logo, self.logo_z, self.logo_scale = nose, small, logo, logo_z, logo_scale
        self.logo_kind, self.logo_dark_z0, self.logo_inks = logo_kind, logo_dark_z0, logo_inks
        self.logo_ground, self.symmetric = logo_ground, symmetric


def lettering(cv, m, fill, outline, shadow=None, k=1):
    """A fine mask onto texture cv (k times finer than the game's), with a
    one-texel outline and (shadow) the outline's shadow a texel down and
    right."""
    edge = fine_grown(m, FINE)
    if shadow is not None:
        blend(cv, coverage(shift(edge, FINE, FINE), k), shadow)
    blend(cv, coverage(edge, k), outline)
    blend(cv, coverage(m, k), fill)


def finer(world, k):
    """texel_world's points regrouped for textures k times finer: each of a
    texel's k x k parts with the points inside it."""
    h, w, n, _ = world.shape
    ss = round(n ** 0.5)
    q = ss // k
    return world.reshape(h, w, k, q, k, q, 2).transpose(0, 2, 1, 4, 3, 5, 6).reshape(h * k, w * k, q * q, 2)


def upscaled(img, k):
    """A texture k times bigger, each texel k x k."""
    return np.repeat(np.repeat(img, k, 0), k, 1)


def borrowed_art(src, s, d, k=1):
    """Design d's art textures in scheme s: CCE's logo on the hood with CCE's
    wordmark across the nose, the number on the roof (on a glow as DUSA's
    rivals have theirs) and the doors, the wordmark on the trunk, the rear
    quarters and the tail. k: drawn k times finer than the game's textures
    (for car select's pictures, tools/car_pictures.py)."""
    a = s.art
    base = dusa_pixels(src.texpl)
    out = {}
    logo = cce_logo(src, d.car, d) if d.logo else Logo(None)
    wordmark = cce_wordmark(src, d.car, d.wordmark, d.wordmark_ink)

    world = finer(texel_world(src, (25, 26, 27)), k)
    hood = canvas(72 * k, 72 * k, s.panel[1])

    def logo_px(x, z):
        return logo.to_px(x, z, d.logo_z, d.logo_scale)
    if logo.shape is not None:
        # outlined, filled with a glow from its core in steps, as CCE's
        blend(hood, world_cover(fine_grown(logo.shape, 0.022 * TOP_PX / d.logo_scale), logo_px, world),
              a['logo_outline'])
        col, row = logo_px(*world.mean(2).transpose(2, 0, 1))
        fire = steps(np.clip(np.hypot(col - logo.core[0], row - logo.core[1]) / logo.reach, 0, 1),
                     a['logo_glow'])
        cover = world_cover(logo.shape, logo_px, world)[..., None]
        hood[:] = hood * (1 - cover) + fire * cover
    for m, key in logo.inks:
        blend(hood, world_cover(m, logo_px, world), a[key])
    # the wordmark across the nose, read from in front
    nose_w, nose_z = d.nose
    edge_w = round(0.022 * NOSE_PX)
    word = np.pad(drawn_up(wordmark, round(nose_w * NOSE_PX)), 3 * edge_w)
    wh, ww = word.shape
    edge = fine_grown(word, edge_w)

    def nose(x, z):
        return x * NOSE_PX + ww / 2, wh / 2 - (z - nose_z) * NOSE_PX
    for m, colour in ((shift(edge, edge_w, edge_w), a['word_shadow']), (edge, a['word_outline']),
                      (word, a['word'])):
        blend(hood, world_cover(m, nose, world), colour)
    out.update(zip((25, 26, 27), split_cols(hood, (24 * k,) * 3)))

    roof = glow(48 * k, 48 * k, (48 * k - 1) / 2, (48 * k - 1) / 2, 32 * k, a['roof'])
    lettering(roof, fine_place(font_mask(d.number, NUMBER_FONT, 30, 42), 48, 48), a['number'], a['number_outline'],
              k=k)
    out[28] = roof

    door = upscaled(np.concatenate([recoloured(src.texpl, base, t, s) for t in (37, 38, 39)], 0), k)
    door[:] = door[:, :2 * k].mean(1, keepdims=True)
    lettering(door, fine_place(font_mask(d.number, NUMBER_FONT, 22, 40), 48, 40, y=5), a['number'],
              a['number_outline'], a['door_shadow'], k=k)
    out.update(zip((37, 38, 39), split_rows(door, (12 * k, 12 * k, 16 * k))))

    trunk = canvas(80 * k, 40 * k, s.panel[1])
    lettering(trunk, fine_place(fitted(wordmark, 72, 22), 80, 40, y=6), a['word'], a['word_outline'],
              a['word_shadow'], k=k)
    for y, col in enumerate(a['stripe']):
        trunk[k * (30 + 2 * y):k * (32 + 2 * y)] = col
    out[29] = trunk

    small = (lambda h: font_mask(*d.small, h)) if d.small else (lambda h: drawn_up(wordmark, h=h * FINE))
    side = small(8)
    for tids, widths in (((46, 47, 48), (40, 24, 72)), ((42, 41, 40), (72, 24, 40))):
        cv = canvas(136 * k, 16 * k, s.body[1])
        for y, col in enumerate(a['stripe']):
            cv[k * y:k * (y + 1)] = col
        lettering(cv, fine_place(side, 136, 16, y=5), a['side'], a['side_outline'], k=k)
        for tid, part in zip(tids, split_cols(cv, [k * w for w in widths])):
            out[tid] = part[:base[tid].shape[0] * k]
    for tid in (43, 49):
        cv = canvas(64 * k, 12 * k, s.body[1])
        for y, col in enumerate(a['stripe']):
            cv[k * y:k * (y + 1)] = col
        out[tid] = cv

    spoiler = canvas(96 * k, 8 * k, s.body[1])
    spoiler[2 * k:4 * k] = a['stripe'][1]
    plate = canvas(96 * k, 16 * k, a['plate'])
    lettering(plate, fine_place(small(11), 96, 16), a['side'], a['side_outline'], k=k)
    out[30], out[31] = spoiler, plate
    return out


BLACK_RAMP = (c('#000000'), c('#141418'), c('#40404c'))
RED_RAMP = (c('#300000'), c('#c00010'), c('#ff5040'))


def ramp_of(hexstr):
    """A body ramp from its middle colour: a darker and a lighter step."""
    mid = np.array(c(hexstr))
    return (tuple(mid * 0.35), tuple(mid), tuple(np.clip(mid * 0.6 + 0.45, 0, 1)))


def shades(hexstr, n=6, low=0.62):
    """A glow's steps from the colour at its edge down to low times it at its centre."""
    col = np.array(c(hexstr))
    return [tuple(col * (1 - (1 - low) * k / (n - 1))) for k in range(n)]


def borrowed_scheme(body, panel, lower, net, word, word_outline, word_shadow, roof, number,
                    number_outline, door_shadow, stripe, side, side_outline, plate, logo_glow=None,
                    logo_outline=None, **inks):
    """A colouring of borrowed art, its colours as '#rrggbb'; body, panel
    and lower are a middle colour or a (dark, mid, light) ramp; roof is the
    glow's edge colour, stripe three rows; the logo's colours as its kind
    takes them: its inks by name (inks) or its glow (logo_glow, core to
    edge) and outline."""
    def body_ramp(x):
        return ramp_of(x) if isinstance(x, str) else x

    def opt(x):
        return None if x is None else c(x)
    return Scheme(body_ramp(body), body_ramp(panel), body_ramp(lower), c(net),
                  word=c(word), word_outline=c(word_outline),
                  word_shadow=c(word_shadow), roof=shades(roof), number=c(number),
                  number_outline=c(number_outline), door_shadow=c(door_shadow),
                  stripe=[c(x) for x in stripe], side=c(side), side_outline=c(side_outline), plate=c(plate),
                  logo_glow=logo_glow and [c(x) for x in logo_glow], logo_outline=opt(logo_outline),
                  **{k: c(v) for k, v in inks.items()})


# CCE's Gallop: the horseshoe and its red bars from the hood, the wordmark
# from the trunk (46, 48, 50)
GALLOP_95 = Borrowed(2, '27', ((46, 48, 50),), logo=(-0.5, 0.5, -1.97, -1.1), logo_dark_z0=-2.16)

DERBY = borrowed_scheme(
    '#102878', '#f0f0f0', '#101830', '#ffffff', word='#e01010', word_outline='#000000',
    word_shadow='#a0a0b0', roof='#102878', number='#ffffff', number_outline='#000000', door_shadow='#000000',
    stripe=['#ffffff', '#e01010', '#ffffff'], side='#ffffff', side_outline='#000000', plate='#102878',
    logo='#000000', logo_red='#e01010')
SILKS = borrowed_scheme(
    '#f0f0f0', '#102878', '#102878', '#ffd800', word='#ffd800', word_outline='#000000',
    word_shadow='#000830', roof='#f0f0f0', number='#e01010', number_outline='#102878', door_shadow='#a0a0b0',
    stripe=['#102878', '#ffd800', '#102878'], side='#102878', side_outline='#ffd800', plate='#102878',
    logo='#ffd800', logo_red='#e01010')
ROSETTE = borrowed_scheme(
    '#c00010', '#f0f0f0', '#101830', '#ffffff', word='#102878', word_outline='#000000',
    word_shadow='#a0a0b0', roof='#f0f0f0', number='#102878', number_outline='#ffffff', door_shadow='#600000',
    stripe=['#ffffff', '#102878', '#ffffff'], side='#ffffff', side_outline='#102878', plate='#102878',
    logo='#102878', logo_red='#e01010')

# CCE's Phoenix: the fireball from the hood (the bar across its tail
# left black), the wordmark from the trunk (43, 45, 47 over 44, 46, 48)
PHOENIX_95 = Borrowed(4, '8', ((43, 45, 47), (44, 46, 48)), wordmark_ink='colour', nose=(0.85, -2.12),
                      small=('PHOENIX', 'impact.ttf'), logo=(-0.45, 0.45, -2.085, -1.21), logo_z=-1.44,
                      logo_scale=0.95, logo_kind='glow')
FIRE = ['#fff070', '#ffd000', '#ff9000', '#f05000', '#c01800']
GOLD = ['#fff4a0', '#ffe040', '#ffd000', '#f0a000', '#c06800']
LOWER_RED = (c('#300000'), c('#a00808'), c('#f04020'))

FIREBIRD_95 = borrowed_scheme(
    BLACK_RAMP, BLACK_RAMP, LOWER_RED, '#ffd800', word='#ff2010', word_outline='#ffd000',
    word_shadow='#600000', roof='#141418', number='#ffd800', number_outline='#a01000', door_shadow='#a01000',
    stripe=['#ffd000', '#ff8000', '#e02000'], side='#ffd000', side_outline='#a01000', plate='#141418',
    logo_glow=FIRE, logo_outline='#ffd000')
EMBER_95 = borrowed_scheme(
    RED_RAMP, BLACK_RAMP, BLACK_RAMP, '#ffd800', word='#ffd800', word_outline='#c00010',
    word_shadow='#000000', roof='#141418', number='#ffd800', number_outline='#c00010', door_shadow='#500000',
    stripe=['#ffd000', '#c00010', '#ffd000'], side='#ffd800', side_outline='#000000', plate='#101010',
    logo_glow=GOLD, logo_outline='#c00010')
SOLAR_95 = borrowed_scheme(
    '#f0b800', BLACK_RAMP, BLACK_RAMP, '#ff2010', word='#ff2010', word_outline='#ffd000',
    word_shadow='#600000', roof='#141418', number='#ff2010', number_outline='#000000', door_shadow='#805000',
    stripe=['#141418', '#ff2010', '#141418'], side='#141418', side_outline='#ff2010', plate='#f0b800',
    logo_glow=FIRE, logo_outline='#ffd000')

# The other five, from their CCE paint, their wordmarks from CCE's hood,
# where they are biggest (Magic's in Bookman, near its serif, which CCE
# draws broken at every size). Max, Oriole and Wolf have no hood logo:
# their wordmark goes big across the hood, as CCE has it.
MAX_95 = Borrowed(3, '2', ('hood', -0.78, 0.78, -2.26, -1.85), nose=(1.15, -1.7))
ORIOLE_95 = Borrowed(5, '16', ('hood', -0.78, 0.78, -2.26, -1.55), wordmark_ink='dark', nose=(1.15, -1.7))


def five_pointed(x, z, r, turn):
    """A regular five-pointed star's outline on the car (x, z): its middle,
    its points r from it, the first turned `turn` degrees from straight ahead."""
    t = math.radians(turn) + np.arange(10) * math.pi / 5
    rad = np.where(np.arange(10) % 2, r * (3 - math.sqrt(5)) / 2, r)    # inner points: r / golden ratio^2
    return tuple(zip(x - rad * np.sin(t), z - rad * np.cos(t)))


# Magic's stars: three regular five-pointed stars, red behind orange behind
# yellow, each fitted to the part CCE's hood shows of it seen from above;
# CCE's wordmark covers their tops, so a trace cut them off
MAGIC_STARS = (
    (five_pointed(-0.0596, -1.8295, 0.6042, 35.72), 'logo_red'),
    (five_pointed(0.1197, -1.9004, 0.4643, 35.65), 'logo_orange'),
    (five_pointed(0.3029, -1.9554, 0.3058, 33.00), 'logo_yellow'),
)
MAGIC_LO, MAGIC_HI = (f([p for outline, _ in MAGIC_STARS for p in outline], 0) for f in (np.min, np.max))
MAGIC_95 = Borrowed(6, '33', ('font', 'magic', 'BOOKOSB.TTF'), nose=(0.8, -2.15),
                    logo=(MAGIC_LO[0], MAGIC_HI[0], MAGIC_LO[1], MAGIC_HI[1]), logo_z=-1.39, logo_scale=0.9,
                    logo_kind='vector', logo_inks=MAGIC_STARS)
WOLF_95 = Borrowed(7, '41', ('hood', -0.78, 0.78, -2.19, -1.7), wordmark_ink='light', nose=(1.0, -1.65),
                   small=('Wolf', 'ariblk.ttf'))
# Balance's orange triangle (the A of its wordmark), half as big again
BALANCE_95 = Borrowed(8, '99', ('hood', -0.8, 0.8, -2.22, -1.62), wordmark_ink='dark', nose=(1.05, -1.95),
                      logo=(-0.2, 0.4, -1.85, -1.5), logo_z=-1.55, logo_scale=1.6, logo_kind='match',
                      logo_inks=(('#f06810', 'logo'),), logo_ground=('#ffffff', '#000000', '#a0a0a0'))

SPEARMINT = borrowed_scheme(
    '#007878', '#f0f0f0', '#004040', '#ffffff', word='#e01010', word_outline='#000000',
    word_shadow='#a0a0b0', roof='#007878', number='#ffffff', number_outline='#000000', door_shadow='#003030',
    stripe=['#ffffff', '#e01010', '#ffffff'], side='#ffffff', side_outline='#e01010', plate='#007878')
POLAR = borrowed_scheme(
    '#f0f0f0', '#007878', '#007878', '#e01010', word='#ffffff', word_outline='#e01010',
    word_shadow='#003030', roof='#f0f0f0', number='#e01010', number_outline='#007878', door_shadow='#a0a0b0',
    stripe=['#007878', '#e01010', '#007878'], side='#007878', side_outline='#ffffff', plate='#007878')
CITRUS = borrowed_scheme(
    '#e8d000', '#007878', '#004040', '#e01010', word='#e01010', word_outline='#ffffff',
    word_shadow='#003030', roof='#007878', number='#ffffff', number_outline='#000000', door_shadow='#806800',
    stripe=['#007878', '#e01010', '#007878'], side='#007878', side_outline='#ffffff', plate='#007878')

CANARY = borrowed_scheme(
    '#f0c800', '#f0c800', '#202020', '#000000', word='#141418', word_outline='#f0c800',
    word_shadow='#a08000', roof='#f0c800', number='#e01010', number_outline='#000000', door_shadow='#806000',
    stripe=['#141418', '#e01010', '#141418'], side='#141418', side_outline='#f0c800', plate='#141418')
NIGHTJAR = borrowed_scheme(
    BLACK_RAMP, '#f0c800', BLACK_RAMP, '#f0c800', word='#141418', word_outline='#f0c800',
    word_shadow='#a08000', roof='#f0c800', number='#e01010', number_outline='#000000', door_shadow='#000000',
    stripe=['#f0c800', '#e01010', '#f0c800'], side='#f0c800', side_outline='#000000', plate='#f0c800')
ROBIN = borrowed_scheme(
    '#f06000', '#f0c800', '#202020', '#000000', word='#141418', word_outline='#f0c800',
    word_shadow='#a08000', roof='#f0c800', number='#141418', number_outline='#ffffff', door_shadow='#802000',
    stripe=['#141418', '#f0c800', '#141418'], side='#141418', side_outline='#f0c800', plate='#141418')

STAR = dict(logo_red='#e01010', logo_orange='#ff8030', logo_yellow='#ffd800')
EMERALD = borrowed_scheme(
    '#00a040', '#f0f0f0', '#004818', '#ffffff', word='#00a040', word_outline='#000000',
    word_shadow='#a0a0b0', roof='#00a040', number='#e01010', number_outline='#ffffff', door_shadow='#004818',
    stripe=['#ffffff', '#e01010', '#ffffff'], side='#ffffff', side_outline='#00a040', plate='#00a040', **STAR)
CONJURER = borrowed_scheme(
    BLACK_RAMP, '#00a040', BLACK_RAMP, '#00c050', word='#ffffff', word_outline='#000000',
    word_shadow='#004818', roof='#00a040', number='#ffffff', number_outline='#e01010', door_shadow='#000000',
    stripe=['#00a040', '#ffd800', '#00a040'], side='#00a040', side_outline='#000000', plate='#00a040', **STAR)
JESTER = borrowed_scheme(
    '#6020a0', '#00a040', '#280848', '#ffd800', word='#ffffff', word_outline='#000000',
    word_shadow='#004818', roof='#00a040', number='#ffd800', number_outline='#280848', door_shadow='#280848',
    stripe=['#ffd800', '#00a040', '#ffd800'], side='#ffd800', side_outline='#280848', plate='#6020a0', **STAR)

TIMBER = borrowed_scheme(
    '#d01020', '#f0f0f0', '#500008', '#ffffff', word='#d01020', word_outline='#000000',
    word_shadow='#a0a0b0', roof='#d01020', number='#ffffff', number_outline='#000000', door_shadow='#500008',
    stripe=['#ffffff', '#141418', '#ffffff'], side='#ffffff', side_outline='#000000', plate='#d01020')
GREY_WOLF = borrowed_scheme(
    '#808890', '#d01020', '#303438', '#ffffff', word='#ffffff', word_outline='#000000',
    word_shadow='#500008', roof='#d01020', number='#141418', number_outline='#ffffff', door_shadow='#303438',
    stripe=['#d01020', '#ffffff', '#d01020'], side='#ffffff', side_outline='#d01020', plate='#d01020')
MIDNIGHT = borrowed_scheme(
    BLACK_RAMP, '#d01020', BLACK_RAMP, '#d01020', word='#ffffff', word_outline='#000000',
    word_shadow='#500008', roof='#d01020', number='#ffffff', number_outline='#000000', door_shadow='#000000',
    stripe=['#d01020', '#ffffff', '#d01020'], side='#d01020', side_outline='#000000', plate='#d01020')

SCALES = borrowed_scheme(
    '#f0f0f0', '#f0f0f0', '#f06810', '#f06810', word='#141418', word_outline='#ffffff',
    word_shadow='#a0a0b0', roof='#f0f0f0', number='#e01010', number_outline='#000000', door_shadow='#a0a0b0',
    stripe=['#f06810', '#141418', '#f06810'], side='#141418', side_outline='#f06810', plate='#f06810',
    logo='#f06810')
TANGERINE = borrowed_scheme(
    '#f06810', '#f0f0f0', '#602000', '#ffffff', word='#141418', word_outline='#ffffff',
    word_shadow='#a0a0b0', roof='#f0f0f0', number='#f06810', number_outline='#000000', door_shadow='#602000',
    stripe=['#ffffff', '#141418', '#ffffff'], side='#ffffff', side_outline='#141418', plate='#141418',
    logo='#f06810')
INKWELL = borrowed_scheme(
    BLACK_RAMP, '#f0f0f0', BLACK_RAMP, '#f06810', word='#141418', word_outline='#ffffff',
    word_shadow='#a0a0b0', roof='#f0f0f0', number='#f06810', number_outline='#000000', door_shadow='#000000',
    stripe=['#f06810', '#ffffff', '#f06810'], side='#f06810', side_outline='#000000', plate='#f06810',
    logo='#f06810')

BORROWED_DESIGNS = {2: GALLOP_95, 3: MAX_95, 4: PHOENIX_95, 5: ORIOLE_95, 6: MAGIC_95, 7: WOLF_95, 8: BALANCE_95}
BORROWED_CANDIDATES = {
    2: [('Derby: navy, white top, black horseshoe', DERBY),
        ('Silks: white, navy top, gold horseshoe', SILKS),
        ('Rosette: red, white top, navy horseshoe', ROSETTE)],
    4: [('Firebird: black, a fireball, red PHOENIX, yellow 8', FIREBIRD_95),
        ('Ember: red sides, black top, a gold fireball and 8', EMBER_95),
        ('Solar: yellow sides, black top, a fireball, red 8', SOLAR_95)],
    3: [('Spearmint: teal, white top, red MAX', SPEARMINT),
        ('Polar: white, teal top, white MAX', POLAR),
        ('Citrus: yellow, teal top, red MAX', CITRUS)],
    5: [('Canary: yellow all over, black oriole, red 16', CANARY),
        ('Nightjar: black, yellow top, red 16', NIGHTJAR),
        ('Robin: orange, yellow top, black 16', ROBIN)],
    6: [('Emerald: green, white top, the star, red 33', EMERALD),
        ('Conjurer: black, green top, the star, white 33', CONJURER),
        ('Jester: purple, green top, the star, yellow 33', JESTER)],
    7: [('Timber: red, white top, red Wolf, white 41', TIMBER),
        ('Grey Wolf: grey, red top, white Wolf, black 41', GREY_WOLF),
        ('Midnight: black, red top, white Wolf, white 41', MIDNIGHT)],
    8: [('Scales: white, orange lower body, black Balance, red 99', SCALES),
        ('Tangerine: orange, white top, orange 99', TANGERINE),
        ('Inkwell: black, white top, orange 99', INKWELL)],
}


def borrowed_candidates(src, car):
    """Each candidate colouring of car's borrowed art, the same in both
    liveries (for previews; a car's chosen pair goes in NINETY_FIVE)."""
    return [assemble(label, src.texpl, [structural_tables(src.texpl, s)] * 2,
                     [borrowed_art(src, s, BORROWED_DESIGNS[car])] * 2)
            for label, s in BORROWED_CANDIDATES[car]]


# The user's picks (2026-10-29): car -> name, automatic, manual
PICKS = {
    2: ("Gallop '95", DERBY, ROSETTE),
    3: ("Max '95", SPEARMINT, CITRUS),
    4: ("Phoenix '95", FIREBIRD_95, EMBER_95),
    5: ("Oriole '95", NIGHTJAR, ROBIN),
    6: ("Magic '95", EMERALD, CONJURER),
    7: ("Wolf '95", TIMBER, MIDNIGHT),
    8: ("Balance '95", SCALES, INKWELL),
}


def ninety_five_art(car, src, k):
    """Car's '95 art textures drawn k times finer, for its car-select
    picture: (automatic, manual), each texture id -> colours."""
    _, *schemes = PICKS[car]
    return [borrowed_art(src, s, BORROWED_DESIGNS[car], k) for s in schemes]


def ninety_five(car, src):
    """Car's '95 paint, its picked automatic and manual colourings."""
    name, *schemes = PICKS[car]
    return assemble(name, src.texpl, [structural_tables(src.texpl, s) for s in schemes],
                    [borrowed_art(src, s, BORROWED_DESIGNS[car]) for s in schemes])


# CCE's cars with a '95 livery: car number (from 1) -> its paint
NINETY_FIVE = {car: functools.partial(ninety_five, car) for car in PICKS}


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
