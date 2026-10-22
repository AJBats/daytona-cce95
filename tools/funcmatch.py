"""Match functions between two SH-2 binaries by normalized instruction shape.

Function starts are taken from bsr targets and from literal-pool words that
point into the code range. Each instruction is normalized to its mnemonic and
registers with immediates, displacements and addresses replaced by '#', so
identical source compiled against different struct layouts/constants still
compares equal.

usage: funcmatch.py <binA> <baseA> <lo> <hi> <binB> <baseB> <lo> <hi> [funcA ...]
  With funcA addresses: report best B match for each. Without: all A funcs.
       funcmatch.py --diff <binA> <baseA> <lo> <hi> <funcA> <binB> <baseB> <lo> <hi> <funcB>
"""
import difflib
import re
import struct
import sys

import capstone

MD = capstone.Cs(capstone.CS_ARCH_SH, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_SH2)
NUM = re.compile(r'-?(0x[0-9a-f]+|\d+)')


class Prog:
    def __init__(self, path, base, lo, hi):
        self.data = open(path, 'rb').read()
        self.base, self.lo, self.hi = base, lo, hi
        self.ins = {}
        for pc in range(lo, hi, 2):
            off = pc - base
            i = next(MD.disasm(self.data[off:off + 2], pc), None)
            self.ins[pc] = i
        starts = set()
        self.literals = set()
        for pc, i in self.ins.items():
            if i is not None:
                lm = re.match(r'mov\.([lw])\s+0x([0-9a-f]+),', f'{i.mnemonic} {i.op_str}')
                if lm:
                    la = int(lm.group(2), 16)
                    self.literals.update(range(la, la + (4 if lm.group(1) == 'l' else 2), 2))

            if i is None:
                continue
            if i.mnemonic == 'bsr':
                starts.add(int(i.op_str, 16))
            m = re.match(r'mov\.l\s+0x([0-9a-f]+),', f'{i.mnemonic} {i.op_str}')
            if m:
                lit = int(m.group(1), 16) - base
                if 0 <= lit + 4 <= len(self.data):
                    v = struct.unpack_from('>I', self.data, lit)[0]
                    if lo <= v < hi and v % 2 == 0 and self._looks_like_entry(v):
                        starts.add(v)
        self.starts = sorted(s for s in starts if lo <= s < hi)

    def _looks_like_entry(self, pc):
        i = self.ins.get(pc)
        return i is not None

    def body(self, start):
        """Normalized instructions from start through first rts+delay slot."""
        out = []
        pc = start
        while pc < self.hi and len(out) < 2000:
            if pc in self.literals:
                pc += 2
                continue
            i = self.ins.get(pc)
            if i is None:
                out.append('?')
            else:
                out.append(i.mnemonic + ' ' + NUM.sub('#', i.op_str))
                if i.mnemonic == 'rts':
                    nxt = self.ins.get(pc + 2)
                    out.append((nxt.mnemonic + ' ' + NUM.sub('#', nxt.op_str)) if nxt else '?')
                    break
            pc += 2
        return out


def best_match(a_body, b, cands):
    sm = difflib.SequenceMatcher(autojunk=False)
    sm.set_seq2(a_body)
    best = (0, None)
    for s in cands:
        bb = b.body(s)
        if abs(len(bb) - len(a_body)) > max(8, len(a_body)):
            continue
        sm.set_seq1(bb)
        if sm.real_quick_ratio() <= best[0] or sm.quick_ratio() <= best[0]:
            continue
        r = sm.ratio()
        if r > best[0]:
            best = (r, s)
    return best


def show_diff(a, fa, b, fb):
    """Side-by-side normalized diff of one function pair."""
    ab, bb = a.body(fa), b.body(fb)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ab, bb, autojunk=False).get_opcodes():
        if op == 'equal':
            print(f'  = {i2 - i1} identical instructions')
        else:
            for k in range(max(i2 - i1, j2 - j1)):
                l = ab[i1 + k] if i1 + k < i2 else ''
                r = bb[j1 + k] if j1 + k < j2 else ''
                print(f'  {op[0]} {l:34s} | {r}')


def main():
    if sys.argv[1] == '--diff':
        a = Prog(sys.argv[2], *(int(x, 16) for x in sys.argv[3:6]))
        b = Prog(sys.argv[7], *(int(x, 16) for x in sys.argv[8:11]))
        show_diff(a, int(sys.argv[6], 16), b, int(sys.argv[11], 16))
        return
    a = Prog(sys.argv[1], *(int(x, 16) for x in sys.argv[2:5]))
    b = Prog(sys.argv[5], *(int(x, 16) for x in sys.argv[6:9]))
    funcs = [int(x, 16) for x in sys.argv[9:]] or a.starts
    print(f'# A funcs found: {len(a.starts)}  B funcs found: {len(b.starts)}')
    for f in funcs:
        ab = a.body(f)
        r, s = best_match(ab, b, b.starts)
        exact = s is not None and b.body(s) == ab
        tag = 'IDENTICAL' if exact else f'{r:.2f}'
        print(f'{f:08x} len={len(ab):4d}  ->  {s or 0:08x}  {tag}')


if __name__ == '__main__':
    main()
