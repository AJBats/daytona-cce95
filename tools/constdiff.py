"""List operand and literal differences between two aligned functions.

Instructions are aligned by normalized shape (as in funcmatch). Within the
aligned runs, any instruction whose raw operands or loaded literal differ is
printed. Struct offsets show up as differing displacements / mov.w index
literals; tuning shows up as differing immediates / mov.l literals.

usage: constdiff.py <binA> <baseA> <loA> <hiA> <binB> <baseB> <loB> <hiB> <fA:fB> [...]
"""
import difflib
import re
import struct
import sys

import funcmatch as fm

LIT = re.compile(r'(mov\.[lw])\s+0x([0-9a-f]+),')


def raw(prog, start):
    """[(pc, normalized, text, literal_value_or_None)] matching prog.body()."""
    out = []
    pc = start
    while pc < prog.hi and len(out) < 2000:
        if pc in prog.literals:
            pc += 2
            continue
        i = prog.ins.get(pc)
        if i is None:
            out.append((pc, '?', '?', None))
        else:
            text = f'{i.mnemonic} {i.op_str}'
            lit = None
            m = LIT.match(text)
            if m:
                off = int(m.group(2), 16) - prog.base
                if 0 <= off + 4 <= len(prog.data):
                    lit = (struct.unpack_from('>I', prog.data, off)[0] if m.group(1) == 'mov.l'
                           else struct.unpack_from('>H', prog.data, off)[0])
                text = re.sub(r'0x[0-9a-f]+,', 'lit,', text)
            out.append((pc, i.mnemonic + ' ' + fm.NUM.sub('#', i.op_str), text, lit))
            if i.mnemonic == 'rts':
                n = prog.ins.get(pc + 2)
                out.append((pc + 2, (n.mnemonic + ' ' + fm.NUM.sub('#', n.op_str)) if n else '?',
                            f'{n.mnemonic} {n.op_str}' if n else '?', None))
                break
        pc += 2
    return out


def diff(a, fa, b, fb):
    ra, rb = raw(a, fa), raw(b, fb)
    sm = difflib.SequenceMatcher(None, [x[1] for x in ra], [x[1] for x in rb], autojunk=False)
    rows = []
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            pa, _, ta, la = ra[blk.a + k]
            pb, _, tb, lb = rb[blk.b + k]
            if ta != tb or la != lb:
                rows.append((pa, ta, la, pb, tb, lb))
    return sm.ratio(), rows


BRANCH = {'bt', 'bf', 'bra', 'bsr', 'bt/s', 'bf/s'}
DISP = re.compile(r'@\((\d+),')


def classify(a, b, row):
    """Kind of difference: branch, field, call, table, const."""
    pa, ta, la, pb, tb, lb = row
    mn = ta.split()[0]
    if mn in BRANCH:
        return 'branch'
    if DISP.search(ta) and DISP.search(tb) and DISP.findall(ta) != DISP.findall(tb):
        return 'field'
    if la is not None and lb is not None:
        if mn == 'mov.w' and la < 0x400 and lb < 0x400:
            return 'field?'
        if a.lo <= la < a.hi and b.lo <= lb < b.hi:
            return 'call'
        if la >= 0x06000000 and (lb >= 0x06000000 or 0x00200000 <= lb < 0x00300000):
            return 'table'
    return 'const'


def fmt_lit(v):
    return '' if v is None else f'=0x{v:x}'


def main():
    a = fm.Prog(sys.argv[1], *(int(x, 16) for x in sys.argv[2:5]))
    b = fm.Prog(sys.argv[5], *(int(x, 16) for x in sys.argv[6:9]))
    for pair in sys.argv[9:]:
        fa, fb = (int(x, 16) for x in pair.split(':'))
        r, rows = diff(a, fa, b, fb)
        rows = [(classify(a, b, row), row) for row in rows]
        rows = [x for x in rows if x[0] != 'branch']
        print(f'## {fa:08x} : {fb:08x}  ratio {r:.2f}  {len(rows)} operand diffs')
        for kind, (pa, ta, la, pb, tb, lb) in rows:
            print(f'  {kind:6s} {pa:08x} {ta:28s}{fmt_lit(la):12s} | {pb:08x} {tb:28s}{fmt_lit(lb)}')


if __name__ == '__main__':
    main()
