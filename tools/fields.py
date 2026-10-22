"""Car-struct field reads/writes per function, and a DUSA->CCE field map.

Tracks the two addressing forms the car code uses with the struct in r0:
  mov.w #off,rN ... mov.x @(r0,rN),rM / mov.x rM,@(r0,rN)
  mov.x @(disp,r0),r0 / mov.x r0,@(disp,r0) and @(disp,rN) after mov r0,rN
The mov.w index literal is tracked per register until overwritten.

usage: fields.py <binA> <baseA> <loA> <hiA> <binB> <baseB> <loB> <hiB> <fA:fB> [...]
"""
import collections
import re
import sys

import funcmatch as fm
from constdiff import raw
import difflib

IDX = re.compile(r'@\(r0, ?(r\d+)\)')
DSP = re.compile(r'@\((\d+), ?r0\)')
SIZE = {'b': 1, 'w': 2, 'l': 4}


def accesses(prog, start):
    """[(index_in_body, 'R'|'W', offset)] for the function body."""
    regs = {}
    out = []
    for k, (pc, norm, text, lit) in enumerate(raw(prog, start)):
        mn = text.split()[0]
        ops = text[len(mn):].strip()
        dst = ops.split(',')[-1].strip() if ',' in ops else None
        if mn == 'mov.w' and ops.startswith('lit,') and lit is not None:
            regs[dst] = lit
            continue
        m = IDX.search(ops)
        if m and m.group(1) in regs and mn.startswith('mov.'):
            kind = 'W' if ops.index('@') > ops.index(',') else 'R'
            out.append((k, kind, regs[m.group(1)]))
        m = DSP.search(ops)
        if m and mn.startswith('mov.'):
            sz = SIZE[mn[-1]]
            kind = 'W' if ops.index('@') > ops.index(',') else 'R'
            out.append((k, kind, int(m.group(1))))
        if dst in regs:
            del regs[dst]
    return out


def main():
    a = fm.Prog(sys.argv[1], *(int(x, 16) for x in sys.argv[2:5]))
    b = fm.Prog(sys.argv[5], *(int(x, 16) for x in sys.argv[6:9]))
    votes = collections.defaultdict(collections.Counter)
    for pair in sys.argv[9:]:
        fa, fb = (int(x, 16) for x in pair.split(':'))
        ra, rb = raw(a, fa), raw(b, fb)
        sm = difflib.SequenceMatcher(None, [x[1] for x in ra], [x[1] for x in rb], autojunk=False)
        amap = {}
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                amap[blk.a + k] = blk.b + k
        aa, bb = accesses(a, fa), accesses(b, fb)
        bidx = {k: (kind, off) for k, kind, off in bb}
        w = sorted({off for _, kind, off in aa if kind == 'W'})
        r = sorted({off for _, kind, off in aa if kind == 'R'})
        print(f'## {fa:08x}:{fb:08x}  DUSA writes {" ".join(hex(x) for x in w)}')
        print(f'   {"":17s}  DUSA reads  {" ".join(hex(x) for x in r)}')
        for k, kind, off in aa:
            if k in amap and amap[k] in bidx:
                votes[off][bidx[amap[k]][1]] += 1
    print('\n# field map DUSA -> CCE (votes)')
    for off in sorted(votes):
        best, n = votes[off].most_common(1)[0]
        alt = ', '.join(f'{hex(o)}:{c}' for o, c in votes[off].most_common()[1:3])
        print(f'  {off:#06x} -> {best:#06x}  ({n}{"; also " + alt if alt else ""})')


if __name__ == '__main__':
    main()
