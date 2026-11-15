"""The two-player cars on DUSA's own low-detail car: POLYGON.BIN model 11
(92 vertices, 49 faces), the mid-distance drone of DUSA's races, in place of
the body (model 0, 132 faces) in PLCAR29 and the '95 cars' PLCAR5n.

Model 11's textures are DUSA's drone bank's, so each livery is painted onto
it again from the livered body: every texel of a model 11 face is a point
on that face (VDP1 stretches a texture over the four corners, so a texel's
point is the bilinear mix of the corners), and the body seen from outside
along the face's normal there (the outermost surface its line meets, near
the face) gives the colour in both liveries. The faces then share colour
tables 2-13 for the automatic livery and 16-27 for the manual one, where
every DUSA-body car file has its livery sets (patches/livery.s copies 16-28
over 2-14 for a manual car), 12 groups of faces each fitted to 16 pairs of
colours (liveries.fit_colours).
The rear window keeps DUSA's window texture, table 15 and texture entry 48,
which the two-player reflection rotates (src/race_block.s, reflect_2p), and
gets the body's window overlay (the frame and bars drawn over its windows,
transparent elsewhere) as a second polygon on the same corners, in the
body's arrangement: the overlay at sort type 1 listed first, the window at
sort type 2, so the overlay draws on top as the body's does in a race. That
is one face more than model 11's 49, and its colours take table 14/28 with
colour 0 left transparent.

Faces are grouped and textures sized from the geometry alone, so every
paint gives the same MDL, as car_convert.py requires.
"""
import struct

import numpy as np

import car_convert as cc
import liveries

LOWPOLY = (0x270, 92, 0x6C0, 49)        # POLYGON.BIN: vertices, count, faces, count
WINDOW_ENTRY = 48                       # reflect_2p's texture entry
REFLECT_STATE = 0x8E0                   # reflect_2p's scroll state in the MDL (src/race_block.s),
REFLECT_IMAGE = 0x8F0                   # then the window's image
GROUPS = 12                             # painted faces: tables 2-13 (automatic) / 16-27 (manual)
OVERLAY_TABLE = 14                      # the rear window's overlay: 14 / 28, colour 0 clear
FLOOR_TID = 4
FLOOR_SIZE = (16, 16)
REACH = 0.6                             # how far from a face its ray looks for the body


def model(poly, spec):
    vo, nv, fo, nf = spec
    verts = np.array([struct.unpack_from('>iii', poly, vo + 12 * i) for i in range(nv)], float) / 65536
    faces = []
    for i in range(nf):
        f = struct.unpack_from('>iiiHHHHHH', poly, fo + 24 * i)
        faces.append((f[3], f[4], tuple(f[5:9])))
    return verts, faces


def half_width(tri, verts0, y, z):
    """The body's half-width at height y, length z: the farthest point a line
    from the centre (0, y, z) out along +x meets; where it meets none (the
    spoiler's thin lip), the nearest body vertex in that cross-section."""
    v0 = tri[:, 0]
    e1, e2 = tri[:, 1] - v0, tri[:, 2] - v0
    d = np.array([1.0, 0, 0])
    p = np.cross(d, e2)
    det = np.einsum('ij,ij->i', e1, p)
    ok = np.abs(det) > 1e-9
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    t = np.array([0.0, y, z]) - v0
    a = np.einsum('ij,ij->i', t, p) * inv
    q = np.cross(t, e1)
    b = (q @ d) * inv
    s = np.einsum('ij,ij->i', q, e2) * inv
    hit = ok & (a >= 0) & (b >= 0) & (a + b <= 1) & (s > 0)
    if hit.any():
        return float(s[hit].max())
    near = verts0[np.abs(verts0[:, 2] - z) < 0.05]
    return float(abs(near[np.argmin(np.abs(near[:, 1] - y)), 0]))


def tucked(poly, verts):
    """Model 11 with its tail tucked in to the body's outline: model 11's rear
    end runs straight back at full width to its last ring, where the body
    narrows from its rear wheels (0.83 either side) to 0.65 at the tail lamps
    and 0.56 at the deck and spoiler. Each vertex of the tail's two rings
    (z over 2.3) and the deck's front corners (z 1.73, y 0.87) moves in to
    the body's half-width at its height and length; y and z stay."""
    verts0, faces0 = model(poly, cc.BODY)
    tri = []
    for _, _, idx in faces0:
        c = verts0[list(idx)]
        for a, b, d in ((0, 1, 2), (0, 2, 3)):
            if np.linalg.norm(np.cross(c[b] - c[a], c[d] - c[a])) > 1e-6:
                tri.append(c[[a, b, d]])
    tri = np.array(tri)
    out = verts.copy()
    for i, (x, y, z) in enumerate(verts):
        tail = z > 2.3
        deck_corner = abs(z - 1.73) < 0.01 and y > 0.8 and abs(x) > 0.7
        if (tail or deck_corner) and abs(x) > 0.3:
            out[i, 0] = np.sign(x) * half_width(tri, verts0, y, min(z, 2.455))
    return out


def body_triangles(poly):
    verts0, faces0 = model(poly, cc.BODY)
    tri = []
    for _, _, idx in faces0:
        c = verts0[list(idx)]
        for a, b, d in ((0, 1, 2), (0, 2, 3)):
            if np.linalg.norm(np.cross(c[b] - c[a], c[d] - c[a])) > 1e-6:
                tri.append(c[[a, b, d]])
    return np.array(tri)


def section(tri, axis, at):
    """Where the body's triangles cross the plane axis = at: the crossing points."""
    pts = []
    for t in tri:
        s = t[:, axis] - at
        if s.min() > 0 or s.max() < 0:
            continue
        for i in range(3):
            p, q = t[i], t[(i + 1) % 3]
            if s[i] == 0:
                pts.append(p)
            elif s[i] * s[(i + 1) % 3] < 0:
                pts.append(p + (q - p) * s[i] / (s[i] - s[(i + 1) % 3]))
    return np.array(pts)


def seated(poly, verts):
    """Model 11's wheels and sills cut off where the body ends, and its lower
    sides sloped in as the body's are, seen from behind or in front. Model 11
    reaches down to y 0 (its wheel blocks) and 0.11-0.14 (nose, sills), with
    square sides from top to bottom; the body ends at 0.17, and its sides
    narrow from 0.88 at y 0.5 to 0.84 at 0.17. The Saturn draws a car over the
    road whatever its depth, so the extra shows as tall dark blocks under the
    tail. Every vertex below the body's lowest point in its cross-section (z)
    rises to it (x and z kept). Then each outer vertex below y 0.3 (the wheel
    and sill bottoms, at 0.82) moves in to the body's outline from behind at
    its height, scaled to model 11's width (0.82 / 0.88), so the lower sides
    slope as the body's; y and z stay, so the side view only loses the part
    below 0.17."""
    tri = body_triangles(poly)
    out = verts.copy()
    lowest = {}
    for i, (x, y, z) in enumerate(verts):
        if z not in lowest:
            lowest[z] = float(section(tri, 2, z)[:, 1].min())
        out[i, 1] = max(y, lowest[z])
    widest = float(np.abs(verts[:, 0]).max())
    body_widest = float(np.abs(tri[:, :, 0]).max())
    outline = {}
    for i, (x, y, z) in enumerate(out):
        if abs(x) > 0.8 and y < 0.3:
            if y not in outline:
                outline[y] = float(np.abs(section(tri, 1, y)[:, 0]).max())
            out[i, 0] = np.sign(x) * widest * outline[y] / body_widest
    return out


def rgb5(w):
    return np.array([w & 31, (w >> 5) & 31, (w >> 10) & 31])


class Body:
    """Model 0 as triangles with texture coordinates, and each face's texels
    as colour pairs (automatic, manual) on the Saturn's 5 bits."""
    def __init__(self, poly, paint):
        verts, faces = model(poly, cc.BODY)
        tri, uvs, owner = [], [], []
        self.texels, self.flips, self.transparent = [], [], []
        for k, (attr, tid, idx) in enumerate(faces):
            c = verts[list(idx)]
            for a, b, d in ((0, 1, 2), (0, 2, 3)):
                if np.linalg.norm(np.cross(c[b] - c[a], c[d] - c[a])) < 1e-6:
                    continue
                tri.append(c[[a, b, d]])
                uvs.append(np.array([(0, 0), (1, 0), (1, 1), (0, 1)], float)[[a, b, d]])
                owner.append(k)
            px = paint.pixels[tid]
            if tid == cc.WINDOW_TEX:
                px = px[:40]
            t = liveries.table_of(tid)
            pal_a = np.array([rgb5(w) for w in paint.tables[t]])
            pal_m = np.array([rgb5(w) for w in paint.tables[t + liveries.SET_B if 2 <= t <= 14 else t]])
            self.texels.append((np.concatenate([pal_a[px], pal_m[px]], -1), px))
            self.flips.append((bool(attr & 0x80), bool(attr & 0x40)))
            self.transparent.append(bool(attr & 0x10))
        self.tri, self.uv, self.owner = np.array(tri), np.array(uvs), np.array(owner)
        e1, e2 = self.tri[:, 1] - self.tri[:, 0], self.tri[:, 2] - self.tri[:, 0]
        n = np.cross(e1, e2)
        self.normal = n / np.linalg.norm(n, axis=1, keepdims=True)

    def colour(self, k, uv):
        (col, px), (hf, vf) = self.texels[k], self.flips[k]
        u, v = uv
        if hf:
            u = 1 - u
        if vf:
            v = 1 - v
        h, w = px.shape
        tx, ty = min(int(u * w), w - 1), min(int(v * h), h - 1)
        return col[ty, tx], (self.transparent[k] and px[ty, tx] == 0)

    def sample(self, points, d, overlay=False):
        """The body's colour pair as seen from outside along d (the face's
        outward normal) at each point: the outermost surface within REACH
        either side, through transparent texels; None where there is none.
        overlay: only the transparent faces, None where they are clear."""
        v0 = self.tri[:, 0]
        e1, e2 = self.tri[:, 1] - v0, self.tri[:, 2] - v0
        pvec = np.cross(d, e2)
        det = np.einsum('ij,ij->i', e1, pvec)
        facing = np.abs(self.normal @ d) > 0.25
        ok_det = (np.abs(det) > 1e-9) & facing
        inv = np.where(ok_det, 1 / np.where(ok_det, det, 1), 0)
        tvec = points[:, None, :] - v0[None]
        a = np.einsum('ntj,tj->nt', tvec, pvec) * inv
        qvec = np.cross(tvec, e1[None])
        b = (qvec @ d) * inv
        t = np.einsum('ntj,tj->nt', qvec, e2) * inv
        hit = ok_det & (a >= -1e-4) & (b >= -1e-4) & (a + b <= 1 + 1e-4) & (np.abs(t) <= REACH)
        out = [None] * len(points)
        for i in range(len(points)):
            cand = [j for j in np.nonzero(hit[i])[0] if not overlay or self.transparent[self.owner[j]]]
            # outermost first; where faces lie on each other (each window and
            # its transparent overlay) the overlay, listed first, is on top,
            # as a race draws the body (the bars show on the rear window)
            for j in sorted(cand, key=lambda j: (-round(t[i, j] / 0.02), self.owner[j])):
                uv = self.uv[j, 0] * (1 - a[i, j] - b[i, j]) + self.uv[j, 1] * a[i, j] + self.uv[j, 2] * b[i, j]
                col, clear = self.colour(self.owner[j], uv)
                if not clear:
                    out[i] = col
                    break
                if overlay:
                    break
        return out


def corner_mix(c, u, v):
    """VDP1's stretch of a texture over corners A, B, C, D at (u, v)."""
    return ((1 - u) * (1 - v))[..., None] * c[0] + (u * (1 - v))[..., None] * c[1] + \
        (u * v)[..., None] * c[2] + ((1 - u) * v)[..., None] * c[3]


def outward(verts, idx):
    """A face's corners and its normal pointing away from the car; a face
    flattened to a line (two of model 11's wheel faces, wholly below the
    body's bottom, once seated) faces straight out from the car's middle."""
    c = verts[list(idx)]
    n = np.cross(c[2] - c[0], c[3] - c[1])
    if np.linalg.norm(n) < 1e-9:
        n = c.mean(0) - verts.mean(0)
    n = n / np.linalg.norm(n)
    if n @ (c.mean(0) - verts.mean(0)) < 0:
        n = -n
    return c, n


OVERLAY = -1                            # the overlay face's texture id here


def layout(poly, budget, tuck=True, seat=True):
    """Model 11's faces, the rear window's overlay added after them: each
    one's texture size (paint-independent) and colour group, at the texel
    density that fills the budget (texels)."""
    verts, faces = model(poly, LOWPOLY)
    if tuck:
        verts = tucked(poly, verts)
    if seat:
        verts = seated(poly, verts)
    window = next(f for f in faces if f[1] == cc.WINDOW_TEX)
    faces.append((0x0011, OVERLAY, window[2]))  # sort type 1, transparent
    lens, feats = [], []
    for attr, tid, idx in faces:
        c, n = outward(verts, idx)
        lens.append((max(np.linalg.norm(c[1] - c[0]), np.linalg.norm(c[2] - c[3])),
                     max(np.linalg.norm(c[3] - c[0]), np.linalg.norm(c[2] - c[1]))))
        feats.append(np.concatenate([c.mean(0), 0.8 * n]))

    def sizes(s):
        out = []
        for (attr, tid, idx), (lw, lh) in zip(faces, lens):
            if tid == cc.WINDOW_TEX:
                out.append((80, 40))
            elif tid == FLOOR_TID:
                out.append(FLOOR_SIZE)
            else:
                out.append((min(max(8, 8 * round(lw * s / 8)), 248), min(max(2, round(lh * s)), 255)))
        return out

    lo, hi = 1.0, 200.0
    for _ in range(40):
        mid = (lo + hi) / 2
        cost = sum(w * h + (-w * h) % 16 for w, h in sizes(mid))
        lo, hi = (mid, hi) if cost <= budget else (lo, mid)
    painted = [i for i, (_, tid, _) in enumerate(faces) if tid not in (cc.WINDOW_TEX, OVERLAY)]
    x = np.array([feats[i] for i in painted])
    centres = liveries.kmeans(x, GROUPS, np.zeros((0, x.shape[1])))
    near = np.linalg.norm(x[:, None] - centres[None], axis=-1).argmin(1)
    group = {i: int(g) for i, g in zip(painted, near)}
    group[len(faces) - 1] = OVERLAY_TABLE - 2
    return verts, faces, sizes(lo), group, lo


def build_2p(poly, paint, entry_count, mdl_size, tex_size, tuck=True, seat=True):
    """One car's two-player MDL and TEX on model 11 -> (mdl, tex, report)."""
    tables_len = liveries.N_TABLES * 32
    budget = (tex_size - 20 - tables_len) * 2 - 16     # texels, the window's 80 x 40 included
    verts, faces, sizes, group, density = layout(poly, budget, tuck, seat)
    body = Body(poly, paint)
    # bake every painted face
    baked = {}
    misses = 0
    overlay = {}
    for i, ((attr, tid, idx), (w, h)) in enumerate(zip(faces, sizes)):
        if tid == cc.WINDOW_TEX:
            continue
        c, n = outward(verts, idx)
        uu, vv = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
        pts = corner_mix(c, uu, vv).reshape(-1, 3)
        if tid == OVERLAY:
            overlay[i] = body.sample(pts, n, overlay=True)
            continue
        cols = body.sample(pts, n)
        got = np.array([x is not None for x in cols])
        misses += int((~got).sum())
        img = np.zeros((h * w, 6))
        if got.any():
            img[got] = np.array([x for x in cols if x is not None])
            if not got.all():               # holes: the nearest baked texel of the face
                yx = np.stack([vv.reshape(-1), uu.reshape(-1)], 1)
                src = np.nonzero(got)[0]
                for j in np.nonzero(~got)[0]:
                    img[j] = img[src[np.argmin(np.linalg.norm(yx[src] - yx[j], axis=1))]]
        baked[i] = img.reshape(h, w, 6)
    # each group's texels to 16 colour pairs
    tables = [list(t) for t in paint.tables]
    pixels = {}
    for g in range(GROUPS):
        members = [i for i in sorted(baked) if group[i] == g]
        if not members:
            continue
        v = np.concatenate([baked[i].reshape(-1, 6) for i in members]) / 31
        v = liveries.fit_colours(v)
        pairs, at = {}, 0
        for i in members:
            h, w = baked[i].shape[:2]
            pixels[i] = np.array([pairs.setdefault((liveries.word(p[:3]), liveries.word(p[3:])), len(pairs))
                                  for p in v[at:at + h * w]]).reshape(h, w)
            at += h * w
        t = 2 + g
        tables[t] = [0x8000] * 16
        tables[t + liveries.SET_B] = [0x8000] * 16
        for (wa, wm), k in pairs.items():
            tables[t][k] = wa
            tables[t + liveries.SET_B][k] = wm
    # the overlay: colour 0 clear, its own 15 pairs
    t = OVERLAY_TABLE
    tables[t] = [0x0000] + [0x8000] * 15
    tables[t + liveries.SET_B] = [0x0000] + [0x8000] * 15
    for i, cols in overlay.items():
        w, h = sizes[i]
        got = [k for k, x in enumerate(cols) if x is not None]
        px = np.zeros(w * h, int)
        if got:
            v = liveries.fit_colours(np.array([cols[k] for k in got]) / 31, 15)
            pairs = {}
            for k, p in zip(got, v):
                px[k] = 1 + pairs.setdefault((liveries.word(p[:3]), liveries.word(p[3:])), len(pairs))
            for (wa, wm), k in pairs.items():
                tables[t][1 + k] = wa
                tables[t + liveries.SET_B][1 + k] = wm
        pixels[i] = px.reshape(h, w)
    # TEX: tables, then each texture at an 8-byte boundary
    tex = bytearray(b''.join(struct.pack('>16H', *t) for t in tables))
    place = {}
    for i, (attr, tid, idx) in enumerate(faces):
        w, h = sizes[i]
        data = cc.nibbles(paint.pixels[cc.WINDOW_TEX][:40] if tid == cc.WINDOW_TEX else pixels[i])
        place[i] = (len(tex) - tables_len) // 8
        tex += data + bytes(-len(data) % 8)
    tex_used = len(tex)
    tex_trailer = tex_size - 2 * 8 - 4
    if len(tex) > tex_trailer:
        raise ValueError(f'the TEX is {len(tex) - tex_trailer} bytes too big')
    tex += bytes(tex_trailer - len(tex))
    tex += struct.pack('>IiIiI', 0xB9, -tex_trailer, 0xBA, tables_len - tex_trailer, 2)
    # MDL: texture table (glass entry 9 left for the loader, the window at 48)
    entry_count = max(entry_count, sum(tid != cc.WINDOW_TEX for _, tid, _ in faces) + 2, WINDOW_ENTRY + 1)
    free = [e for e in range(entry_count) if e not in (cc.GLASS_ENTRY, WINDOW_ENTRY)]
    entry, k = {}, 0
    for i, (attr, tid, idx) in enumerate(faces):
        if tid == cc.WINDOW_TEX:
            entry[i] = WINDOW_ENTRY
        else:
            entry[i] = free[k]
            k += 1
    table = bytearray(struct.pack('>HHHH', entry_count, 0, 0, 0))
    by_entry = {e: i for i, e in entry.items()}
    for e in range(entry_count):
        if e in by_entry:
            i = by_entry[e]
            w, h = sizes[i]
            tnum = 15 if faces[i][1] == cc.WINDOW_TEX else 2 + group[i]
            pmod = 0x1488 if faces[i][1] == OVERLAY else 0x14C8
            table += struct.pack('>4H', pmod, 4 * tnum, place[i], (w // 8) << 8 | h)
        else:
            table += struct.pack('>4H', 0x14C8, 0, 0, 0x0108)
    # polygons in model 11's order, the overlay just before the window
    order = list(range(len(faces) - 1))
    order.insert(next(i for i, f in enumerate(faces) if f[1] == cc.WINDOW_TEX), len(faces) - 1)
    polys = bytearray()
    for i in order:
        attr, tid, idx = faces[i]
        direction = (0, 2, 1, 3)[(attr >> 6) & 3] if tid == cc.WINDOW_TEX else 0
        sort = 2 if tid == cc.WINDOW_TEX else cc.SORT[attr & 7]
        cattr = 0x40 | (sort << 1) | (0 if attr & 8 else 0x10) | (direction << 12)
        polys += struct.pack('>6H', cattr, 8 * entry[i], *(16 * v for v in idx))
    headers_at = len(table)
    polys_at = headers_at + 6 * 20
    verts_at = polys_at + len(polys)
    blocks = b''
    for k in range(6):
        h = headers_at + 20 * k
        blocks += struct.pack('>HHiiii', len(verts), len(faces), verts_at - h, polys_at - h, -h, 0)
    vblock = b''.join(struct.pack('>3h', *(round(c * 1024) for c in v)) for v in verts)
    mdl = bytes(table) + blocks + bytes(polys) + vblock
    used = len(mdl)
    if used > REFLECT_STATE:
        raise ValueError(f'the MDL runs into reflect_2p\'s state at +0x{REFLECT_STATE:X} ({used} bytes)')
    # src/race_block.s's reflect_2p: its state (zeros), then the window's image once
    # and its first byte again, which it DMAs into the window from any start
    window = cc.nibbles(paint.pixels[cc.WINDOW_TEX][:40])
    mdl += bytes(REFLECT_IMAGE - len(mdl)) + window + window[:1]
    trailer_at = mdl_size - 8 * len(cc.TRAILER_IDS) - 4
    if trailer_at < len(mdl):
        raise ValueError(f'the window image runs into the trailer at +0x{trailer_at:X}')
    mdl += bytes(trailer_at - len(mdl))
    targets = [0, 8 + 8 * cc.GLASS_ENTRY] + [headers_at + 20 * k for k in range(6)]
    for sid, t in zip(cc.TRAILER_IDS, targets):
        mdl += struct.pack('>Ii', sid, t - trailer_at)
    mdl += struct.pack('>I', len(cc.TRAILER_IDS))
    texels = sum(w * h for w, h in sizes)
    report = (f'model 11 and the rear window overlay, {len(faces)} faces; MDL {used} bytes used of {mdl_size}; TEX {tex_used} of {tex_size}, '
              f'{texels} texels at {density:.1f} a unit; {misses} texels filled from neighbours')
    return mdl, bytes(tex), report
