"""ULTIMATE in place of CIRCUIT EDITION under the main menu's logo: rewrite
the strip of CCE's menu picture in DAYTONA/TITLED.BIN and DAYTONA/LOGO2.DAT.

usage: menu_subtitle.py <cce extracted dir> <out dir> [--word ULTIMATE] [--sheet <png>]
  Run after tools/menu_title.py, which writes <out dir>/DAYTONA/TITLED.BIN;
  the picture's bytes there are checked to be CCE's (or already these).
  --word takes letters this file draws (GLYPHS); --sheet saves the strip
  before and after, twice the size.

The picture (docs/menu_subtitle.md): 704 x 448, 8 x 8 chars of 256
colours, then a long holding the chars' size (0x18140), then the map, a
word a cell (the char number, 32-byte units), 88 x 56, then the palette,
256 colours. The menu shows it on NBG0, interlaced; TITLED.BIN holds it at
its start, LOGO2.DAT (the XBAND modem's start, BKUP.BIN 06028054) at
0x11A84.

CIRCUIT EDITION is 15 letters spread from x 23.6 to 667.3, their fill
13.46 lines tall from y 199.3: maroon, a white keyline 2.4 wide, a soft
dark shadow down and to the right, all softened. Its letters were measured
(the I for the style, then U, T, E and N for their shapes) and the word
is drawn the same way, from signed distances to each letter's outline,
eight samples a pixel each way: L, M and A are new, in the same strokes
(stems 6.4, bars 3.45, the E's rounded corner on the L, the N's diagonals
on the M and the A). The new letters are spread over the same span, with
equal gaps, as CCE spread its own, and the TM goes. Each pixel is the
nearest of the colours CCE's strip already uses; the palette is unchanged.

Before the word goes in, the old one comes out: the strip's grey where it
was, and the logo's white keyline rebuilt where the O of DAYTONA dips
into the strip (each pixel near the logo's black takes the keyline's
colour at its distance, measured on the keyline beside it). The four cell
rows the strip touches (24-27) are cut again: a cell equal to one already
in the picture is shared, a new one takes the place of a cell that only
the old strip used.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

W, H = 88, 56
SIZE_AT, MAP_AT, PAL_AT = 0x18140, 0x18144, 0x1A7C4
PICTURE_END = PAL_AT + 512
LOGO2_AT = 0x11A84
CELL_ROWS = range(24, 28)
BG = 81                                   # the strip's grey, (152, 152, 152)

SS = 8                                    # samples a pixel each way
STYLE = dict(ro=2.4, sx=0.787, sy=1.012, sg=-0.3, ss=0.588, sigma=0.484, halo=1.0,
             halo_col=(120, 120, 120), white=(248, 248, 240), maroon=(136, 6, 22))
DY, HC = 199.325, 13.46                   # the fill's top and height
S, B = 6.4, 3.45                          # the new letters' stems and bars
DIAG = 4.96                               # the N's diagonal, square to its slope
LEFT, RIGHT = 23.6, 667.3                 # CIRCUIT EDITION's fill, C to N
OUT = 20                                  # how far an open cut runs past its letter: a cut
                                          # ending nearer than the keyline closes it in white


# --- letters: (width, [('+' | '-', polygon)]) with y down from the fill's top

def arc(cx, cy, r, a0, a1, n=12):
    a = np.radians(np.linspace(a0, a1, n))
    return [(cx + r * np.cos(t), cy + r * np.sin(t)) for t in a]


def rrect(x0, y0, x1, y1, tl=0, tr=0, br=0, bl=0):
    p = arc(x0 + tl, y0 + tl, tl, 180, 270) if tl else [(x0, y0)]
    p += arc(x1 - tr, y0 + tr, tr, 270, 360) if tr else [(x1, y0)]
    p += arc(x1 - br, y1 - br, br, 0, 90) if br else [(x1, y1)]
    p += arc(x0 + bl, y1 - bl, bl, 90, 180) if bl else [(x0, y1)]
    return p


def glyph_U():                            # measured
    w = 24.07
    return w, [('+', rrect(0, 0, w, HC, br=5.41, bl=5.41)), ('-', rrect(6.14, -OUT, w - 6.14, HC - 3.47, br=3.47, bl=3.47))]


def glyph_I():                            # measured
    return 6.42, [('+', rrect(0, 0, 6.42, HC))]


def glyph_T():                            # measured
    w = 24.12
    return w, [('+', rrect(0, 0, w, 3.25)), ('+', rrect((w - 6.66) / 2, 0, (w + 6.66) / 2, HC))]


def glyph_E():                            # measured
    w, g, y1, y2 = 22.18, 1.45, 4.17, 9.2
    return w, [('+', rrect(0, 0, w, HC, tl=6.52, bl=6.52)),
               ('-', rrect(7.97, y1 - g / 2, w + OUT, y1 + g / 2)), ('-', rrect(7.97, y2 - g / 2, w + OUT, y2 + g / 2))]


def glyph_N():                            # measured
    w, s, t = 25.14, 6.34, 8.02
    return w, [('+', rrect(0, 0, s, HC)), ('+', rrect(w - s, 0, w, HC)), ('+', [(0, 0), (t, 0), (w, HC), (w - t, HC)])]


def glyph_L():                            # the E's spine and corner, a bar
    w = 20.0
    return w, [('+', rrect(0, 0, w, HC, bl=6.52)), ('-', rrect(S, -OUT, w + OUT, HC - B))]


def glyph_M():                            # stems, and diagonals of the N's stroke meeting at the baseline
    w = 31.0
    c, t = w / 2, DIAG
    for _ in range(8):                    # the diagonal's width across, for its slope
        t = DIAG * np.hypot(1, (c - t / 2) / HC)
    return w, [('+', rrect(0, 0, S, HC)), ('+', rrect(w - S, 0, w, HC)),
               ('+', [(0, 0), (t, 0), (c + t / 2, HC), (c - t / 2, HC)]),
               ('+', [(w - t, 0), (w, 0), (c + t / 2, HC), (c - t / 2, HC)])]


def glyph_A():                            # legs of the N's diagonal stroke, a flat top, a bar
    w, top, bar = 26.0, 8.0, 7.0
    run = (w - top) / 2
    k = run / HC
    leg = DIAG * np.hypot(1, k)
    inner = lambda y: (run - k * y + leg, w - run + k * y - leg)
    apex = max(B, (2 * run + 2 * leg - w) / (2 * k))     # where the legs' inner edges part
    a, b, c, d = inner(apex), inner(bar), inner(bar + B), inner(HC + OUT)
    return w, [('+', [(run, 0), (w - run, 0), (w, HC), (0, HC)]),
               ('-', [(a[0], apex), (a[1], apex), (b[1], bar), (b[0], bar)]),
               ('-', [(c[0], bar + B), (c[1], bar + B), (d[1], HC + OUT), (d[0], HC + OUT)])]


GLYPHS = {'U': glyph_U, 'I': glyph_I, 'T': glyph_T, 'E': glyph_E, 'N': glyph_N,
          'L': glyph_L, 'M': glyph_M, 'A': glyph_A}


# --- drawing

def sdf_poly(X, Y, poly):
    """Signed distance to a closed polygon, negative inside."""
    P = np.asarray(poly, dtype=np.float64)
    d2 = np.full(X.shape, np.inf)
    inside = np.zeros(X.shape, dtype=bool)
    for (ax, ay), (bx, by) in zip(P, np.roll(P, -1, axis=0)):
        ex, ey = bx - ax, by - ay
        t = np.clip(((X - ax) * ex + (Y - ay) * ey) / max(ex * ex + ey * ey, 1e-12), 0, 1)
        d2 = np.minimum(d2, (X - ax - t * ex) ** 2 + (Y - ay - t * ey) ** 2)
        if ay != by:
            inside ^= ((ay > Y) != (by > Y)) & (X < ex * (Y - ay) / ey + ax)
    d = np.sqrt(d2)
    return np.where(inside, -d, d)


def sdf(X, Y, parts):
    d = np.full(X.shape, np.inf)
    for op, poly in parts:
        e = sdf_poly(X, Y, poly)
        d = np.minimum(d, e) if op == '+' else np.maximum(d, -e)
    return d


def gauss(a, sigma):
    r = int(np.ceil(sigma * 3))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a = np.apply_along_axis(np.convolve, 0, a, k, mode='same')
    return np.apply_along_axis(np.convolve, 1, a, k, mode='same')


def draw(base, parts, gx, gy, width, p=STYLE):
    """Composite one letter onto the picture's colours, in place."""
    x0, y0 = int(np.floor(gx)) - 8, int(np.floor(gy)) - 8
    w, h = int(np.ceil(width)) + 17, int(np.ceil(HC)) + 17
    X, Y = np.meshgrid(x0 + (np.arange(w * SS) + 0.5) / SS, y0 + (np.arange(h * SS) + 0.5) / SS)
    d = sdf(X - gx, Y - gy, parts)
    ds = sdf(X - gx - p['sx'], Y - gy - p['sy'], parts)
    pool = lambda a: a.reshape(h, SS, w, SS).mean(axis=(1, 3))
    fill = gauss(pool((d < 0).astype(float)), p['sigma'])
    key = gauss(pool((d < p['ro']).astype(float)), p['sigma'])
    shadow = gauss(pool((ds < p['ro'] + p['sg']).astype(float)), p['ss'])
    c = base[y0:y0 + h, x0:x0 + w]
    for cov, col in ((shadow * p['halo'], p['halo_col']), (key, p['white']), (fill, p['maroon'])):
        c += (np.array(col, float) - c) * cov[..., None]


def layout(word):
    letters = [GLYPHS[ch]() for ch in word]
    gap = (RIGHT - LEFT - sum(w for w, _ in letters)) / (len(letters) - 1)
    x, out = LEFT, []
    for w, parts in letters:
        out.append((parts, round(x * SS) / SS, w))
        x += w + gap
    return out, gap


# --- the picture

def load(data):
    assert struct.unpack_from('>I', data, SIZE_AT)[0] == SIZE_AT
    m = np.array(struct.unpack_from(f'>{W * H}H', data, MAP_AT), dtype=np.int64).reshape(H, W)
    pal = struct.unpack_from('>256H', data, PAL_AT)
    rgb = np.array([((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in pal], dtype=float)
    img = np.zeros((H * 8, W * 8), dtype=np.uint8)
    for cy in range(H):
        for cx in range(W):
            o = m[cy, cx] * 32
            img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = np.frombuffer(data[o:o + 64], dtype=np.uint8).reshape(8, 8)
    return m, rgb, img


def erase(img, rgb):
    """The picture's colours with the old strip and its TM taken out."""
    A = rgb[img]
    red = np.clip((A[..., 0] - A[..., 1]) / 128.0, 0, 1)
    mask = np.zeros(img.shape, bool)
    for y, x in zip(*np.nonzero(red[197:219] > 0.12)):
        mask[max(y + 197 - 5, 197):y + 197 + 6, max(x - 5, 0):x + 6] = True
    mask[195:206, 672:692] = True                         # the TM, its keyline under the A of USA
    black = (A.max(axis=2) < 60) & ~mask
    black[:180] = False
    dist = np.full(img.shape, np.inf)                     # to the logo's black, up to 4 away
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            moved = np.zeros_like(black)
            moved[max(dy, 0):H * 8 + min(dy, 0), max(dx, 0):W * 8 + min(dx, 0)] = \
                black[max(-dy, 0):H * 8 - max(dy, 0), max(-dx, 0):W * 8 - max(dx, 0)]
            dist = np.where(moved, np.minimum(dist, np.hypot(dy, dx)), dist)

    # the logo's keyline by distance from its black, from the unmasked pixels beside the strip
    bins = {}
    for y in range(190, 201):
        for x in range(704):
            if not mask[y, x] and not black[y, x] and dist[y, x] <= 3.5:
                bins.setdefault(int(dist[y, x] * 2), []).append(A[y, x])
    profile = {k: np.mean(v, axis=0) for k, v in bins.items()}

    out = A.copy()
    lum = A.mean(axis=2)
    for y in range(195, 219):
        x = 0
        while x < 704:
            if not mask[y, x]:
                x += 1
                continue
            e = x
            while e < 704 and mask[y, e]:
                e += 1
            l, r = x - 1, min(e, 703)
            for i in range(x, e):
                d = dist[y, i] if y <= 200 else np.inf
                if d <= 3.5 and int(d * 2) in profile:
                    out[y, i] = profile[int(d * 2)]
                elif abs(lum[y, l] - lum[y, r]) <= 24:
                    f = (i - l) / (r - l)
                    out[y, i] = A[y, l] * (1 - f) + A[y, r] * f
                else:
                    out[y, i] = A[y, l] if abs(lum[y, l] - 152) < abs(lum[y, r] - 152) else A[y, r]
            x = e
    return out


def quantize(colours, img, rgb):
    """Rows 192-223 as indices: each changed pixel the nearest colour the old
    strip used, the rest as they were."""
    allowed = np.unique(img[197:219, 16:696])
    block = colours[192:224]
    d = ((block[..., None, :] - rgb[allowed][None, None]) ** 2).sum(-1)
    changed = np.abs(block - rgb[img[192:224]]).max(axis=-1) > 0.5
    out = img.copy()
    out[192:224] = np.where(changed, allowed[d.argmin(-1)], img[192:224])
    return out


def recut(data, m, img):
    """The picture's chars and map with cell rows 24-27 cut from img again."""
    chars = bytearray(data[:SIZE_AT])
    known = {}
    for cy in range(H):
        for cx in range(W):
            if cy not in CELL_ROWS:
                n = int(m[cy, cx])
                known.setdefault(bytes(chars[n * 32:n * 32 + 64]), n)
    old = {int(m[cy, cx]) for cy in CELL_ROWS for cx in range(W)} - set(known.values())
    kept = {bytes(chars[n * 32:n * 32 + 64]): n for n in old}     # the strip rows' own cells, by content
    cells = {(cy, cx): img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].tobytes() for cy in CELL_ROWS for cx in range(W)}
    place = {c: known.get(c, kept.get(c)) for c in set(cells.values())}
    free = sorted(old - set(place.values()))
    fresh = 0
    for c in sorted(c for c, n in place.items() if n is None):
        if not free:
            sys.exit('error: the strip needs more cells than the old one freed')
        place[c] = free.pop(0)
        chars[place[c] * 32:place[c] * 32 + 64] = c
        fresh += 1
    for n in free:                                        # cells nothing shows any more
        chars[n * 32:n * 32 + 64] = bytes(64)
    new_m = m.copy()
    for (cy, cx), c in cells.items():
        new_m[cy, cx] = place[c]
    out = bytearray(data[:PICTURE_END])
    out[:SIZE_AT] = chars
    out[MAP_AT:MAP_AT + W * H * 2] = struct.pack(f'>{W * H}H', *new_m.flatten().tolist())
    return bytes(out), fresh, len(free)


def put(path, at, original, picture):
    data = bytearray(open(path, 'rb').read())
    if data[at:at + PICTURE_END] not in (original, picture):
        sys.exit(f'error: {path} does not hold CCE\'s menu picture at {at:#x}')
    data[at:at + PICTURE_END] = picture
    open(path, 'wb').write(data)


def main():
    args = sys.argv[1:]
    word, sheet = 'ULTIMATE', None
    if '--word' in args:
        i = args.index('--word')
        word = args.pop(i + 1)
        args.pop(i)
    if '--sheet' in args:
        i = args.index('--sheet')
        sheet = args.pop(i + 1)
        args.pop(i)
    cce, dst = args
    titled = open(os.path.join(cce, 'DAYTONA', 'TITLED.BIN'), 'rb').read()
    original = titled[:PICTURE_END]
    m, rgb, img = load(original)

    colours = erase(img, rgb)
    letters, gap = layout(word)
    for parts, gx, w in letters:
        draw(colours, parts, gx, DY, w)
    new_img = quantize(colours, img, rgb)
    picture, used, left = recut(original, m, new_img)
    _, _, check = load(picture)
    assert (check == new_img).all()

    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    out_titled = os.path.join(dst, 'DAYTONA', 'TITLED.BIN')
    if not os.path.exists(out_titled):
        open(out_titled, 'wb').write(titled)
    put(out_titled, 0, original, picture)
    out_logo2 = os.path.join(dst, 'DAYTONA', 'LOGO2.DAT')
    open(out_logo2, 'wb').write(open(os.path.join(cce, 'DAYTONA', 'LOGO2.DAT'), 'rb').read())
    put(out_logo2, LOGO2_AT, original, picture)

    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in ['DAYTONA/LOGO2.DAT', 'DAYTONA/TITLED.BIN'] if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))

    if sheet:
        strip = lambda a: rgb[a[176:232]].astype(np.uint8)
        both = np.concatenate([strip(img), np.zeros((4, 704, 3), np.uint8), strip(new_img)])
        Image.fromarray(both).resize((704 * 2, both.shape[0] * 2), Image.NEAREST).save(sheet)
    print(f'menu subtitle: {word} under the logo, gaps of {gap:.1f}; {used} new cells, '
          f'{left} of the old strip\'s cleared; TITLED.BIN and LOGO2.DAT')


if __name__ == '__main__':
    main()
