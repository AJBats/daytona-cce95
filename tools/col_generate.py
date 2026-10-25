"""DUSA-style ground for CCE's own courses, made from CCE's collision files.

DUSA never had National Park Speedway or Desert City, so there is no DUSA
ground to copy; this builds what DUSA's would have been from CCE's
(docs/conformance.md, "Ground for CCE's own courses").

On the courses both games share, CCE's ground is DUSA's refined: 81-84% of
DUSA's corners are CCE corners, at the same heights (to +-0.01), with
cross-sections added between DUSA's (every 8 units on the banks, against 16)
and rows added across the banks, raised to a curve. CCE then gave each quad
one plane, which leaves steps where neighbours meet. DUSA's banks are a
straight ramp from edge to edge, split into two triangles that meet exactly.
So, on CCE's grid:

  1. Corner heights: the median of the planes of the ground polygons that
     share the corner (on Three Seven and Seaside, DUSA's corner heights;
     the median, because a few of CCE's quads are far from flat, up to 1
     unit off at a corner on Desert City).
  2. The grid: a quad's corners run around it, so its edges 0-1 / 2-3 and
     1-2 / 3-0 are its two opposite pairs. Which pair crosses the track is
     carried from quad to quad through shared edges; the choice whose
     strips (quads chained through their across edges) run longest is the
     one along the track. Big flat quads (over 100 square units, infields)
     are left out: they join unrelated roads into one cross-section.
  3. Cross-section lines: chains of across edges. Every other line is
     kept, counted out from the longest strip; a line whose neighbours
     disagree is kept.
  4. Cells: per strip, the quads between consecutive kept lines. Within a
     section, neighbouring cells of the same surface type merge across, so
     a bank is one cell from edge to edge.
  5. Each merged cell: one quad if its four corners are coplanar, else two
     triangles through them, split on the diagonal whose two corners lie
     lower, as DUSA's are (27 of the 29 Dinosaur Canyon cells that match a
     DUSA pair). Quads outside the grid become two triangles each (CCE's
     corners, but no steps).
  6. Road direction (DUSA's straightening target, patches/road_direction.s):
     each cell's along-track chord, pointed the way the race goes. That way
     is flooded over the ground from the polygon under the start grid (its
     heading), through shared edges and corners, the most nearly parallel
     neighbour first.

A merged cell's sides are chords; the corners it drops lie on CCE's
curved outline, where its neighbours keep them. Where a dropped corner
lies outside the chord, a sliver triangle in the plane of the side's
triangle fills to it, so the neighbours (and the wall strips) meet the
cell without gaps or steps. Where it lies inside, the neighbour or wall
strip, listed first, covers the overlap. Each list holds CCE's wall strips
first, then the new polygons. Each new polygon is listed, per grid, in the
cells its CCE quads were listed in there (Desert City crosses itself; the
grids differ where it does).

Tried on Three Seven (CCE's mesh in, DUSA's out to compare), along the
user's turn-1 line: roll vs DUSA's ground 0.67 deg rms (CCE's 2.19),
roll reversals 11 (DUSA 13, CCE 27), deepest -16.2 deg (DUSA -17.3, CCE
-20.0). Turn 2's quads don't form a clean grid there (CCE derived them
from DUSA's irregular mesh), so they only lose their steps. CCE's own
courses are cleaner grids: 95% of National Park's quads and 79% of Desert
City's merge.
"""
import collections
import heapq
import math
import struct

import numpy as np

LOAD = 0x00220000
POLYS_AT = 0x8000


def fix(v):
    return round(v * (1 << 20))


def ccw(vs):
    area = sum(vs[i][0] * vs[(i + 1) % len(vs)][1] - vs[(i + 1) % len(vs)][0] * vs[i][1] for i in range(len(vs)))
    return vs if area > 0 else vs[::-1]


class Ground:
    def __init__(self, col):
        self.col = col

        def lst(grid, c):
            p = struct.unpack_from('>I', col, grid + 4 * c)[0]
            if not p:
                return ()
            n = struct.unpack_from('>H', col, p - LOAD)[0]
            return struct.unpack_from(f'>{n}H', col, p - LOAD + 2)
        self.grids = [{c: lst(g, c) for c in range(4096) if lst(g, c)} for g in (0, 0x4000)]
        ids = sorted({i for g in self.grids for l in g.values() for i in l})
        self.polys = {i: struct.unpack_from('>13i', col, POLYS_AT + 0x34 * i) for i in ids}
        self.walls, self.quads, self.tris, self.type = {}, {}, {}, {}
        self.pos = {}
        hs = collections.defaultdict(list)
        for i, r in self.polys.items():
            if r[0] >> 16 == 0 or not r[10]:
                self.walls[i] = r
                continue
            vs = []
            for j in range(3 if r[0] & 1 else 4):
                x, z = r[1 + 2 * j], r[2 + 2 * j]
                v = (x >> 12, z >> 12)                       # 1/256 unit
                self.pos[v] = (x / 2**20, z / 2**20)
                hs[v].append(4 * r[12] / r[10] - (r[9] * x + r[11] * z) / r[10] / 2**20)
                vs.append(v)
            (self.tris if r[0] & 1 else self.quads)[i] = vs
            self.type[i] = r[0] >> 16
        self.h = {v: float(np.median(l)) for v, l in hs.items()}
        self.free = {i: q for i, q in self.quads.items() if self.area(q) > 100 and self.planar(q, 0.01)}
        for i in self.free:
            del self.quads[i]

    def P(self, v):
        return (*self.pos[v], self.h[v])

    def area(self, q):
        p = [self.pos[v] for v in q]
        return abs(sum(p[j][0] * p[(j + 1) % len(p)][1] - p[(j + 1) % len(p)][0] * p[j][1] for j in range(len(p)))) / 2

    def planar(self, q, tol):
        P = np.array([self.P(v) for v in q])
        A = np.c_[P[:, 0], P[:, 1], np.ones(len(P))]
        sol = np.linalg.lstsq(A, P[:, 2], rcond=None)[0]
        return np.abs(A @ sol - P[:, 2]).max() < tol

    # the grid -----------------------------------------------------------------

    def label(self):
        edges = collections.defaultdict(list)
        for i, q in self.quads.items():
            for j in range(4):
                edges[frozenset((q[j], q[(j + 1) % 4]))].append((i, j))
        self.edges = edges
        par = {}
        for seed in self.quads:
            if seed in par:
                continue
            par[seed] = 0
            stack = [seed]
            while stack:
                i = stack.pop()
                for j in range(4):
                    across = j % 2 == par[i]
                    for k, jj in edges[frozenset((self.quads[i][j], self.quads[i][(j + 1) % 4]))]:
                        if k != i and k not in par:
                            par[k] = jj % 2 if across else 1 - jj % 2
                            stack.append(k)
        best = None
        for flip in (0, 1):
            self.par = {i: p ^ flip for i, p in par.items()}
            self.find_strips()
            score = sum(sorted((len(s) for s in self.strip_list), reverse=True)[:6])
            if best is None or score > best[0]:
                best = (score, dict(self.par))
        self.par = best[1]
        self.find_strips()

    def across_edges(self, i):
        q, p = self.quads[i], self.par[i]
        return (q[p], q[p + 1]), (q[(p + 2) % 4], q[(p + 3) % 4])

    def find_strips(self):
        nb = collections.defaultdict(list)
        for i in self.quads:
            for a, b in self.across_edges(i):
                for k, jj in self.edges[frozenset((a, b))]:
                    if k != i and jj % 2 == self.par[k]:
                        nb[i].append(k)
        self.nb = nb
        seen, strips = set(), []
        for i in self.quads:
            if i in seen:
                continue
            comp, stack = [], [i]
            while stack:
                k = stack.pop()
                if k not in seen:
                    seen.add(k)
                    comp.append(k)
                    stack += [n for n in nb[k] if n not in seen]
            strips.append(comp)
        self.strip_list = strips

    def ordered(self, strip):
        s = set(strip)
        ends = [i for i in strip if sum(n in s for n in self.nb[i]) < 2] or [strip[0]]
        order, prev, cur = [], None, ends[0]
        while cur is not None:
            order.append(cur)
            nxt = [n for n in self.nb[cur] if n in s and n != prev and n not in order]
            prev, cur = cur, (nxt[0] if nxt else None)
        return order

    def lines(self):
        parent = {}

        def f(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for i in self.quads:
            for a, b in self.across_edges(i):
                ra, rb = f(a), f(b)
                if ra != rb:
                    parent[ra] = rb
        self.line_of = {v: f(v) for v in parent}
        members = collections.defaultdict(list)
        for v, c in self.line_of.items():
            members[c].append(v)
        self.line_order = {c: self.chain(vs) for c, vs in members.items()}
        return members

    def chain(self, verts):
        vs = set(verts)
        adj = collections.defaultdict(set)
        for i in self.quads:
            for a, b in self.across_edges(i):
                if a in vs and b in vs:
                    adj[a].add(b)
                    adj[b].add(a)
        ends = [v for v in vs if len(adj[v]) == 1]
        if len(ends) != 2 or any(len(adj[v]) > 2 for v in vs):
            return None
        order, prev = [ends[0]], None
        while len(order) < len(vs):
            nxt = [n for n in adj[order[-1]] if n != prev]
            if not nxt:
                return None
            prev = order[-1]
            order.append(nxt[0])
        return order

    # cells --------------------------------------------------------------------

    def cells(self):
        """Merged cells: (corners, type, quads, strip index of the first quad, reversed)."""
        self.label()
        members = self.lines()
        L = self.line_of
        succ = collections.defaultdict(set)
        self.seqs = []
        for s in self.strip_list:
            o = self.ordered(s)
            seq = []
            for k, q in enumerate(o):
                a, b = self.across_edges(q)
                ca, cb = L[a[0]], L[b[0]]
                if k + 1 < len(o):
                    nxt = set(self.quads[o[k + 1]])
                    c_next = ca if a[0] in nxt and a[1] in nxt else cb
                elif k > 0:
                    prv = set(self.quads[o[k - 1]])
                    c_next = cb if a[0] in prv and a[1] in prv else ca
                else:
                    c_next = cb
                c_prev = cb if c_next == ca else ca
                seq.append((c_prev, q, c_next))
                succ[c_prev].add(c_next)
                succ[c_next].add(c_prev)
            self.seqs.append(seq)
        start = max(self.seqs, key=len)[0][0]
        dist = {start: 0}
        dq = collections.deque([start])
        while dq:
            c = dq.popleft()
            for n in succ[c]:
                if n not in dist:
                    dist[n] = dist[c] + 1
                    dq.append(n)
        keep = {c: c not in dist or dist[c] % 2 == 0 or
                any(abs(dist.get(n, 0) - dist[c]) != 1 for n in succ[c] if n in dist) for c in members}
        by_sec = collections.defaultdict(list)
        for si, seq in enumerate(self.seqs):
            cur, quads = None, []
            for c_prev, q, c_next in seq:
                if keep[c_prev]:
                    cur, quads = c_prev, []
                quads.append(q)
                if keep[c_next] and cur is not None and cur != c_next:
                    a, b, qs, rev = cur, c_next, quads, False
                    if (b, a) < (a, b):
                        a, b, qs, rev = b, a, qs[::-1], True
                    by_sec[(a, b)].append((qs, si, rev))
                    cur, quads = c_next, []
        out = []
        for (a, b), groups in by_sec.items():
            oa, ob = self.line_order.get(a), self.line_order.get(b)
            if not oa or not ob:
                continue
            ia = {v: k for k, v in enumerate(oa)}
            ib = {v: k for k, v in enumerate(ob)}
            pa, pb = [], []
            for qs, si, rev in groups:
                ea = [ia[v] for v in self.quads[qs[0]] if v in ia]
                eb = [ib[v] for v in self.quads[qs[-1]] if v in ib]
                if ea and eb:
                    pa.append(min(ea))
                    pb.append(min(eb))
            if len(pa) > 1 and np.corrcoef(pa, pb)[0, 1] < 0:
                ob = ob[::-1]
                ib = {v: k for k, v in enumerate(ob)}
            items = []
            for qs, si, rev in groups:
                ea = [v for v in self.quads[qs[0]] if v in ia]
                eb = [v for v in self.quads[qs[-1]] if v in ib]
                if len(ea) != 2 or len(eb) != 2 or abs(ia[ea[0]] - ia[ea[1]]) != 1 or abs(ib[eb[0]] - ib[eb[1]]) != 1:
                    items = None
                    break
                types = {self.type[q] for q in qs}
                items.append((min(ia[ea[0]], ia[ea[1]]), min(ib[eb[0]], ib[eb[1]]), qs,
                              types.pop() if len(types) == 1 else -1, si, rev))
            if not items:
                continue
            items.sort(key=lambda it: it[:2])
            run = []
            for it in items + [None]:
                if it and run and it[3] != -1 and it[3] == run[-1][3] and it[0] == run[-1][0] + 1 \
                        and it[1] == run[-1][1] + 1:
                    run.append(it)
                    continue
                if run:
                    corners = [oa[run[0][0]], oa[run[-1][0] + 1], ob[run[-1][1] + 1], ob[run[0][1]]]
                    # line b may run the other way (a section of one strip has nothing to line it up by):
                    # take the corner order that makes a ring, not a bow tie
                    ring = lambda c: abs(sum(self.pos[c[i]][0] * self.pos[c[(i + 1) % 4]][1] -
                                             self.pos[c[(i + 1) % 4]][0] * self.pos[c[i]][1] for i in range(4)))
                    swapped = [corners[0], corners[1], corners[3], corners[2]]
                    if ring(swapped) > ring(corners):
                        corners = swapped
                    out.append((corners, run[0][3], [q for r in run for q in r[2]], run[0][4], run[0][5]))
                run = [it] if it else []
        return out

    # polygons -----------------------------------------------------------------

    def split(self, corners, qs):
        P = [self.P(v) for v in corners]

        def plane(p, q, r):
            u = np.subtract(q, p)
            w = np.subtract(r, p)
            n = np.cross([u[0], u[1], u[2]], [w[0], w[1], w[2]])
            a, b = -n[0] / n[2], -n[1] / n[2]
            return a, b, p[2] - a * p[0] - b * p[1]
        a, b, c = plane(P[0], P[1], P[2])
        if abs(a * P[3][0] + b * P[3][1] + c - P[3][2]) < 0.002:
            return [(0, 1, 2, 3)]
        # DUSA's own splits join the two corners whose heights add up lower (27 of the 29 Dinosaur Canyon
        # cells that match a DUSA pair; the cell at the start of Three Seven's turn 1 too)
        if P[0][2] + P[2][2] <= P[1][2] + P[3][2]:
            return [(0, 1, 2), (0, 2, 3)]
        return [(0, 1, 3), (1, 2, 3)]

    def build(self, start, heading):
        """New polygons: (record, (x, z) corners, CCE quads they replace)."""
        out = self.cells()
        # the way the race goes over every ground polygon: from the polygon under the start grid (the start
        # heading), flooded through shared edges and corners, the most nearly parallel neighbour first; a grid quad
        # takes its own along-track axis pointed that way, the rest (big flat quads, triangles) their neighbour's
        ground = {**self.quads, **self.free, **self.tris}
        cent = {i: np.mean([self.pos[v] for v in q], axis=0) for i, q in ground.items()}
        axes = {}                                    # a grid quad's two axes, its along-track one first
        for i, q in self.quads.items():
            a_, b_ = self.across_edges(i)
            pair = []
            for (p0, p1), (p2, p3) in ((a_, b_), ((a_[0], b_[1]), (a_[1], b_[0]))):
                v = np.mean([self.pos[p2], self.pos[p3]], axis=0) - np.mean([self.pos[p0], self.pos[p1]], axis=0)
                pair.append(v / (np.linalg.norm(v) or 1))
            axes[i] = pair
        at_vertex = collections.defaultdict(set)
        for i, q in ground.items():
            for v in q:
                at_vertex[v].add(i)
        fwd = np.array([-math.sin(heading / 65536 * 2 * math.pi), math.cos(heading / 65536 * 2 * math.pi)])
        first = min(ground, key=lambda i: math.dist(cent[i], start))
        way = {}
        heap = [(-1.0, 0, first, tuple(fwd))]
        tick = 0
        while heap:
            _, _, i, d = heapq.heappop(heap)
            if i in way:
                continue
            d = np.array(d)
            if i in axes:
                # the along-track axis, unless the grid's labels are crossed here (a big quad on a straight)
                ax = max(axes[i], key=lambda a: abs(np.dot(a, d)) + (0.2 if a is axes[i][0] else 0))
                way[i] = ax * (1 if np.dot(ax, d) >= 0 else -1)
            else:
                way[i] = d
            for v in ground[i]:
                for n in at_vertex[v]:
                    if n not in way:
                        tick += 1
                        prio = max(abs(np.dot(a, way[i])) for a in axes[n]) if n in axes else 0.5
                        heapq.heappush(heap, (-prio, tick, n, tuple(way[i])))
        self.way, self.cent = way, cent

        def toward(vec, qs):
            d = sum(self.way[q] for q in qs if q in self.way)
            return vec if np.dot(vec, d) >= 0 else -vec

        def direction(vec):
            return round(math.atan2(-vec[0], vec[1]) * 65536 / (2 * math.pi)) & 0xFFFF

        polys, used = [], set()

        def emit(pts, typ, vec, qs):
            vs = ccw([(p[0], p[1]) for p in pts])
            area = abs(sum(vs[i][0] * vs[(i + 1) % len(vs)][1] - vs[(i + 1) % len(vs)][0] * vs[i][1]
                           for i in range(len(vs)))) / 2
            if area < 0.01:
                return
            (x0, z0, y0), (x1, z1, y1), (x2, z2, y2) = pts[:3]
            u, w = (x1 - x0, z1 - z0, y1 - y0), (x2 - x0, z2 - z0, y2 - y0)
            nx, nz, ny = u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]
            if ny < 0:
                nx, nz, ny = -nx, -nz, -ny
            s = (1 << 24) / math.sqrt(nx * nx + ny * ny + nz * nz)
            Ny = round(ny * s)
            c = y0 + nx / ny * x0 + nz / ny * z0
            d = direction(vec) if vec is not None else None
            rec = [(typ << 16) | (len(vs) == 3) | (0 if d is None else 2 | d & 0xFFFC)]
            rec += [fix(t) for v in vs for t in v] + [0, 0] * (4 - len(vs))
            rec += [round(nx * s), Ny, round(nz * s), round(c * Ny / 4)]
            polys.append((rec, vs, qs))

        for corners, t, qs, si, rev in out:
            P = [self.P(v) for v in corners]
            ring = [(p[0], p[1]) for p in P]
            area = abs(sum(ring[i][0] * ring[(i + 1) % 4][1] - ring[(i + 1) % 4][0] * ring[i][1] for i in range(4))) / 2
            if area < 0.05 or len({(round(x, 3), round(z, 3)) for x, z in ring}) < 4:
                continue
            # the chord between the cell's two section lines, or between its sides where the grid's labels are
            # crossed (big quads on a straight): whichever lies along the way the race goes
            d = sum(self.way[q] for q in qs if q in self.way)
            vec = max((np.mean([P[2][:2], P[3][:2]], axis=0) - np.mean([P[0][:2], P[1][:2]], axis=0),
                       np.mean([P[1][:2], P[2][:2]], axis=0) - np.mean([P[0][:2], P[3][:2]], axis=0)),
                      key=lambda v: abs(np.dot(v / (np.linalg.norm(v) or 1), d)))
            vec = toward(vec, qs)
            tris = self.split(corners, qs)
            for tri in tris:
                emit([P[k] for k in tri], t, vec, qs)
            used.update(qs)
            # the corners the cell drops from its sides: where one lies outside the side's chord, the sliver
            # between them (A, dropped corners, B) continues the side's triangle, so its neighbours meet it
            sides = collections.Counter()
            for q in qs:
                Lq = self.quads[q]
                for j in range(4):
                    sides[frozenset((Lq[j], Lq[(j + 1) % 4]))] += 1
            nxt = collections.defaultdict(list)
            for e, n in sides.items():
                if n == 1:
                    u, w = tuple(e)
                    nxt[u].append(w)
                    nxt[w].append(u)
            cset = set(corners)
            mid = np.mean(ring, axis=0)
            for k in range(4):
                A, B = corners[k], corners[(k + 1) % 4]
                # walk the cell's outline from A each way, collecting dropped corners, until B
                for first in nxt[A]:
                    path, prev, cur = [], A, first
                    while cur != B and cur not in cset and len(path) < 16:
                        path.append(cur)
                        step = [n for n in nxt[cur] if n != prev]
                        if not step:
                            break
                        prev, cur = cur, step[0]
                    if cur == B:
                        break
                if cur != B or not path:
                    continue
                tri = next(tr for tr in tris if k in tr and (k + 1) % 4 in tr)
                (xa, za, ya), (xb, zb, yb), (xc, zc, yc) = [P[j] for j in tri[:3]]
                det = (xb - xa) * (zc - za) - (xc - xa) * (zb - za)

                def height(x, z):
                    wb = ((x - xa) * (zc - za) - (xc - xa) * (z - za)) / det
                    wc = ((xb - xa) * (z - za) - (x - xa) * (zb - za)) / det
                    return ya + wb * (yb - ya) + wc * (yc - ya)
                (x0, z0), (x1, z1) = self.pos[A], self.pos[B]
                side = lambda x, z: (x1 - x0) * (z - z0) - (z1 - z0) * (x - x0)
                inside = side(*mid)
                pts = [self.pos[A]] + [self.pos[v] for v in path] + [self.pos[B]]
                for j in range(1, len(pts) - 1):
                    x, z = pts[j]
                    if side(x, z) * inside < 0:
                        tr = [pts[0], pts[j], pts[j + 1]] if j + 1 < len(pts) else [pts[0], pts[j], pts[-1]]
                        emit([(x, z, height(x, z)) for x, z in tr], t, vec, qs)
        for i, q in self.quads.items():
            if i in used:
                continue
            a, b = self.across_edges(i)
            vec = np.mean([self.pos[v] for v in b], axis=0) - np.mean([self.pos[v] for v in a], axis=0)
            vec = toward(vec, [i])
            parts = [(0, 1, 2, 3)] if self.planar(q, 0.002) else [(0, 1, 2), (0, 2, 3)]
            for tri in parts:
                emit([self.P(q[k]) for k in tri], self.type[i], vec, [i])
        for i, q in list(self.free.items()) + list(self.tris.items()):
            emit([self.P(v) for v in q], self.type[i], self.way.get(i), [i])
        self.merged = used
        return polys

    def write(self, polys):
        """The new file: CCE's wall strips, then the new polygons."""
        member = [collections.defaultdict(set), collections.defaultdict(set)]
        for g, grid in enumerate(self.grids):
            for c, lst in grid.items():
                for i in lst:
                    member[g][i].add(c)
        ids = [i for i in self.way]
        pts = np.array([self.cent[i] for i in ids])
        recs = []
        lists = [collections.defaultdict(list), collections.defaultdict(list)]

        def add(rec, cells_by_grid):
            n = len(recs)
            recs.append(struct.pack('>13i', *rec))
            for g in (0, 1):
                for c in sorted(cells_by_grid[g]):
                    lists[g][c].append(n)

        def with_dir(i):
            r = list(self.polys[i])
            k = 3 if r[0] & 1 else 4
            at = np.array([sum(r[1:1 + 2 * k:2]) / k, sum(r[2:2 + 2 * k:2]) / k]) / 2**20
            vec = self.way[ids[int(np.argmin(np.hypot(*(pts - at).T)))]]
            r[0] = r[0] & 0xFFFF0001 | 2 | round(math.atan2(-vec[0], vec[1]) * 65536 / (2 * math.pi)) & 0xFFFC
            return r
        for i in sorted(self.walls):
            add(with_dir(i), [member[0][i], member[1][i]])
        from col_convert import cells as geo_cells
        for rec, vs, qs in polys:
            geo = set(geo_cells(vs))
            add(rec, [geo & set().union(*(member[g][q] for q in qs)) for g in (0, 1)])
        out = bytearray(len(self.col))
        at = POLYS_AT
        for r in recs:
            out[at:at + 0x34] = r
            at += 0x34
        written = {}
        for g in (0, 1):
            for c, lst in lists[g].items():
                key = tuple(lst)
                if key not in written:
                    written[key] = LOAD + at
                    struct.pack_into(f'>H{len(lst)}H', out, at, len(lst), *lst)
                    at += 2 + 2 * len(lst)
                struct.pack_into('>I', out, 0x4000 * g + 4 * c, written[key])
        if at > len(out):
            raise ValueError(f'{at} bytes, the slot holds {len(out)}')
        return bytes(out), at


def generate(col, start, heading):
    """CCE file bytes -> (DUSA-style file bytes, report)."""
    G = Ground(col)
    polys = G.build(start, heading)
    data, size = G.write(polys)
    return data, (f'{len(G.walls)} wall strips; {len(polys)} new polygons for CCE\'s '
                  f'{len(G.quads) + len(G.free) + len(G.tris)} ({len(G.merged)} quads merged); {size} of {len(col)} bytes')
