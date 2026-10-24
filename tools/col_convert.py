"""Put DUSA's ground under Three Seven in CCE95: rebuild CS0_COL.BIN.

usage: col_convert.py <dusa extracted dir> <cce extracted dir> <out dir>
  Reads DUSA's COURSE0.BIN and CCE's DAYTONA/CS0_COL.BIN; writes
  DAYTONA/CS0_COL.BIN under <out dir> and lists it in PATCHED.txt. The file
  keeps its size (the disc keeps the original directory entries).

Both games find the ground the same way (docs/conformance.md, "Turns 1-2
banks"): a 64 x 64 grid of 32-unit cells, each with a list of polygons; the
first polygon in the list that holds the point gives the height from its
plane. CCE re-meshed the banks into quads whose planes don't meet, and the
car rocks where the wheels straddle the steps; DUSA's triangles meet.

DUSA, COURSE0.BIN: 0x34-byte polygons from +0 (flags; plane y = a x + b z
+ c; four edge lines m x + k [+ z], flag bits 0x01000000 << i: no z term),
the grid at +0x6660 and the lists at +0xA660. A triangle repeats its third
edge. Flags low byte: 01 road (41 one road piece), 02 apron, 04 grass, 80
the ground outside the track edges.

CCE, CS0_COL.BIN (loaded as is at 00220000): grids for z >= 0 at +0 and
z < 0 at +0x4000 (the same for this course), 4096 pointers to lists
(count, polygon index...); 0x34-byte polygons from +0x8000: flags (type <<
16, bit 0 triangle), four (x, z) corners in 12.20, normal x, y, z in 8.24
and D, y = 4D / Ny - (Nx x + Nz z) / Ny. A point is inside when every
edge's cross product is >= 0 (a quad also takes all < 0). Types: 0 wall
strip (vertical, Ny = 0), 1 road, 2 a patch on the main straight, 3 grass,
4 apron. Only the lookup (060368D4-06036A9A) reads the file.

Written here, in list order (the first polygon that holds a point wins):
  CCE's wall strips and its type-2 patch, unchanged
  DUSA's road, apron and grass as types 1, 4 and 3
  DUSA's ground outside the edges as road: it only shows through where
  neither of the above lies, slivers between DUSA's road edge and CCE's
  walls (CCE had road there) and beyond the walls
Corners shared between DUSA polygons are snapped to one value, so
neighbours share their edges exactly.
"""
import math
import os
import struct
import sys

COURSE = 'COURSE0.BIN'
COL = 'DAYTONA/CS0_COL.BIN'
LOAD = 0x00220000
POLYS_AT = 0x8000
DUSA_GRID, DUSA_LISTS = 0x6660, 0xA660
TYPES = {0x01: 1, 0x41: 1, 0x02: 4, 0x04: 3, 0x80: 1}
KEEP = (0, 2)                   # CCE types kept: wall strips, the straight's patch
CELL = 32.0
SNAP = 1 / 64                   # corners closer than this are one corner


def dusa_polys(course):
    n = DUSA_GRID // 0x34
    for i in range(n):
        r = struct.unpack_from('>13i', course, 0x34 * i)
        edges = []
        for k in range(4):
            e = (r[4 + 2 * k], r[5 + 2 * k], not r[0] & (0x01000000 << k))
            if not edges or e != edges[-1]:
                edges.append(e)
        if len(edges) > 3 and edges[-1] == edges[0]:
            edges.pop()
        yield r, edges


def meet(e1, e2):
    """Where m1 x + k1 [+ z] = 0 meets m2 x + k2 [+ z] = 0."""
    (m1, k1, z1), (m2, k2, z2) = [(m / 65536, k / 65536, z) for m, k, z in (e1, e2)]
    det = m1 * z2 - m2 * z1
    x = (-k1 * z2 + k2 * z1) / det
    z = (-m1 * k2 + m2 * k1) / det
    return x, z


def ccw(vs):
    area = sum(vs[i][0] * vs[(i + 1) % len(vs)][1] - vs[(i + 1) % len(vs)][0] * vs[i][1] for i in range(len(vs)))
    return vs if area > 0 else vs[::-1]


def clip_area(vs, x0, x1, z0, z1):
    """Area of polygon vs inside the rectangle."""
    for axis, lim, keep_above in ((0, x0, True), (0, x1, False), (1, z0, True), (1, z1, False)):
        out = []
        for i, p in enumerate(vs):
            q = vs[(i + 1) % len(vs)]
            pin = p[axis] >= lim if keep_above else p[axis] <= lim
            qin = q[axis] >= lim if keep_above else q[axis] <= lim
            if pin:
                out.append(p)
            if pin != qin:
                t = (lim - p[axis]) / (q[axis] - p[axis])
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        vs = out
        if not vs:
            return 0.0
    return abs(sum(vs[i][0] * vs[(i + 1) % len(vs)][1] - vs[(i + 1) % len(vs)][0] * vs[i][1] for i in range(len(vs)))) / 2


def cells(vs):
    """CCE's cells (index = column + 64 x row) the polygon covers."""
    xs, zs = [v[0] for v in vs], [v[1] for v in vs]
    out = []
    for col in range(max(0, math.floor(min(xs) / CELL) + 32), min(63, math.floor(max(xs) / CELL) + 32) + 1):
        for row in range(max(0, 31 - math.ceil(max(zs) / CELL)), min(63, 32 - math.floor(min(zs) / CELL)) + 1):
            x0 = (col - 32) * CELL
            z1 = (32 - row) * CELL
            if clip_area(vs, x0 - 1e-3, x0 + CELL + 1e-3, z1 - CELL - 1e-3, z1 + 1e-3) > 1e-9:
                out.append(col + 64 * row)
    return out


def fix(v):
    return round(v * (1 << 20))


def main():
    src, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    course = open(os.path.join(src, COURSE), 'rb').read()
    col = open(os.path.join(cce, COL), 'rb').read()

    def cce_list(grid, c):
        p = struct.unpack_from('>I', col, grid + 4 * c)[0]
        if not p:
            return ()
        n = struct.unpack_from('>H', col, p - LOAD)[0]
        return struct.unpack_from(f'>{n}H', col, p - LOAD + 2)
    if any(cce_list(0, c) != cce_list(0x4000, c) for c in range(4096)):
        sys.exit('error: CCE\'s two grids differ; only one grid is written')

    # CCE's kept polygons, with the cells they were listed in
    kept = {}
    for c in range(4096):
        for i in cce_list(0, c):
            r = struct.unpack_from('>13i', col, POLYS_AT + 0x34 * i)
            if r[0] >> 16 in KEEP:
                kept.setdefault(i, (r, set()))[1].add(c)

    # DUSA's polygons, corners snapped
    snapped = {}

    def snap(p):
        key = (round(p[0] / SNAP), round(p[1] / SNAP))
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                q = snapped.get((key[0] + dx, key[1] + dz))
                if q and abs(q[0] - p[0]) < SNAP and abs(q[1] - p[1]) < SNAP:
                    return q
        snapped[key] = p
        return p

    ground, outside = [], []
    for r, edges in dusa_polys(course):
        if r[0] & 0xFF not in TYPES:
            sys.exit(f'error: DUSA polygon flags {r[0]:08X}')
        vs = ccw([snap(meet(edges[k], edges[(k + 1) % len(edges)])) for k in range(len(edges))])
        a, b, c = r[1] / 65536, r[2] / 65536, r[3] / 65536
        s = (1 << 24) / math.sqrt(a * a + b * b + 1)
        ny = round(s)
        rec = [(TYPES[r[0] & 0xFF] << 16) | (len(vs) == 3)]
        rec += [fix(t) for v in vs for t in v] + [0, 0] * (4 - len(vs))
        rec += [round(-a * s), ny, round(-b * s), round(c * ny / 4)]
        (outside if r[0] & 0x80 else ground).append((rec, vs))

    polys = [r for i, (r, _) in sorted(kept.items())] + [r for r, _ in ground + outside]
    lists = {}
    for n, (i, (r, was)) in enumerate(sorted(kept.items())):
        k = 3 if r[0] & 1 else 4
        vs = [(r[1 + 2 * j] / (1 << 20), r[2 + 2 * j] / (1 << 20)) for j in range(k)]
        for c in was | set(cells(vs)):
            lists.setdefault(c, []).append(n)
    for n, (r, vs) in enumerate(ground + outside, len(kept)):
        for c in cells(vs):
            lists.setdefault(c, []).append(n)

    out = bytearray(len(col))
    at = POLYS_AT
    for r in polys:
        struct.pack_into('>13i', out, at, *r)
        at += 0x34
    for c in sorted(lists):
        struct.pack_into('>I', out, 4 * c, LOAD + at)
        struct.pack_into('>I', out, 0x4000 + 4 * c, LOAD + at)
        struct.pack_into(f'>H{len(lists[c])}H', out, at, len(lists[c]), *lists[c])
        at += 2 + 2 * len(lists[c])
    if at > len(col):
        sys.exit(f'error: {at} bytes, CS0_COL.BIN holds {len(col)}')

    path = os.path.join(dst, COL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(out)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    if COL not in have:
        have.append(COL)
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'CS0_COL.BIN: {len(kept)} CCE polygons kept, {len(ground)} DUSA ground and {len(outside)} outside; '
          f'{len(lists)} cells, {at} of {len(col)} bytes')


if __name__ == '__main__':
    main()
