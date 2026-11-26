"""Check that our bytes don't land on bytes CCE's live code still uses.

A patch that takes "free" space in one of the game's programs (a code
cave) is only safe if nothing live reaches into that space. "Nothing
branches to it" is not enough on the SH-2: a compiler keeps one literal
pool for several neighbouring functions, and live code loads constants
from a dead function's pool with mov.l/mov.w @(disp,PC). A function can
also be live through a pointer only: a task's address in a neighbour's
pool, a table of handlers. Three caves broke live code that way
(OPEN_ISSUES, 2026-11-25), and patches/vdp1x.s's cave once froze the
attract.

So the build compares each program as we ship it with CCE's own, works out
which code is live in the shipped program by following its control flow,
and fails when live code we left unchanged:

  1. reaches into a cave (a range a patch declares with `.cave`): loads a
     literal there, branches there, or holds a pointer there (in a literal
     it loads, or in an aligned word anywhere in the program);
  2. outside the caves, loads a literal whose bytes we changed, where the
     change is more than literals: a literal pool overwritten by new code
     or data. A change made only of loaded literals is a deliberate tuning
     or a repointed call and passes.

Patches declare their caves with `.cave <first> <last>` in the .s (an
inclusive range, as the comments write them), which tools/mkpatch.py
copies into the .patch as `#!cave <disc path> <first> <last>`; a
hand-written .patch writes that line itself. A cave is the dead space a
patch claims, not just the bytes it writes, so the check also covers the
part still unused.

Live code is found statically, which covers rare paths (two-player
options, manual-gearbox keys) that no emulator run would visit: every path
of every reached function from the program's entry, calls through
literals, switch tables (mova + braf), task and handler pointers held in
literals or aligned words, and the addresses our own code elsewhere (the
attract, the VDP1 pass, the crash screen) and the other programs name. A
candidate pointer counts as code when the bytes there decode as SH-2
instructions up to a return or jump. The shipped program is traced as it
ships and as the attract's CCE choice puts some of CCE's bytes back at run
time (tools/title_convert.py's CCE_SWITCH); code live in either is live.

usage:
  cave_check.py check <extracted dir> <built dir>
      The build's check; exits 1 on a finding.
  cave_check.py free <extracted dir> <built dir> [disc path] [min bytes] [cdl ...]
      Space for a new cave: whole functions (or runs of zeros) that neither
      CCE's program nor ours executes or loads, that nothing points into and
      no patch writes; with Mednafen CDL dumps (cdl_dump) taken while that
      program was loaded, also none of whose bytes ran or were read. Each
      still has to be read before it is used, then declared with .cave.
  cave_check.py refs <extracted dir> <built dir> <disc path> <first> [last]
      Everything in the shipped program that reaches into a range, and
      what reached it in CCE's.
"""
import bisect
import collections
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The SH-2 programs patches change, by disc path: load address. The
# overlays all load at 06028000, one at a time; DAYTONA/0 stays resident.
SH2 = {
    'DAYTONA/0': 0x06005200,
    'DAYTONA/RACE.BIN': 0x06028000,
    'DAYTONA/SLCT.BIN': 0x06028000,
    'DAYTONA/NAME.BIN': 0x06028000,
    'DAYTONA/BKUP.BIN': 0x06028000,
    'DAYTONA/RESULT2P.BIN': 0x06028000,
}
KERNEL = 'DAYTONA/0'
PATCH_GLOBS = ['patches/*.patch', 'patches/options/*.patch']

_valid = None


def valid_table():
    """SH7604 opcodes capstone decodes, as a 64K table."""
    global _valid
    if _valid is None:
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_SH, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_SH2)
        _valid = bytearray(65536)
        for w in range(65536):
            if next(md.disasm(struct.pack('>H', w), 0), None) is not None:
                _valid[w] = 1
    return _valid


def s8(v):
    return v - 0x100 if v & 0x80 else v


def s12(v):
    return v - 0x1000 if v & 0x800 else v


def writes(w):
    """Registers an instruction may write (approximate, for literal tracking)."""
    hi, n, m, lo = w >> 12, (w >> 8) & 15, (w >> 4) & 15, w & 15
    if hi in (0x5, 0x7, 0x9, 0xD, 0xE):
        return {n}
    if hi == 0x6:
        return {n, m} if lo in (4, 5, 6) else {n}          # post-increment loads move Rm
    if hi == 0x0:
        if lo in (2, 9, 10, 12, 13, 14):                    # stc, movt, sts, mov @(r0,Rm),Rn
            return {n}
        return {n, m} if lo == 15 else set()                # mac.l
    if hi == 0x2:
        return {n} if lo in (4, 5, 6, 9, 10, 11, 13) else set()
    if hi == 0x3:
        return set() if lo in (0, 2, 3, 5, 6, 7, 13) else {n}
    if hi == 0x4:
        if lo in (10, 11, 14) or w & 0xFF in (0x11, 0x15, 0x1B):
            return set()                                    # lds, ldc, jsr, jmp, cmp/pz, cmp/pl, tas
        return {n, m} if lo == 15 else {n}
    if hi == 0x8:
        return {0} if n in (4, 5) else set()
    if hi == 0xC:
        return {0} if n in (4, 5, 6, 7, 9, 10, 11) else set()
    return set()


def delayed(w):
    """A branch with a delay slot: bra, bsr, bt/s, bf/s, jmp, jsr, braf, bsrf, rts, rte."""
    return (w >> 12 in (0xA, 0xB) or w >> 8 in (0x8D, 0x8F) or w & 0xF0FF in (0x402B, 0x400B, 0x0023, 0x0003)
            or w in (0x000B, 0x002B))


def unconditional(w):
    """A branch that doesn't come back past its delay slot: bra, jmp, braf, rts, rte."""
    return w >> 12 == 0xA or w & 0xF0FF in (0x402B, 0x0023) or w in (0x000B, 0x002B)


def addressed(w):
    """Registers an instruction uses as a memory address."""
    hi, n, m, lo = w >> 12, (w >> 8) & 15, (w >> 4) & 15, w & 15
    if hi == 0x6 and lo in (0, 1, 2, 4, 5, 6):
        return {m}
    if hi == 0x5:
        return {m}
    if hi == 0x1:
        return {n}
    if hi == 0x2 and lo in (0, 1, 2, 4, 5, 6):
        return {n}
    if hi == 0x8 and n in (0, 1):
        return {m}
    if hi == 0x8 and n in (4, 5):
        return {m}
    if hi == 0x0 and lo in (4, 5, 6, 12, 13, 14):
        return {n if lo < 8 else m, 0}
    if hi in (0x0, 0x4) and lo == 15:
        return {n, m}
    if hi == 0x4 and (w & 0xFF) in (0x1B, 0x06, 0x07, 0x16, 0x17, 0x26, 0x27, 0x02, 0x03, 0x12, 0x13, 0x22, 0x23):
        return {n}
    return set()


def prologue(w):
    """A word a function typically starts with: a push to the stack."""
    return w & 0xFF0F == 0x2F06 or w in (0x4F22, 0x4F12, 0x4F02, 0x4F13, 0x4F03) or w >> 8 == 0x7F


class Program:
    """One SH-2 program and its live code."""

    def __init__(self, data, base, extra=()):
        self.data, self.base, self.end = data, base, base + len(data)
        self.valid = valid_table()
        self.code = set()                      # instruction addresses reached
        self.loads = collections.defaultdict(set)    # loaded address -> (loader PC, size)
        self.branches = collections.defaultdict(set)  # target -> branch PCs
        self.lit_ptrs = collections.defaultdict(set)  # pointed address -> literal addresses
        self.tables = collections.defaultdict(set)    # mova's address (a table) -> mova PCs
        self.entries = {}                      # entry -> how it was found
        self.unresolved = []                   # jumps with no known target (jmp, braf, bsrf)
        self.via = {}                          # (branch, target) -> (literal or table entry, its loader, size)
        self.trace(extra)

    def word(self, a):
        return struct.unpack_from('>H', self.data, a - self.base)[0]

    def long(self, a):
        return struct.unpack_from('>I', self.data, a - self.base)[0]

    def inside(self, a, n=2):
        return self.base <= a and a + n <= self.end

    def looks_like_code(self, a):
        """Decodes cleanly up to a return or an unconditional jump."""
        pc, seen = a, 0
        while seen < 400:
            if not self.inside(pc):
                return False
            w = self.word(pc)
            if not self.valid[w]:
                return False
            k = w >> 12
            if w in (0x000B, 0x002B) or k == 0xA or (k == 4 and w & 0xFF == 0x2B) or (k == 0 and w & 0xFF == 0x23):
                return self.inside(pc + 2) and self.valid[self.word(pc + 2)] and seen >= 1
            if (w >> 8) in (0x89, 0x8B, 0x8D, 0x8F) and not self.inside(pc + 4 + s8(w & 0xFF) * 2):
                return False
            if k == 0xB and not self.inside(pc + 4 + s12(w & 0xFFF) * 2):
                return False
            pc += 2
            seen += 1
        return False

    def plausible_entry(self, a):
        """Code that starts like a function, or right after one ends."""
        if not self.looks_like_code(a):
            return False
        if prologue(self.word(a)):
            return True
        if not self.inside(a - 4):
            return False
        w = self.word(a - 4)
        return w in (0x000B, 0x002B) or w >> 12 == 0xA or w & 0xF0FF == 0x402B

    def use_of(self, pc, reg):
        """How the value a literal load puts in reg is first used: 'call'
        (jsr/jmp through it), 'mem' (an address to read or write), or 'other'."""
        a = pc + 2
        while a < pc + 40 and self.inside(a):
            w = self.word(a)
            if w & 0xF0FF in (0x400B, 0x402B) and (w >> 8) & 15 == reg:
                return 'call'
            if reg in addressed(w):
                return 'mem'
            k = w >> 12
            if reg in writes(w) or k in (0xA, 0xB) or w in (0x000B, 0x002B) or (w >> 8) in (0x89, 0x8B, 0x8D, 0x8F):
                return 'other'
            if (w & 0xF00F) == 0x6003 and (w >> 4) & 15 == reg:
                return 'other'
            a += 2
        return 'other'

    def lit_before(self, pc, reg, start):
        """The literal last loaded into reg in this block before pc, and its
        address and loader, if any."""
        a, add = pc - 2, 0
        while a >= start and a >= pc - 40:
            w = self.word(a)
            if w >> 12 == 0xD and (w >> 8) & 15 == reg:
                t = (a & ~3) + 4 + (w & 0xFF) * 4
                return ((self.long(t) + add) & 0xFFFFFFFF, t, a) if self.inside(t, 4) else (None, None, None)
            if w >> 12 == 0x7 and (w >> 8) & 15 == reg:          # add #imm: a literal plus an offset
                add += s8(w & 0xFF)
            elif reg in writes(w):
                return None, None, None
            a -= 2
        return None, None, None

    def pointer_table(self, pc, reg, start):
        """jmp/jsr through a table of code addresses: mov.l =table,rK; (add rI,rK;)
        mov.l @rK,rM; jmp @rM. The table runs while its words point at code."""
        a, regs, found = pc - 2, None, None
        while a >= start and a >= pc - 32:
            w = self.word(a)
            if regs is None:
                if w >> 12 == 0x6 and w & 15 in (2, 6) and (w >> 8) & 15 == reg:
                    regs = {(w >> 4) & 15}
                elif reg in writes(w):
                    return []
            else:
                if w >> 12 == 0x3 and w & 15 == 0xC and (w >> 8) & 15 in regs:
                    regs.add((w >> 4) & 15)
                elif w >> 12 == 0xD and (w >> 8) & 15 in regs:
                    t = (a & ~3) + 4 + (w & 0xFF) * 4
                    found = self.long(t) if self.inside(t, 4) else None
                    break
            a -= 2
        if found is None or not self.inside(found, 4) or found & 3:
            return []
        out = []
        for e in range(found, min(found + 256, self.end - 3), 4):
            v = self.long(e)
            if not self.inside(v) or v & 1 or not self.looks_like_code(v):
                break
            self.loads[e].add((pc, 4))
            self.via[(pc, v)] = (e, None, 4)
            out.append(v)
        return out

    def switch_targets(self, pc, start):
        """braf's or bsrf's targets through a mova table: mova tbl,r0;
        mov.w @(r0,rI),rX; braf rX. With no bound check before it (an index
        masked instead), the table runs while its entries lead to code, up to
        the first target past it."""
        tbl, count = None, None
        a = pc - 2
        while a >= start and a >= pc - 24:
            w = self.word(a)
            if w >> 8 == 0xC7:
                tbl = (a & ~3) + 4 + (w & 0xFF) * 4
                break
            a -= 2
        if tbl is None:
            return None
        b = a - 2                  # the bound: mov #n,rK; cmp/hs rK,rI (or cmp/hi n-1)
        while b >= start and b >= a - 24:
            w = self.word(b)
            if w >> 12 == 0x3 and w & 15 in (2, 6):
                k = (w >> 4) & 15
                c = b - 2
                while c >= start and c >= b - 12:
                    v = self.word(c)
                    if v >> 12 == 0xE and (v >> 8) & 15 == k:
                        count = (v & 0xFF) + (1 if w & 15 == 6 else 0)
                        break
                    c -= 2
                break
            b -= 2
        out, limit = [], count if count else 64
        for i in range(limit):
            e = tbl + 2 * i
            after = [t for t in out if t > tbl]
            if not self.inside(e) or (count is None and after and e >= min(after)):
                break
            v = self.word(e)
            t = pc + 4 + (v - 0x10000 if v & 0x8000 else v)
            if not self.inside(t) or t & 1 or not self.valid[self.word(t)]:
                break
            if count is None and out and abs(t - out[0]) > 0x1000:     # the entries of one switch stay close
                break
            out.append(t)
        for i, t in enumerate(out):
            self.loads[tbl + 2 * i].add((pc, 2))
            self.via[(pc, t)] = (tbl + 2 * i, None, 2)
        return out

    def trace(self, extra):
        pending = collections.deque()

        def push(t, how, func=False):
            if not self.inside(t) or t & 1:
                return
            if func and t not in self.entries:
                self.entries[t] = how
            pending.append(t)

        self.entries[self.base] = 'entry'
        pending.append(self.base)
        for v in sorted(extra):
            if self.inside(v) and not v & 1 and self.plausible_entry(v):
                push(v, 'outside', True)
        candidates = set()
        while True:
            while pending:
                start = pending.popleft()
                self.walk(start, push, candidates)
            # pointers to code: literals live code loads, then aligned words anywhere
            more = False
            for v, use in sorted(candidates):
                if v in self.code or v in self.entries or use == 'mem':
                    continue
                if self.looks_like_code(v):
                    push(v, 'literal', True)
                    more = True
            candidates.clear()
            if not more:
                for a in range(self.base + (-self.base % 4), self.end - 3, 4):
                    if a in self.code or (a + 2) in self.code:
                        continue
                    v = self.long(a)
                    if self.inside(v) and not v & 1 and v not in self.code and v not in self.entries \
                            and a not in self.loads and self.looks_like_code(v):
                        push(v, 'word', True)
                        more = True
            if not more:
                break

    def walk(self, start, push, candidates):
        pc, block = start, start

        def one(pc):
            """Note one instruction's references; False if it can't be code."""
            if not self.inside(pc):
                return False
            w = self.word(pc)
            if not self.valid[w]:
                return False
            self.code.add(pc)
            k = w >> 12
            if k == 0x9:
                self.loads[pc + 4 + (w & 0xFF) * 2].add((pc, 2))
            elif k == 0xD:
                t = (pc & ~3) + 4 + (w & 0xFF) * 4
                self.loads[t].add((pc, 4))
                if self.inside(t, 4):
                    v = self.long(t)
                    self.lit_ptrs[v].add(t)
                    if self.inside(v) and not v & 1:
                        candidates.add((v, self.use_of(pc, (w >> 8) & 15)))
            elif w >> 8 == 0xC7:
                t = (pc & ~3) + 4 + (w & 0xFF) * 4
                self.loads[t].add((pc, 4))
                self.tables[t].add(pc)
            return True

        while True:
            if pc in self.code or not one(pc):
                return
            w = self.word(pc)
            k, op = w >> 12, w & 0xFF
            if k == 0xA:                                   # bra
                t = pc + 4 + s12(w & 0xFFF) * 2
                self.branches[t].add(pc)
                push(t, 'bra')
                one(pc + 2)
                return
            if k == 0xB:                                   # bsr
                t = pc + 4 + s12(w & 0xFFF) * 2
                self.branches[t].add(pc)
                push(t, 'bsr', True)
                one(pc + 2)
                pc = block = pc + 4
                continue
            if w >> 8 in (0x89, 0x8B):                     # bt, bf
                t = pc + 4 + s8(op) * 2
                self.branches[t].add(pc)
                push(t, 'bt')
                pc = block = pc + 2
                continue
            if w >> 8 in (0x8D, 0x8F):                     # bt/s, bf/s
                t = pc + 4 + s8(op) * 2
                self.branches[t].add(pc)
                push(t, 'bt/s')
                one(pc + 2)
                pc = block = pc + 4
                continue
            if k == 0x4 and op in (0x0B, 0x2B):            # jsr, jmp @Rm
                v, lit, loader = self.lit_before(pc, (w >> 8) & 15, block)
                if v is not None and self.inside(v):
                    self.branches[v].add(pc)
                    self.via[(pc, v)] = (lit, loader, 4)
                    push(v, 'jsr' if op == 0x0B else 'jmp', True)
                elif v is None:
                    ts = self.pointer_table(pc, (w >> 8) & 15, block)
                    for t in ts:
                        self.branches[t].add(pc)
                        push(t, 'table', True)
                    if not ts and op == 0x2B:
                        self.unresolved.append(pc)
                one(pc + 2)
                if op == 0x2B:
                    return
                pc = block = pc + 4
                continue
            if k == 0x0 and op == 0x23:                    # braf
                ts = self.switch_targets(pc, block)
                for t in ts or ():
                    self.branches[t].add(pc)
                    push(t, 'switch')
                if not ts:
                    self.unresolved.append(pc)
                one(pc + 2)
                return
            if k == 0x0 and op == 0x03:                    # bsrf
                ts = self.switch_targets(pc, block)
                for t in ts or ():
                    self.branches[t].add(pc)
                    push(t, 'switch', True)
                if not ts:
                    self.unresolved.append(pc)
                one(pc + 2)
                pc = block = pc + 4
                continue
            if w in (0x000B, 0x002B):                      # rts, rte
                one(pc + 2)
                return
            pc += 2

    def aligned_ptrs(self, lo, hi):
        """Aligned words outside [lo, hi] whose value points into it."""
        out = []
        for a in range(self.base + (-self.base % 4), self.end - 3, 4):
            if not lo <= a <= hi and lo <= self.long(a) <= hi:
                out.append((a, self.long(a)))
        return out


class Traced:
    """A program traced as it ships and in its run-time variants: the union."""

    def __init__(self, datas, base, extra):
        self.progs = [Program(d, base, extra) for d in datas]
        self.code = set().union(*(p.code for p in self.progs))
        self.loads, self.branches, self.lit_ptrs, self.tables = (collections.defaultdict(set) for _ in range(4))
        for p in self.progs:
            for mine, theirs in ((self.loads, p.loads), (self.branches, p.branches), (self.lit_ptrs, p.lit_ptrs),
                                 (self.tables, p.tables)):
                for k, v in theirs.items():
                    mine[k] |= v
        self.unresolved = sorted(set().union(*(p.unresolved for p in self.progs)))
        self.via = {}
        for p in self.progs:
            self.via.update(p.via)


def read_caves():
    """#!cave lines from every patch: (disc path, first, last, patch)."""
    caves = []
    for g in PATCH_GLOBS:
        for p in sorted(glob.glob(g)):
            for line in open(p):
                if line.startswith('#!cave'):
                    f = line.split()
                    caves.append((f[1], int(f[2], 16), int(f[3], 16), os.path.basename(p)))
    return caves


def patch_lines(path):
    """(first, last, patch) of every patch line that writes path."""
    out = []
    for g in PATCH_GLOBS:
        for p in sorted(glob.glob(g)):
            for line in open(p):
                f = line.split('#', 1)[0].split()
                if len(f) >= 5 and f[0] == path:
                    s = int(f[1], 16)
                    out.append((s, s + len(f[4]) // 2 - 1, os.path.basename(p)))
    return out


def changes(path, old, new, base):
    """The changed bytes as units: each patch line that changes anything, then
    the runs no patch line covers (the tools' writes), joined across gaps of
    up to 3 unchanged bytes. A unit is one intended change."""
    units, covered = [], bytearray(len(old))
    for s, e, p in patch_lines(path):
        lo, hi = s - base, e - base + 1
        diff = [i for i in range(lo, hi) if old[i] != new[i]]
        if diff:
            units.append((base + diff[0], base + diff[-1], p))
        covered[lo:hi] = b'\1' * (hi - lo)
    i, n = 0, min(len(old), len(new))
    while i < n:
        if old[i] != new[i] and not covered[i]:
            j, gap, last = i, 0, i
            while j < n and gap <= 3:
                if old[j] != new[j] and not covered[j]:
                    gap, last = 0, j
                else:
                    gap += 1
                j += 1
            units.append((base + i, base + last, 'a tool'))
            i = last + 1
        else:
            i += 1
    return sorted(units)


def shipped_files(built):
    listing = os.path.join(built, 'PATCHED.txt')
    return set(open(listing).read().split()) if os.path.exists(listing) else set()


def runtime_variants(path, old, new):
    """The program as the game may have it in memory besides as shipped."""
    if path != 'DAYTONA/RACE.BIN':
        return []
    from title_convert import CCE_SWITCH, RACE_AT
    v = bytearray(new)
    for a, n in CCE_SWITCH:
        v[a - RACE_AT:a - RACE_AT + n] = old[a - RACE_AT:a - RACE_AT + n]
    return [bytes(v)]


def words(data):
    return struct.unpack(f'>{len(data) // 4}I', data[:len(data) // 4 * 4])


def outside_names(extracted, built):
    """Addresses in each program that other code names, as aligned words, for
    CCE's programs and for ours: for DAYTONA/0, every other program on the
    disc (the overlays call it); for an overlay, DAYTONA/0, and in ours also
    the code we add elsewhere (new files, the bytes grown onto CCE's, the
    bytes we changed in files that aren't programs)."""
    shipped = shipped_files(built)
    kernel_lo = SH2[KERNEL]
    kernel_hi = kernel_lo + os.path.getsize(os.path.join(extracted, KERNEL))
    over_lo, over_hi = 0x06028000, 0x06060000
    ours = []
    for name in sorted(shipped):
        b = os.path.join(built, name)
        o = os.path.join(extracted, name)
        if name in SH2 or not os.path.exists(b):
            continue
        new = open(b, 'rb').read()
        old = open(o, 'rb').read() if os.path.exists(o) else b''
        if new[:len(old)] != old:
            ours.append(bytes(x if x != y else 0 for x, y in zip(new, old)))
        ours.append(new[len(old) & ~3:])
    others = [open(f, 'rb').read() for f in glob.glob(os.path.join(extracted, 'DAYTONA', '*.BIN'))]
    shipped_progs = [open(os.path.join(built if p in shipped else extracted, p), 'rb').read()
                     for p in SH2 if p != KERNEL]

    def names(sources, lo, hi):
        return {v for data in sources for v in words(data) if lo <= v < hi}

    cce_kernel = open(os.path.join(extracted, KERNEL), 'rb').read()
    our_kernel = open(os.path.join(built if KERNEL in shipped else extracted, KERNEL), 'rb').read()
    cce = {KERNEL: names(others, kernel_lo, kernel_hi)}
    mine = {KERNEL: names(ours + shipped_progs + others, kernel_lo, kernel_hi)}
    to_cce_overlay = names([cce_kernel], over_lo, over_hi)
    to_our_overlay = names(ours + [our_kernel], over_lo, over_hi)
    for p in SH2:
        if p != KERNEL:
            cce[p], mine[p] = to_cce_overlay, to_our_overlay
    return cce, mine


def table_extents(t, cce, old, base):
    """How far each table live code takes the address of (mova) may run: to the
    next instruction either program runs, or the next word that starts a
    function (mov.l rN,@-r15 or sts.l pr,@-r15)."""
    out = {}
    for a in t.tables:
        e = a + 2
        while e < base + len(old) - 1 and e - a < 0x400 and e not in t.code and e not in cce.code:
            w = struct.unpack_from('>H', old, e - base)[0]
            if w & 0xFF0F == 0x2F06 or w == 0x4F22:
                break
            e += 2
        out[a] = e - a
    return out


def check(extracted, built):
    caves = read_caves()
    shipped = shipped_files(built)
    cce_names, names = outside_names(extracted, built)
    problems, notes = [], []
    for path, base in SH2.items():
        if path not in shipped:
            continue
        old = open(os.path.join(extracted, path), 'rb').read()
        new = open(os.path.join(built, path), 'rb').read()
        t = Traced([new] + runtime_variants(path, old, new), base, names[path])
        cce = Traced([old], base, cce_names[path])
        extent = table_extents(t, cce, old, base)
        mine = [(s, e, p) for f, s, e, p in caves if f == path]
        same = lambda a, n=2: old[a - base:a - base + n] == new[a - base:a - base + n]
        in_cave = lambda a: any(s <= a <= e for s, e, _ in mine)
        live = lambda pc: pc in t.code and not in_cave(pc) and same(pc)
        hexes = lambda pcs: ', '.join(f'{pc:08X}' for pc in sorted(pcs))

        def cce_branch(pc, target):
            """A live branch of CCE's we left as it was, through a literal or
            table entry we left too."""
            if not live(pc):
                return False
            lit, loader, size = t.via.get((pc, target), (None, None, 0))
            return lit is None or (same(lit, size) and (loader is None or same(loader)))

        def runs_into(a):
            """CCE's live code we left as it was carries on into a: it falls
            through, or a is the delay slot of its branch."""
            prev = a - 2
            if prev not in t.code or in_cave(prev) or not same(prev):
                return False
            w = struct.unpack_from('>H', new, prev - base)[0]
            if delayed(w):
                return True
            if prev - 2 in t.code and unconditional(struct.unpack_from('>H', new, prev - 2 - base)[0]):
                return False
            return True

        cce_used = bytearray(len(old))      # what CCE's own program runs or reads
        for a in cce.code:
            cce_used[a - base] = cce_used[a - base + 1] = 1
        for a, ls in cce.loads.items():
            for pc, size in ls:
                for b in range(a, a + max(size, extent.get(a, 0))):
                    if pc in cce.code and 0 <= b - base < len(old):
                        cce_used[b - base] = 1

        def reads(lo, hi):
            """(loader, address, size) of live unchanged loads that overlap [lo, hi]."""
            out = []
            for a in range(lo - 0x400, hi + 1):
                for pc, size in t.loads.get(a, ()):
                    size = max(size, extent.get(a, 0))
                    if live(pc) and a + size - 1 >= lo and a <= hi:
                        out.append((pc, a, size))
            return sorted(set(out))

        # 1. caves: nothing live reaches in
        for s, e, p in mine:
            where = f"{p}'s cave {s:08X}-{e:08X}"
            for pc, a, size in reads(s, e):
                first = max(a, s)
                table = f' (a table to {a + size - 1:08X})' if size > 4 else ''
                problems.append(f'{path} {pc:08X} loads {a:08X}{table} in {where} '
                                f'(CCE has {old[first - base:first - base + 4].hex()} at {first:08X})')
            for a in range(s, e + 1):
                for pc in t.branches.get(a, ()):
                    if cce_branch(pc, a):
                        problems.append(f'{path} {pc:08X} branches to {a:08X} in {where}')
                for lit in t.lit_ptrs.get(a, ()):
                    users = [pc for pc, _ in t.loads[lit] if live(pc)]
                    if not in_cave(lit) and same(lit, 4) and users:
                        problems.append(f'{path} literal {lit:08X} = {a:08X} points into {where} '
                                        f'(loaded by {hexes(users)})')
                if a in cce_names[path]:
                    problems.append(f'{path} {a:08X} in {where} is named by another of the game\'s programs')
            if runs_into(s):
                problems.append(f'{path} {s - 2:08X} runs on into {where}')
            for a, v in t.progs[0].aligned_ptrs(s, e):
                if in_cave(a) or not same(a, 4) or a in t.lit_ptrs.get(v, ()) or a in t.code or a + 2 in t.code:
                    continue
                problems.append(f'{path} word {a:08X} = {v:08X} points into {where} (a table of pointers?)')

        for s, e, who in changes(path, old, new, base):
            if in_cave(s) and in_cave(e):
                continue
            if in_cave(s) or in_cave(e):
                problems.append(f'{path} {s:08X}-{e:08X} ({who}) runs over the edge of a cave')
                continue
            # 2. literals live code loads, overwritten with more than literals
            hits = reads(s, e)
            covered = set()
            for pc, a, size in hits:
                covered.update(range(a, a + size))
            pure = all(a in covered for a in range(s, e + 1) if old[a - base] != new[a - base])
            for pc, a, size in hits:
                lo, hi = max(a, s), min(a + size - 1, e)
                was, now = old[lo - base:hi + 1 - base].hex(), new[lo - base:hi + 1 - base].hex()
                if was != now:
                    line = f'{path} {pc:08X} loads {lo:08X}: CCE {was}, ours {now} ({who}, {s:08X}-{e:08X})'
                    (notes if pure else problems).append(line)
            # 3. our code in what CCE never runs or reads is a cave, which says so
            if any(a in t.code and not same(a) for a in range(s & ~1, e + 1, 2))                     and not any(cce_used[a - base] for a in range(s, e + 1)):
                problems.append(f'{path} {s:08X}-{e:08X} ({who}) puts code where CCE has dead code: declare the '
                                f'cave (.cave first last) so this check covers it')
    return problems, notes


def free(extracted, built, only=None, minimum=16, dumps=()):
    caves = read_caves()
    seen = []                            # Mednafen CDL dumps (cdl_dump): lo, hi, flags a byte
    for d in dumps:
        raw = open(d, 'rb').read()
        lo, hi = struct.unpack('<II', raw[:8])
        seen.append((lo, hi, raw[8:]))
    shipped = shipped_files(built)
    cce_names, names = outside_names(extracted, built)
    for path, base in SH2.items():
        if only and path != only:
            continue
        old = open(os.path.join(extracted, path), 'rb').read()
        new = open(os.path.join(built, path), 'rb').read() if path in shipped else old
        cce = Traced([old], base, cce_names[path])
        ours = Traced([new] + runtime_variants(path, old, new), base, names[path])
        used = bytearray(len(old))       # 1 live in ours or written by us, 2 live in CCE only
        for t, mark in ((cce, 2), (ours, 1)):
            for a in t.code:
                used[a - base] = used[a - base + 1] = mark
            for a, ls in t.loads.items():
                for pc, size in ls:
                    if pc in t.code:
                        for b in range(a, a + size):
                            if base <= b < base + len(old):
                                used[b - base] = mark
        for i in range(len(old)):
            if old[i] != new[i]:
                used[i] = 1
        for lo, hi, flags in seen:
            for i in range(len(old)):
                a = (base + i) & 0x0FFFFFFF
                if lo <= a < hi and flags[a - lo] & 3:
                    used[i] = 1
        pointed = set(cce.lit_ptrs) | set(ours.lit_ptrs) | set(cce.branches) | set(ours.branches)
        pointed |= names[path] | cce_names[path]
        for data in (old, new):
            pointed.update(words(data))
        claimed = [(s, e, p) for f, s, e, p in caves if f == path]
        print(f'== {path}: {len(ours.code) * 2} bytes of live code, '
              f'{len(ours.unresolved)} indirect jumps with no known target')
        i = 0
        while i < len(old):
            if used[i] == 1:
                i += 1
                continue
            j, bypassed = i, False
            while j < len(old) and used[j] != 1:
                bypassed |= used[j] == 2
                j += 1
            s, e = base + i, base + j - 1
            zero = all(b == 0 for b in old[i:j])
            starts = zero or prologue(struct.unpack_from('>H', old, i)[0])
            if j - i >= minimum and starts and not any(s <= v <= e for v in pointed):
                tags = ['zeros'] if zero else []
                if bypassed:
                    tags.append('CCE runs or loads part of it; dead only while our patches bypass it')
                cave = [p for cs, ce, p in claimed if cs <= s and e <= ce]
                if cave:
                    tags.append(f'in {cave[0]}\'s cave')
                after = max((u for u in ours.unresolved if u < s and s - u < 0x400), default=None)
                if after:
                    tags.append(f'an unresolved jump at {after:08X} before it: check it isn\'t a switch case')
                print(f'  {s:08X}-{e:08X} {j - i:5d} bytes{"; " if tags else ""}{"; ".join(tags)}')
            i = j


def refs(extracted, built, path, lo, hi):
    base = SH2[path]
    shipped = shipped_files(built)
    cce_names, names = outside_names(extracted, built)
    old = open(os.path.join(extracted, path), 'rb').read()
    new = open(os.path.join(built, path), 'rb').read() if path in shipped else old
    for title, t, named in (('ours', Traced([new] + runtime_variants(path, old, new), base, names[path]), names),
                            ('CCE\'s', Traced([old], base, cce_names[path]), cce_names)):
        print(f'-- in {title} program')
        for a in range(lo, hi + 1):
            for pc, size in sorted(t.loads.get(a, ())):
                print(f'{pc:08X} loads {a:08X} ({size} bytes){"" if pc in t.code else " (not live)"}')
            for pc in sorted(t.branches.get(a, ())):
                print(f'{pc:08X} branches to {a:08X}')
            for lit in sorted(t.lit_ptrs.get(a, ())):
                print(f'literal {lit:08X} = {a:08X}, loaded by '
                      f'{", ".join(f"{p:08X}" for p, _ in sorted(t.loads[lit]))}')
            if a in named[path]:
                print(f'{a:08X} is named outside the program')
        for a, v in t.progs[0].aligned_ptrs(lo, hi):
            print(f'word {a:08X} = {v:08X}{" (live code)" if a in t.code else ""}')
        live = [a for a in range(lo, hi + 1, 2) if a in t.code]
        if live:
            print(f'{len(live)} instructions in the range are live code, first {live[0]:08X}')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'check':
        problems, notes = check(sys.argv[2], sys.argv[3])
        if problems:
            print('cave_check: live CCE code reaches bytes we changed:')
            for p in problems:
                print('  ' + p)
            sys.exit(1)
        print(f'cave_check: no live code reaches our caves; {len(notes)} literals changed on purpose')
    elif cmd == 'free':
        free(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None,
             int(sys.argv[5]) if len(sys.argv) > 5 else 16, sys.argv[6:])
    elif cmd == 'refs':
        refs(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5], 16),
             int(sys.argv[6] if len(sys.argv) > 6 else sys.argv[5], 16))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
