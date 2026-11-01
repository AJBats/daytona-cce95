"""The in-car view's hood pictures for the cars on DUSA's body: each '95
car in its livery and DUSA's own car in its paint, in both gearboxes'
colours (docs/hoods.md).

usage: hoods.py <dusa extracted dir> <cce extracted dir> <out dir>
  Writes HOOD<n><A|M><1|2>P.BIN for car n (a '95 car's number from 1, or
  9 for DUSA's car), automatic or manual, one or two players, under
  <out dir>/DAYTONA, and lists them in PATCHED.txt. The pictures take a
  few minutes; they are kept in build/hoods and rendered again only when
  what they are made from changes.

CCE's in-car view lays a picture of the car's hood over the bottom of the
3D view, and with one player the dashboard under it: VDP2 cells, a file a
car (HORNET.BIN, PHENIX2P.BIN, ...; patches/hoods.s names them). A file is
a header (a count, then each part's size and destination), 8 x 8 chars of
256 colours, a map of one-word names (the char x 2) 44 cells wide, and the
colours. The map holds four pictures: the hood whole, crumpled on both
sides, on the left, and on the right (0602E7EC picks one by the car's
damage bits, +0x128). One player's are 14 rows of cells: the hood above
the cowl, the dashboard below it. Two players' are the same pictures' top
7 rows, the hood alone, in at most 127 colours: the load adds 128 to
player 2's.

CCE's pictures are renders of each car's hood in its paint. Ours render
DUSA's body in a '95 paint the same way, with the camera CCE's were made
with: fitted to CCE's own model and pictures (CAMERA). Seen from above
with its paint on, the body's front is a height field, smoothed a little
(SMOOTH) so DUSA's flat panels read curved as CCE's renders do, and each
line of sight is followed to where it meets the field. The paint is the
car-select pictures' art, four times finer than the car's textures, with
its glows blended evenly rather than dithered: the dither the car's 16
colours need breaks up into grit on a hood this close. The light was
fitted to four of CCE's pictures (LIGHT). Crumpled hoods add zigzag folds
across the front (crumple), the same folds for every car. Below the cowl
the dashboard is CCE's, taken from the car's own file, colours and all;
the hood gets the rest of the palette.
"""
import math
import os
import struct
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import car_convert as cc  # noqa: E402
import car_pictures as cp  # noqa: E402
import liveries  # noqa: E402

# CCE's hood files, by car from 0 (the secret car's last)
CCE_FILES = ['HORNET', 'GALLOP', 'MAX', 'PHENIX', 'ORIOLE', 'MAGIC', 'WOLF', 'BALANCE', 'OLD_DAYT']
CCE_2P = {'BALANCE': 'BALANC2P', 'OLD_DAYT': 'OLD_DAY2'}
COLS, ROWS_1P, ROWS_2P = 44, 14, 7
W, H = 8 * COLS, 8 * ROWS_1P
CHARS_AT, MAP_AT, COLOURS_AT = 0x25E42000, 0x002F2CC0, 0x25F00600
MAX_CHARS_1P = 0x19300 // 64            # CCE's largest (HORNET.BIN)
MAX_CHARS_2P = 0xF600 // 64             # each player's room in VRAM (06033CBE)

# Fitted to CCE's pictures with CCE's own model (flat texture colours):
# the eye above the ground and ahead of the car's middle, pitched down, the
# lens and the horizon's line (negative: above the picture). x across the
# car, y up, z toward the tail.
CAMERA = dict(height=1.284, z=-0.318, pitch=math.radians(10.486), lens=232.76, cx=W / 2, cy=-15.01)
# Light from the front left, low; ambient, diffuse, highlight, shine, and a
# darkening at grazing angles (all fitted on the Gallop, Oriole, Phoenix and
# Hornet pictures).
LIGHT = dict(azimuth=-0.6181, elevation=0.3873, ambient=0.4408, diffuse=0.8332,
             specular=0.4211, shine=64.16, grazing=0.4808)
SMOOTH = 0.04                           # units of blur over the body's top
RES = 0.0025                            # units a cell of the height field, finer than the art's texels
FIELD_X, FIELD_Z = (-0.95, 0.95), (-2.6, -0.4)
OUTSIDE = 0.3                           # the field's height off the body
NOSE = -2.46
SS = 4                                  # rays a pixel, each way
# the four pictures: the sides crumpled, each with its folds' seed (the
# right's alone the left's mirrored)
DAMAGE = ((), (('left', 1), ('right', 3)), (('left', 2),), (('right', 2),))
ART_SCALE = 4                           # the '95 art drawn this many times finer


# ---------------------------------------------------------------- CCE's files

def read_hood(path):
    """(chars, map words, colour words) of a hood file."""
    d = open(path, 'rb').read()
    n = struct.unpack_from('>I', d, 0)[0]
    parts, o = [], 4 + 8 * n
    for i in range(n):
        size, _ = struct.unpack_from('>II', d, 4 + 8 * i)
        parts.append(d[o:o + size])
        o += size
    chars, mp, colours = parts
    return chars, struct.unpack('>%dH' % (len(mp) // 2), mp), struct.unpack('>%dH' % (len(colours) // 2), colours)


def pictures(chars, words, rows):
    """The map's four pictures as colour indices, rows x 8 lines each."""
    out = []
    for f in range(4):
        img = np.zeros((rows * 8, W), np.uint8)
        for r in range(rows):
            for c in range(COLS):
                ch = (words[(f * rows + r) * COLS + c] & 0xFFF) * 32
                img[r * 8:r * 8 + 8, c * 8:c * 8 + 8] = np.frombuffer(chars[ch:ch + 64], np.uint8).reshape(8, 8)
        out.append(img)
    return out


def word_rgb(w):
    return np.array([w & 31, (w >> 5) & 31, (w >> 10) & 31], float) / 31


def rgb_word(c):
    r, g, b = (int(round(v * 31)) for v in np.clip(c, 0, 1))
    return r | g << 5 | b << 10


def cowl_line(cce):
    """The first dashboard line in every column: where CCE's eight cars'
    whole hoods stop differing and their pictures stay alike for 12 lines
    (the cowl, the same on all). Found that way the line is ragged: a
    column where the hoods happen to look alike for a line ends late. So
    it is a smooth curve along the lowest of those lines (a line lower
    shows the hood's paint past CCE's, where ours has less of it)."""
    pics = []
    for name in CCE_FILES[:8]:
        chars, words, colours = read_hood(os.path.join(cce, 'DAYTONA', name + '.BIN'))
        pal = np.array([word_rgb(w) for w in colours])
        pics.append(pal[pictures(chars, words, ROWS_1P)[0]])
    alike = np.array(pics).std(0).max(-1) < 0.06
    top = np.zeros(W)
    for x in range(W):
        for y in range(H - 12):
            if alike[y:y + 12, x].all():
                top[x] = y
                break
    x = np.arange(W)
    keep = np.ones(W, bool)
    for _ in range(4):                  # fit, drop the points above the curve, again
        curve = np.polyval(np.polyfit(x[keep], top[keep], 4), x)
        keep = top <= curve + 0.5
    return np.round(curve).astype(int)


# ---------------------------------------------------------------- rendering

def body_mesh(poly, tex):
    """DUSA's body's quads (corners, colours, pixels, transparent, h flip,
    v flip) with textures tex, glass left out; its vertices."""
    vo, nv, fo, nf = cc.BODY
    verts = np.array([struct.unpack_from('>iii', poly, vo + 12 * i) for i in range(nv)], float) / 65536
    verts *= [-1, 1, 1]
    quads = []
    for i in range(nf):
        f = struct.unpack_from('>iiiHHHHHH', poly, fo + 24 * i)
        attr, tid, idx = f[3], f[4], f[5:9]
        if tid == cc.WINDOW_TEX:
            continue
        col, px = tex[tid]
        quads.append((idx, col, px, bool(attr & 0x10), bool(attr & 0x80), bool(attr & 0x40)))
    return verts, quads


def top_view(verts, quads, n=8):
    """The body from above on the field's grid: (colour, top's height,
    covered), rows along z from the nose, columns along x."""
    xs = np.arange(*FIELD_X, RES) + RES / 2
    zs = np.arange(*FIELD_Z, RES) + RES / 2
    h, w = len(zs), len(xs)
    col = np.zeros((h, w, 3))
    top = np.full((h, w), -np.inf)
    uu, vv = np.meshgrid(np.linspace(0, 1, n + 1), np.linspace(0, 1, n + 1))
    w4 = np.stack([(1 - uu) * (1 - vv), uu * (1 - vv), uu * vv, (1 - uu) * vv], -1)
    for idx, c, px, transparent, hflip, vflip in quads:
        p = w4 @ verts[list(idx)]
        gx = (p[..., 0] - FIELD_X[0]) / RES
        gz = (p[..., 2] - FIELD_Z[0]) / RES
        gy = p[..., 1]
        th, tw = px.shape
        for j in range(n):
            for k in range(n):
                for tri in (((j, k), (j, k + 1), (j + 1, k + 1)), ((j, k), (j + 1, k + 1), (j + 1, k))):
                    X, Z, Y, us, ws = (np.array([q[t] for t in tri]) for q in (gx, gz, gy, uu, vv))
                    x0, x1 = max(0, math.floor(X.min())), min(w - 1, math.ceil(X.max()))
                    z0, z1 = max(0, math.floor(Z.min())), min(h - 1, math.ceil(Z.max()))
                    det = (X[1] - X[0]) * (Z[2] - Z[0]) - (X[2] - X[0]) * (Z[1] - Z[0])
                    if x1 < x0 or z1 < z0 or abs(det) < 1e-9:
                        continue
                    ax, az = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(z0, z1 + 1) + 0.5)
                    l1 = ((ax - X[0]) * (Z[2] - Z[0]) - (X[2] - X[0]) * (az - Z[0])) / det
                    l2 = ((X[1] - X[0]) * (az - Z[0]) - (ax - X[0]) * (Z[1] - Z[0])) / det
                    l0 = 1 - l1 - l2
                    m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
                    y = l0 * Y[0] + l1 * Y[1] + l2 * Y[2]
                    u = l0 * us[0] + l1 * us[1] + l2 * us[2]
                    v = l0 * ws[0] + l1 * ws[1] + l2 * ws[2]
                    if hflip:
                        u = 1 - u
                    if vflip:
                        v = 1 - v
                    tx = np.clip((u * tw).astype(int), 0, tw - 1)
                    ty = np.clip((v * th).astype(int), 0, th - 1)
                    if transparent:
                        m &= px[ty, tx] != 0
                    win = top[z0:z1 + 1, x0:x1 + 1]
                    m &= y > win
                    if m.any():
                        win[m] = y[m]
                        sample = bilinear(c, np.clip(u * tw - 0.5, 0, tw - 1), np.clip(v * th - 0.5, 0, th - 1))
                        col[z0:z1 + 1, x0:x1 + 1][m] = sample[m]
    covered = np.isfinite(top)
    # colours carried a few cells past the edge, so samples there aren't black
    grown, m = col.copy(), covered.astype(np.uint8)
    for _ in range(8):
        wider = cv2.dilate(grown, np.ones((3, 3), np.uint8))
        more = cv2.dilate(m, np.ones((3, 3), np.uint8))
        grown = np.where(((m == 0) & (more == 1))[..., None], wider, grown)
        m = more
    return xs, zs, grown, np.where(covered, top, OUTSIDE), covered


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def crumple(xs, zs, sides):
    """Height added for a crumpled front: each side's folds, (side, seed),
    a side's from its seed the same on either side, mirrored."""
    out = np.zeros((len(zs), len(xs)))
    for side, seed in sides:
        h = folds(xs, zs, seed, alone=len(sides) == 1)
        out += h if side == 'left' else h[:, ::-1]
    return out


def folds(xs, zs, seed, alone):
    """Zigzag folds across the front's left (x < 0, the picture's left),
    deepest at the nose, with a few spikes where folds meet; reaching
    further toward the middle when the left is the only side crumpled."""
    rng = np.random.default_rng(seed)
    X, Z = np.meshgrid(xs, zs)
    lateral = smoothstep(-0.1, 0.6, -X) if alone else smoothstep(-0.2, 0.5, -X)
    depth = rng.uniform(0.75, 1.0)
    reach = 1 - smoothstep(NOSE + 0.25, NOSE + depth, Z)
    angle = rng.uniform(-0.5, 0.5) - 0.3
    spacing = rng.uniform(0.11, 0.16)
    warp = 0.06 * noise(X.shape, rng, 0.25 / RES)
    d = X * np.sin(angle) + (Z - NOSE) * np.cos(angle) + warp
    zigzag = 2 * np.abs((d / spacing) % 1 - 0.5)
    h = 0.09 * (1 + 0.5 * noise(X.shape, rng, 0.15 / RES)) * (zigzag - 0.3)
    for _ in range(4):
        cx, cz = -rng.uniform(0.2, 0.8), NOSE + rng.uniform(0.05, 0.45)
        r = np.hypot(X - cx, Z - cz)
        h += rng.uniform(0.05, 0.12) * np.clip(1 - r / rng.uniform(0.06, 0.12), 0, None)
    return lateral * reach * h


def noise(shape, rng, scale):
    n = cv2.GaussianBlur(rng.standard_normal(shape), (0, 0), scale)
    return n / (n.std() + 1e-9)


def bilinear(grid, gx, gz):
    h, w = grid.shape[:2]
    gx = np.clip(gx, 0, w - 1.001)
    gz = np.clip(gz, 0, h - 1.001)
    x0, z0 = gx.astype(int), gz.astype(int)
    fx, fz = gx - x0, gz - z0
    if grid.ndim == 3:
        fx, fz = fx[..., None], fz[..., None]
    return (grid[z0, x0] * (1 - fx) * (1 - fz) + grid[z0, x0 + 1] * fx * (1 - fz)
            + grid[z0 + 1, x0] * (1 - fx) * fz + grid[z0 + 1, x0 + 1] * fx * fz)


def rays(lines):
    """Each sample's line of sight (unit, model space) from the eye."""
    px, py = np.meshgrid((np.arange(W * SS) + 0.5) / SS, (np.arange(lines * SS) + 0.5) / SS)
    vx = (px - CAMERA['cx']) / CAMERA['lens']
    vy = -(py - CAMERA['cy']) / CAMERA['lens']
    c, s = math.cos(CAMERA['pitch']), math.sin(CAMERA['pitch'])
    d = np.stack([vx, vy * c - s, -(vy * s + c)], -1)
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def picture(xs, zs, colour, height, covered, rows=ROWS_1P, steps=400):
    """The hood seen from the eye: (colour, coverage) rows x 8 lines."""
    eye = np.array([0.0, CAMERA['height'], CAMERA['z']])
    d = rays(rows * 8).reshape(-1, 3)

    def ground(p):
        return bilinear(height, (p[:, 0] - xs[0]) / RES, (p[:, 2] - zs[0]) / RES)

    # march each ray between the field's highest and lowest heights
    down = -d[:, 1]
    live = down > 1e-6
    t0 = np.where(live, (eye[1] - height.max()) / np.maximum(down, 1e-6), 0)
    t1 = np.where(live, np.minimum((eye[1] - height.min()) / np.maximum(down, 1e-6), 5.0), 0)
    hit_t = np.full(len(d), np.nan)
    idx = np.flatnonzero(live)
    prev = t0[idx]
    for i in range(1, steps + 1):
        t = t0[idx] + (t1[idx] - t0[idx]) * i / steps
        p = eye + t[:, None] * d[idx]
        under = p[:, 1] <= ground(p)
        if under.any():
            lo, hi = prev[under], t[under]
            dd = d[idx[under]]
            for _ in range(14):
                mid = (lo + hi) / 2
                q = eye + mid[:, None] * dd
                b = q[:, 1] <= ground(q)
                hi, lo = np.where(b, mid, hi), np.where(b, lo, mid)
            hit_t[idx[under]] = hi
            idx, prev = idx[~under], t[~under]
        else:
            prev = t
        if not len(idx):
            break
    p = eye + np.nan_to_num(hit_t)[:, None] * d
    gx, gz = (p[:, 0] - xs[0]) / RES, (p[:, 2] - zs[0]) / RES
    inside = (gx >= 0) & (gx < len(xs) - 1) & (gz >= 0) & (gz < len(zs) - 1)
    hit = np.isfinite(hit_t) & inside
    hit[hit] = bilinear(covered.astype(float), gx[hit], gz[hit]) > 0.5

    slope_z, slope_x = np.gradient(height, RES)
    n = np.stack([-bilinear(slope_x, gx, gz), np.ones(len(d)), -bilinear(slope_z, gx, gz)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    az, el = LIGHT['azimuth'], LIGHT['elevation']
    light = np.array([math.cos(el) * math.sin(az), math.sin(el), -math.cos(el) * math.cos(az)])
    view = -d
    half = (light + view) / np.linalg.norm(light + view, axis=-1, keepdims=True)
    lambert = np.clip(n @ light, 0, None)
    highlight = np.clip((n * half).sum(-1), 0, None) ** LIGHT['shine']
    grazing = LIGHT['grazing'] * (1 - np.clip((n * view).sum(-1), 0, 1)) ** 3
    base = bilinear(colour, gx, gz)
    lit = (base * (LIGHT['ambient'] + LIGHT['diffuse'] * lambert)[:, None] * (1 + grazing[:, None])
           - grazing[:, None] * np.array([0.75, 0.85, 1.0]) + LIGHT['specular'] * highlight[:, None])
    lit = np.clip(lit, 0, 1) * hit[:, None]
    lit = lit.reshape(rows * 8, SS, W, SS, 3).sum(axis=(1, 3))
    count = hit.reshape(rows * 8, SS, W, SS).sum(axis=(1, 3))
    return lit / np.maximum(count, 1)[..., None], count / SS ** 2


def foreshortened(colour, xs, zs, height):
    """The paint blurred along the car by as much as the picture squeezes
    it there: toward the nose a line of the picture spans a dozen of the
    field's rows, more than its samples can take apart, and fine lettering
    there broke up into grit."""
    eye = np.array([0.0, CAMERA['height'], CAMERA['z']])
    c, s = math.cos(CAMERA['pitch']), math.sin(CAMERA['pitch'])
    y = height[:, len(xs) // 2] - eye[1]
    ahead = eye[2] - zs
    line = CAMERA['cy'] - CAMERA['lens'] * (y * c + ahead * s) / (ahead * c - y * s)
    rows_a_line = 1 / np.maximum(np.abs(np.gradient(line)), 1e-6)
    sigma = 0.5 * rows_a_line / SS                     # field rows between a line's samples, halved
    levels = (0, 0.5, 1, 1.5, 2, 3, 4)
    blurred = [colour] + [cv2.GaussianBlur(colour, (1, 0), sigmaX=1e-3, sigmaY=v) for v in levels[1:]]
    pick = np.interp(sigma, levels, np.arange(len(levels)))
    lo = np.floor(pick).astype(int)
    hi = np.minimum(lo + 1, len(levels) - 1)
    f = (pick - lo)[:, None, None]
    rows = np.arange(len(zs))
    out = np.array(blurred)
    return out[lo, rows] * (1 - f) + out[hi, rows] * f


def hood_pictures(poly, tex):
    """The four hood pictures (colour, coverage) of DUSA's body in tex."""
    xs, zs, colour, top, covered = top_view(*body_mesh(poly, tex))
    smooth = cv2.GaussianBlur(top, (0, 0), SMOOTH / RES)
    colour = foreshortened(colour, xs, zs, smooth)
    out = []
    for sides in DAMAGE:
        height = smooth + crumple(xs, zs, sides) * covered
        out.append(picture(xs, zs, colour, height, covered))
    return out


# ---------------------------------------------------------------- the files

def kmeans(pixels, k):
    """k colours for pixels (n x 3), on the colour words' 5-bit steps."""
    if len(pixels) <= k:
        return np.unique(np.round(pixels * 31) / 31, axis=0)
    cv2.setRNGSeed(1)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 1e-4)
    _, _, centres = cv2.kmeans(pixels.astype(np.float32), k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    return np.unique(np.round(np.clip(centres, 0, 1) * 31) / 31, axis=0)


def nearest(pixels, palette):
    d = ((pixels[:, None, :] - palette[None, :, :]) ** 2).sum(-1)
    return d.argmin(1)


def pack(pics, rows, colours):
    """A hood file of four index pictures (rows x 8 lines) and 256 colour words."""
    cells = {bytes(64): 0}
    chars, words = [bytes(64)], []
    for img in pics:
        for r in range(rows):
            for c in range(COLS):
                cell = img[r * 8:r * 8 + 8, c * 8:c * 8 + 8].tobytes()
                if cell not in cells:
                    cells[cell] = len(chars)
                    chars.append(cell)
                words.append(2 * cells[cell])
    chars = b''.join(chars)
    mp = struct.pack('>%dH' % len(words), *words)
    pal = struct.pack('>256H', *colours)
    head = struct.pack('>I', 3) + struct.pack('>II', len(chars), CHARS_AT) + struct.pack('>II', len(mp), MAP_AT) \
        + struct.pack('>II', len(pal), COLOURS_AT)
    return head + chars + mp + pal, len(chars) // 64


def one_player(hoods, cce_file, cowl):
    """The one-player file: our hood above the cowl, CCE's dashboard (its
    pixels and colours) from the cowl down."""
    chars, words, colours = read_hood(cce_file)
    theirs = pictures(chars, words, ROWS_1P)
    below = [np.arange(H)[:, None] >= cowl[None, :]] * 4
    dash = sorted(set(np.concatenate([p[b] for p, b in zip(theirs, below)]).tolist()) - {0})
    words_out = [colours[0]] + [colours[i] for i in dash]
    remap = np.zeros(256, np.uint8)
    remap[dash] = np.arange(1, len(dash) + 1)
    shown = [(c, (a >= 0.5) & ~b) for (c, a), b in zip(hoods, below)]
    pixels = np.concatenate([c[m] for c, m in shown])
    ours = kmeans(pixels, 256 - len(words_out))
    palette = np.array([word_rgb(w) for w in words_out[1:]] + list(ours))
    words_out += [rgb_word(c) for c in ours]
    pics = []
    for (c, m), b, p in zip(shown, below, theirs):
        img = np.where(b, remap[p], 0).astype(np.uint8)
        img[m] = 1 + nearest(c[m], palette)
        pics.append(img)
    data, n = pack(pics, ROWS_1P, words_out + [0] * (256 - len(words_out)))
    assert n <= MAX_CHARS_1P, f'{n} chars, room for {MAX_CHARS_1P}'
    return data


def two_players(hoods):
    """The two-player file: the pictures' top 7 rows, 127 colours."""
    lines = 8 * ROWS_2P
    shown = [(c[:lines], a[:lines] >= 0.5) for c, a in hoods]
    ours = kmeans(np.concatenate([c[m] for c, m in shown]), 127)
    pics = []
    for c, m in shown:
        img = np.zeros((lines, W), np.uint8)
        img[m] = 1 + nearest(c[m], ours)
        pics.append(img)
    words = [0x03E0] + [rgb_word(c) for c in ours]
    data, n = pack(pics, ROWS_2P, words + [0] * (256 - len(words)))
    assert n <= MAX_CHARS_2P, f'{n} chars, room for {MAX_CHARS_2P}'
    return data


# the cars with hoods of ours, by digit (patches/hoods.s's OURS): each '95
# car by its number from 1, and DUSA's car (the Hornet on DUSA's body and
# the secret car) as 9
DUSA_CAR = 9
CARS = (2, 3, 4, 5, 6, 7, 8, DUSA_CAR)
# whose dashboard a car's pictures keep: its own file's, DUSA's car the
# Hornet's (the secret car's dashboard is another, but below the screen)
DASH = {DUSA_CAR: 'HORNET'}
CACHE = 'build/hoods'
# what the pictures are made from, for the cache's key
SOURCES = ('hoods.py', 'liveries.py', 'car_pictures.py', 'car_convert.py', 'dusa_lzss.py')


def car_files(job):
    """One car and gearbox's two files: [(name, data)]."""
    dusa, cce, car, manual, cowl = job
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    src = liveries.Sources(dusa, cce)
    if car == DUSA_CAR:
        tex = cp.textures(src.texpl, manual)
    else:
        art = liveries.ninety_five_art(car, src, ART_SCALE, smooth=True)
        tex = cp.paint_textures(liveries.NINETY_FIVE[car](src), manual, art[manual])
    hoods = hood_pictures(poly, tex)
    dash = DASH.get(car, CCE_FILES[car - 1])
    gear = 'AM'[manual]
    return [(f'HOOD{car}{gear}1P.BIN', one_player(hoods, os.path.join(cce, 'DAYTONA', dash + '.BIN'), cowl)),
            (f'HOOD{car}{gear}2P.BIN', two_players(hoods))]


def build(dusa, cce, cars):
    """{file name: data} for each car digit in cars, both gearboxes, each
    on a process of its own."""
    import multiprocessing
    cowl = cowl_line(cce)
    jobs = [(dusa, cce, car, manual, cowl) for car in cars for manual in (0, 1)]
    with multiprocessing.Pool(min(len(jobs), os.cpu_count() or 1)) as pool:
        return dict(f for files in pool.map(car_files, jobs) for f in files)


def key(dusa, cce):
    """A hash of everything the pictures are made from."""
    import hashlib
    h = hashlib.sha1(repr(CARS).encode())
    here = os.path.dirname(os.path.abspath(__file__))
    for name in SOURCES:
        h.update(open(os.path.join(here, name), 'rb').read())
    for path in sorted([os.path.join(dusa, 'POLYGON.BIN'), os.path.join(dusa, 'TEX_PL.BIN')]
                       + [os.path.join(cce, 'DAYTONA', n) for n in os.listdir(os.path.join(cce, 'DAYTONA'))
                          if n.startswith('PLCAR') or os.path.splitext(n)[0] in CCE_FILES]):
        h.update(open(path, 'rb').read())
    return h.hexdigest()


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    stamp = os.path.join(CACHE, 'key.txt')
    k = key(dusa, cce)
    if os.path.exists(stamp) and open(stamp).read() == k:
        out = {n: open(os.path.join(CACHE, n), 'rb').read() for n in sorted(os.listdir(CACHE)) if n != 'key.txt'}
        how = 'unchanged, from ' + CACHE
    else:
        out = build(dusa, cce, CARS)
        os.makedirs(CACHE, exist_ok=True)
        for n in os.listdir(CACHE):
            os.remove(os.path.join(CACHE, n))
        for name, data in out.items():
            open(os.path.join(CACHE, name), 'wb').write(data)
        open(stamp, 'w').write(k)
        how = 'rendered'
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    for name, data in out.items():
        open(os.path.join(dst, 'DAYTONA', name), 'wb').write(data)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [f'DAYTONA/{n}' for n in out if f'DAYTONA/{n}' not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'hoods: {len(out)} files for cars {list(CARS)}, {how}')


if __name__ == '__main__':
    main()
