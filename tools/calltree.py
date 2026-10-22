"""Reachable callee set from a root, built from a Mednafen call trace.

Each trace line is '<cycle> <cpu> <callsite> <target>'. A callsite is
attributed to the nearest called target at or below it, which gives a
caller->callee graph good enough to walk the subtree under one function.

usage: calltree.py <call_trace.txt> <root> [lo hi]
"""
import bisect
import collections
import sys


def load(path, lo=0, hi=0xFFFFFFFF):
    edges = []
    for line in open(path):
        p = line.split()
        if len(p) < 4 or p[1] != 'M':
            continue
        site, tgt = int(p[2], 16), int(p[3], 16)
        if lo <= tgt < hi:
            edges.append((site, tgt))
    targets = sorted({t for _, t in edges})
    graph = collections.defaultdict(collections.Counter)
    for site, tgt in edges:
        i = bisect.bisect_right(targets, site) - 1
        if i >= 0:
            graph[targets[i]][tgt] += 1
    return graph


def reach(graph, root):
    seen, order, stack = {root}, [], [root]
    while stack:
        f = stack.pop()
        order.append(f)
        for c in sorted(graph[f]):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return order


def main():
    lo, hi = (int(sys.argv[3], 16), int(sys.argv[4], 16)) if len(sys.argv) > 4 else (0, 0xFFFFFFFF)
    g = load(sys.argv[1], lo, hi)
    for f in reach(g, int(sys.argv[2], 16)):
        print(f'{f:08x}  callees: {" ".join(f"{c:08x}" for c in sorted(g[f]))}')


if __name__ == '__main__':
    main()
