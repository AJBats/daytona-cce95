"""DUSA's ground under all of CCE95's courses: rebuild CSn_COL.BIN.

usage: col_convert.py <dusa extracted dir> <cce extracted dir> <out dir>
  Reads DUSA's COURSE0-2.BIN and CCE's DAYTONA/CS0_COL.BIN, CS1_COL.BIN,
  CS12_COL.BIN (Dinosaur Canyon when 0605492A is 1), CS2_COL.BIN,
  CS3_COL.BIN and CS4_COL.BIN; writes the six under <out dir>/DAYTONA and
  lists them in PATCHED.txt. Files keep their sizes (the disc keeps the
  original directory entries).

DUSA's three courses get DUSA's own ground, below. CCE's own two (National
Park Speedway, Desert City) get ground made from CCE's the way DUSA's was
made, by tools/col_generate.py.

Both games find the ground the same way (docs/conformance.md, "Turns 1-2
banks"): a 64 x 64 grid of 32-unit cells, each with a list of polygons; the
first polygon in the list that holds the point gives the height from its
plane. CCE re-meshed the courses into quads whose planes don't meet, and the
car rocks where the wheels straddle the steps; DUSA's triangles meet.

DUSA, COURSEn.BIN: 0x34-byte polygons from +0 (flags; plane y = a x + b z
+ c; four edge lines m x + k [+ z], flag bits 0x01000000 << i: no z term),
then the grid (4096 x (byte offset, count)) and the lists (the loader's
offsets, DUSA 06018808...). A triangle repeats its third edge. On Seaside
Street Galaxy (course 2) twelve cells where the road crosses itself have a
second list, used while car +0x1EC <= 70 (DUSA 06027F20; cells at
06061270, lists at 06061240): the upper road.

CCE, CSn_COL.BIN (loaded as is at 00220000): two grids of 4096 pointers to
lists (count, polygon index...), at +0 and +0x4000; 0x34-byte polygons from
+0x8000: flags (type << 16, low word below), four (x, z) corners in 12.20,
normal x, y, z in 8.24 and D, y = 4D / Ny - (Nx x + Nz z) / Ny. A point is
inside when every edge's cross product is >= 0 (a quad also takes all < 0).
Each car uses the grid in +0x12C, switched when it reaches the course's two
switch segments (06038600, table 0604F9BC); the grids differ only where
Seaside crosses itself, where the first holds the upper road. Type 0 is a
wall strip (vertical, Ny = 0), with a "height" ramping up from the edge. The
ground contact (060386D8) only tells 0 from the rest. Each corner contact
(06036BB8) maps the type through the table at 0604E1C4 into car +0x4C..
+0x58: 1 road -> 1, 3 grass -> 4, 4 apron -> 3, and 2, road under a roof
(Three Seven's cover over the main straight, the tunnels) -> 17, which turns
CCE's tunnel echo on (06030D20: the race's mixers change while a front
corner reads 17). Only the lookup (060368D4-06036A9A) reads the file, and
of the flags' low word only bit 0 (triangle).

DUSA's polygons carry no roof, so each one that lies at least half under
CCE's type 2 polygons, at the same height (the upper road crosses over
Seaside's tunnel), is written as type 2.

DUSA's straightening pull aims at a road direction kept in each polygon (+0x30
high word), taken from the polygon under the car's front corner (+0.92 right,
1.8 ahead; DUSA 06027CA4). CCE's comes from its course line (+0x194). Each
polygon written here carries DUSA's direction in its flags' low word: bit 1
set, bits 2-15 the direction's (bits 0-1 dropped); the wall strips carry the
direction of DUSA's polygon at their centre. patches/road_direction.s reads it.

Written here, for each grid and cell:
  CCE's wall strips, as CCE lists them in that grid
  DUSA's list for the cell, in its order, as types 1 (road, and DUSA's 80,
  the ground outside the track edges, which shows only where no wall lies),
  4 (apron) and 3 (grass); on Seaside the first grid has the upper road's
  list ahead of it where DUSA has one, as CCE's first grid holds the upper
  road there
  outside the cells where CCE's two grids differ (the crossing), any DUSA
  polygon over the cell that DUSA's list leaves out: DUSA's lists miss a
  few, and a point found nowhere keeps a neighbouring wheel's height
Each DUSA polygon's corners are where its edge lines meet, so it covers
what DUSA's own test covers (to 2^-20 units).
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import col_generate  # noqa: E402

LOAD = 0x00220000
POLYS_AT = 0x8000
# (DUSA file, its grid and lists offsets, CCE file)
COURSES = (
    ('COURSE0.BIN', 0x6660, 0xA660, 'DAYTONA/CS0_COL.BIN'),
    ('COURSE1.BIN', 0x180B8, 0x1C0B8, 'DAYTONA/CS1_COL.BIN'),
    ('COURSE1.BIN', 0x180B8, 0x1C0B8, 'DAYTONA/CS12_COL.BIN'),
    ('COURSE2.BIN', 0x18598, 0x1C598, 'DAYTONA/CS2_COL.BIN'),
)
# CCE's own courses: the start grid (Time Attack, build/states/cce95_col_csN_start.mcs): x, z and heading,
# which way the race goes for the road directions
GENERATED = (
    ('DAYTONA/CS3_COL.BIN', (-145.93, -117.3), 21888),
    ('DAYTONA/CS4_COL.BIN', (-337.0, -65.0), 0),
)
UPPER = {'COURSE2.BIN': dict(zip(
    (1433, 1434, 1497, 1498, 1499, 1500, 1561, 1562, 1563, 1564, 1627, 1628),
    ((4472, 3), (4502, 1), (4726, 6), (4756, 4), (4794, 2), (4810, 2), (5072, 6), (5100, 4), (5126, 3),
     (5146, 6), (5510, 1), (5526, 3))))}
TYPES = {0x01: 1, 0x41: 1, 0x09: 1, 0x10: 1, 0x20: 1, 0x80: 1, 0x02: 4, 0x04: 3, 0x0C: 3}
CELL = 32.0


def meet(e1, e2):
    """Where m1 x + k1 [+ z] = 0 meets m2 x + k2 [+ z] = 0."""
    (m1, k1, z1), (m2, k2, z2) = [(m / 65536, k / 65536, z) for m, k, z in (e1, e2)]
    det = m1 * z2 - m2 * z1
    return (-k1 * z2 + k2 * z1) / det, (-m1 * k2 + m2 * k1) / det


def ccw(vs):
    area = sum(vs[i][0] * vs[(i + 1) % len(vs)][1] - vs[(i + 1) % len(vs)][0] * vs[i][1] for i in range(len(vs)))
    return vs if area > 0 else vs[::-1]


def clip_area(vs, x0, x1, z0, z1):
    """Area of polygon vs inside the rectangle."""
    for axis, lim, above in ((0, x0, True), (0, x1, False), (1, z0, True), (1, z1, False)):
        out = []
        for i, p in enumerate(vs):
            q = vs[(i + 1) % len(vs)]
            pin = p[axis] >= lim if above else p[axis] <= lim
            qin = q[axis] >= lim if above else q[axis] <= lim
            if pin:
                out.append(p)
            if pin != qin:
                t = (lim - p[axis]) / (q[axis] - p[axis])
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        vs = out
        if not vs:
            return 0.0
    return abs(sum(vs[i][0] * vs[(i + 1) % len(vs)][1] - vs[(i + 1) % len(vs)][0] * vs[i][1] for i in range(len(vs)))) / 2


def clip_convex(vs, clip):
    """vs (ccw) inside the convex ccw polygon clip."""
    for i, a in enumerate(clip):
        b = clip[(i + 1) % len(clip)]
        side = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        out = []
        for j, p in enumerate(vs):
            q = vs[(j + 1) % len(vs)]
            sp, sq = side(p), side(q)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        vs = out
        if len(vs) < 3:
            return []
    return vs


def area_centroid(vs):
    a = cx = cz = 0.0
    for i, p in enumerate(vs):
        q = vs[(i + 1) % len(vs)]
        w = p[0] * q[1] - q[0] * p[1]
        a += w
        cx += (p[0] + q[0]) * w
        cz += (p[1] + q[1]) * w
    if abs(a) < 1e-12:
        return 0.0, vs[0]
    return abs(a) / 2, (cx / (3 * a), cz / (3 * a))


def roofed(col):
    """CCE's type 2 polygons: (ccw corners, height at (x, z))."""
    out = []
    for i in range((len(col) - POLYS_AT) // 0x34):
        r = struct.unpack_from('>13i', col, POLYS_AT + 0x34 * i)
        if r[0] >> 16 != 2 or not r[10]:
            continue
        k = 3 if r[0] & 1 else 4
        vs = ccw([(r[1 + 2 * j] / (1 << 20), r[2 + 2 * j] / (1 << 20)) for j in range(k)])
        nx, ny, nz, d = r[9:13]
        out.append((vs, lambda x, z, nx=nx, ny=ny, nz=nz, d=d: (4 * d - nx * x - nz * z) / ny))
    return out


def under_roof(vs, height, roofs):
    """Whether at least half of polygon vs lies under the roofed polygons at its own height."""
    total, _ = area_centroid(vs)
    xs, zs = [v[0] for v in vs], [v[1] for v in vs]
    covered = 0.0
    for rv, rh in roofs:
        if min(v[0] for v in rv) > max(xs) or max(v[0] for v in rv) < min(xs) or \
                min(v[1] for v in rv) > max(zs) or max(v[1] for v in rv) < min(zs):
            continue
        part = clip_convex(vs, rv)
        if part:
            a, (x, z) = area_centroid(part)
            if abs(height(x, z) - rh(x, z)) < 3:
                covered += a
    return covered >= total / 2


def cells(vs):
    """CCE's cells (column + 64 x row) the polygon covers."""
    xs, zs = [v[0] for v in vs], [v[1] for v in vs]
    out = []
    for col in range(max(0, math.floor(min(xs) / CELL) + 32), min(63, math.floor(max(xs) / CELL) + 32) + 1):
        for row in range(max(0, 31 - math.ceil(max(zs) / CELL)), min(63, 32 - math.floor(min(zs) / CELL)) + 1):
            x0, z1 = (col - 32) * CELL, (32 - row) * CELL
            if clip_area(vs, x0, x0 + CELL, z1 - CELL, z1) > 1e-6:
                out.append(col + 64 * row)
    return out


def fix(v):
    return round(v * (1 << 20))


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def dusa_holds(r, x, z):
    """DUSA's own test (06027EDE): x, z in 16.16."""
    for k in range(4):
        v = s32(((x * r[4 + 2 * k]) >> 16) + r[5 + 2 * k])
        if not r[0] & (0x01000000 << k):
            v = s32(v + z)
        if r[0] & (0x100 << k):
            v = -v
        if v < 0:
            return False
    return True


def direction(r):
    """Flags low word bits 1-15 for DUSA polygon record r."""
    return 2 | (r[12] >> 16) & 0xFFFC


def convert(course, grid_at, lists_at, upper_at, col):
    def dusa_list(at, count):
        return struct.unpack_from(f'>{count}h', course, lists_at + at)

    normal = {}
    for c in range(4096):
        at, count = struct.unpack_from('>hh', course, grid_at + 4 * c)
        if count > 0:
            normal[c] = dusa_list(at, count)
    upper = {c: dusa_list(at, count) for c, (at, count) in upper_at.items()}

    def cce_list(grid, c):
        p = struct.unpack_from('>I', col, grid + 4 * c)[0]
        if not p:
            return ()
        n = struct.unpack_from('>H', col, p - LOAD)[0]
        return struct.unpack_from(f'>{n}H', col, p - LOAD + 2)
    walls = [{}, {}]
    for g in (0, 1):
        for c in range(4096):
            for i in cce_list(0x4000 * g, c):
                if struct.unpack_from('>i', col, POLYS_AT + 0x34 * i)[0] >> 16 == 0:
                    walls[g].setdefault(c, []).append(i)

    crossing = {c for c in range(4096) if cce_list(0, c) != cce_list(0x4000, c)}

    # CCE's walls first, then DUSA's polygons
    wall_ids = sorted({i for w in walls for l in w.values() for i in l})
    index = {('cce', i): n for n, i in enumerate(wall_ids)}
    dusa_ids = sorted({i for l in list(normal.values()) + list(upper.values()) for i in l})
    index.update({('dusa', i): n for n, i in enumerate(dusa_ids, len(wall_ids))})

    def dusa_at(x, z):
        x, z = round(x * 65536), round(z * 65536)
        c = (((x + 0x4000000) & 0xFFFFFFFF) >> 21) + ((((0x3FFFFFF - z) & 0xFFFFFFFF) >> 21) << 6)
        for i in normal.get(c, ()):
            r = struct.unpack_from('>13i', course, 0x34 * i)
            if dusa_holds(r, x, z):
                return r
        return None

    roofs = roofed(col)
    n_roofed = 0
    polys = []
    for i in wall_ids:
        r = list(struct.unpack_from('>13i', col, POLYS_AT + 0x34 * i))
        k = 3 if r[0] & 1 else 4
        d = dusa_at(sum(r[1:1 + 2 * k:2]) / k / (1 << 20), sum(r[2:2 + 2 * k:2]) / k / (1 << 20))
        if d is not None:
            r[0] = r[0] & 0xFFFF0001 | direction(d)
        polys.append(struct.pack('>13i', *r))
    over = {}
    for i in dusa_ids:
        r = struct.unpack_from('>13i', course, 0x34 * i)
        if r[0] & 0xFF not in TYPES:
            sys.exit(f'error: DUSA polygon {i} flags {r[0]:08X}')
        edges = []
        for k in range(4):
            e = (r[4 + 2 * k], r[5 + 2 * k], not r[0] & (0x01000000 << k))
            if not edges or e != edges[-1]:
                edges.append(e)
        if len(edges) > 3 and edges[-1] == edges[0]:
            edges.pop()
        vs = ccw([meet(edges[k], edges[(k + 1) % len(edges)]) for k in range(len(edges))])
        for c in cells(vs):
            over.setdefault(c, []).append(i)
        a, b, c = r[1] / 65536, r[2] / 65536, r[3] / 65536
        s = (1 << 24) / math.sqrt(a * a + b * b + 1)
        ny = round(s)
        typ = TYPES[r[0] & 0xFF]
        if under_roof(vs, lambda x, z: a * x + b * z + c, roofs):
            typ = 2
            n_roofed += 1
        rec = [(typ << 16) | direction(r) | (len(vs) == 3)]
        rec += [fix(t) for v in vs for t in v] + [0, 0] * (4 - len(vs))
        rec += [round(-a * s), ny, round(-b * s), round(c * ny / 4)]
        polys.append(struct.pack('>13i', *rec))

    out = bytearray(len(col))
    at = POLYS_AT
    for p in polys:
        out[at:at + 0x34] = p
        at += 0x34
    written = {}
    for g in (0, 1):
        for c in range(4096):
            dusa = list(normal.get(c, ()))
            if g == 0 and c in upper:
                dusa = list(upper[c]) + [i for i in dusa if i not in upper[c]]
            if c not in crossing:
                dusa += [i for i in over.get(c, ()) if i not in dusa]
            lst = [index['cce', i] for i in walls[g].get(c, ())] + [index['dusa', i] for i in dusa]
            if not lst:
                continue
            key = tuple(lst)
            if key not in written:
                written[key] = LOAD + at
                struct.pack_into(f'>H{len(lst)}H', out, at, len(lst), *lst)
                at += 2 + 2 * len(lst)
            struct.pack_into('>I', out, 0x4000 * g + 4 * c, written[key])
    if at > len(col):
        sys.exit(f'error: {at} bytes, the slot holds {len(col)}')
    return out, len(wall_ids), len(dusa_ids), n_roofed, at


def main():
    src, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    for course_name, grid_at, lists_at, name in COURSES:
        course = open(os.path.join(src, course_name), 'rb').read()
        col = open(os.path.join(cce, name), 'rb').read()
        out, walls, ground, roofed_n, size = convert(course, grid_at, lists_at, UPPER.get(course_name, {}), col)
        path = os.path.join(dst, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(out)
        if name not in have:
            have.append(name)
        print(f'{os.path.basename(name)}: {walls} CCE wall strips, {ground} DUSA polygons from {course_name} '
              f'({roofed_n} under a roof); {size} of {len(col)} bytes')
    for name, start, heading in GENERATED:
        out, report = col_generate.generate(open(os.path.join(cce, name), 'rb').read(), start, heading)
        open(os.path.join(dst, name), 'wb').write(out)
        if name not in have:
            have.append(name)
        print(f'{os.path.basename(name)}: {report}')
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))


if __name__ == '__main__':
    main()
