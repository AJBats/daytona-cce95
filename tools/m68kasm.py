"""Minimal 68000 assembler for sound-driver patches.

Covers the instructions the patches use. Source syntax as sh2asm.py: one
instruction or directive per line, `;` comments, `label:` on its own line,
`.org <hex>` starting each section, `.word`/`.long <value|label>`.
Operands in Motorola syntax: d0, a1, #$7f, $2(a1), $3a(a2,d1.w), $6f00.w.
Numbers: $hex, 0xhex or decimal. Branch displacements are computed from
labels and checked; `.s` branches are 8-bit, `.w` 16-bit.

usage: m68kasm.py <src.s> <orig.bin> <base> <disc path>
  Prints one patch line per section (old bytes read from orig.bin).
"""
import re
import sys

SIZE = {'b': 0, 'w': 1, 'l': 2}                  # size field for most ops
MOVE_SIZE = {'b': 1, 'w': 3, 'l': 2}             # size field of move
COND = {'ra': 0, 'sr': 1, 'hi': 2, 'ls': 3, 'cc': 4, 'hs': 4, 'cs': 5, 'lo': 5, 'ne': 6, 'eq': 7,
        'vc': 8, 'vs': 9, 'pl': 10, 'mi': 11, 'ge': 12, 'lt': 13, 'gt': 14, 'le': 15}
SCC = {'t': 0, 'f': 1, **{k: v for k, v in COND.items() if k not in ('ra', 'sr')}}


def num(s, labels=None):
    s = s.strip().lstrip('#')
    if labels and s in labels:
        return labels[s]
    neg = s.startswith('-')
    s = s.lstrip('-')
    v = int(s[1:], 16) if s.startswith('$') else int(s, 0)
    return -v if neg else v


def reg(s):
    m = re.fullmatch(r'([da])([0-7])', s)
    return (m.group(1), int(m.group(2))) if m else None


def ea(op, size, labels):
    """Effective address -> (mode, reg, extension bytes)."""
    r = reg(op)
    if r:
        return (0 if r[0] == 'd' else 1), r[1], b''
    if op.startswith('#'):
        v = num(op, labels)
        return 7, 4, (v & 0xFFFFFFFF).to_bytes(4, 'big') if size == 'l' else (v & 0xFFFF).to_bytes(2, 'big')
    if m := re.fullmatch(r'\(a([0-7])\)', op):
        return 2, int(m.group(1)), b''
    if m := re.fullmatch(r'\(a([0-7])\)\+', op):
        return 3, int(m.group(1)), b''
    if m := re.fullmatch(r'-\(a([0-7])\)', op):
        return 4, int(m.group(1)), b''
    if m := re.fullmatch(r'([-$\w]+)\(a([0-7])\)', op):
        d = num(m.group(1))
        assert -0x8000 <= d < 0x8000, op
        return 5, int(m.group(2)), (d & 0xFFFF).to_bytes(2, 'big')
    if m := re.fullmatch(r'([-$\w]*)\(a([0-7]),([da])([0-7])\.([wl])\)', op):
        d = num(m.group(1)) if m.group(1) else 0
        assert -0x80 <= d < 0x80, op
        ext = (m.group(3) == 'a') << 15 | int(m.group(4)) << 12 | (m.group(5) == 'l') << 11 | (d & 0xFF)
        return 6, int(m.group(2)), ext.to_bytes(2, 'big')
    if m := re.fullmatch(r'([-$\w]+)\.w', op):
        return 7, 0, (num(m.group(1)) & 0xFFFF).to_bytes(2, 'big')
    raise ValueError(f'bad operand {op}')


INLINE_IMM = ('moveq', 'addq', 'subq', 'asr', 'asl', 'lsr', 'lsl')


def ext_len(op, size):
    """Extension bytes an operand adds."""
    if reg(op) or re.fullmatch(r'-?\(a[0-7]\)\+?', op):
        return 0
    if op.startswith('#'):
        return 4 if size == 'l' else 2
    return 2  # d16(An), d8(An,Xn), abs.w


def length(op, base, size, args):
    """Instruction length in bytes; needs no labels, so pass 1 can use it."""
    if op in ('.word', 'rts', 'nop'):
        return 2
    if op == '.long':
        return 4
    if base[0] == 'b' and (base[1:] in COND or base == 'bsr'):
        return 2 if size == 's' else 4
    if base in INLINE_IMM:
        args = args[1:]
    return 2 + sum(ext_len(a, size) for a in args)


def split(line):
    op, _, rest = line.partition(' ')
    args = [a.strip() for a in re.split(r',(?![^(]*\))', rest)] if rest.strip() else []
    base, _, size = op.partition('.')
    return op, base, size, args


def assemble(lines):
    items, labels, pc, orgs = [], {}, None, []
    for raw in lines:
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if line.endswith(':'):
            labels[line[:-1]] = pc
            continue
        op, base, size, args = split(line)
        if op == '.org':
            pc = int(args[0], 16)
            orgs.append(pc)
            continue
        items.append((pc, op, base, size, args))
        pc += length(op, base, size, args)
    sections = {org: bytearray() for org in orgs}
    for pc, op, base, size, args in items:
        org = max(o for o in orgs if o <= pc)
        code = encode(pc, op, base, size, args, labels)
        assert len(code) == length(op, base, size, args), (hex(pc), op, args)
        sections[org] += code
    return [(o, bytes(b)) for o, b in sections.items()]


def branch(pc, target, short, what):
    d = target - (pc + 2)
    if short:
        if not (-0x80 <= d < 0x80) or d == 0:
            raise ValueError(f'{what}: 0x{target:X} out of short range')
        return d & 0xFF, b''
    if not -0x8000 <= d < 0x8000:
        raise ValueError(f'{what}: 0x{target:X} out of range')
    return 0, (d & 0xFFFF).to_bytes(2, 'big')


def encode(pc, op, base, size, a, labels):
    w = lambda v: v.to_bytes(2, 'big')
    if op == '.word':
        return (num(a[0], labels) & 0xFFFF).to_bytes(2, 'big')
    if op == '.long':
        return (num(a[0], labels) & 0xFFFFFFFF).to_bytes(4, 'big')
    if op == 'rts':
        return w(0x4E75)
    if op == 'nop':
        return w(0x4E71)
    if base[0] == 'b' and (base[1:] in COND or base == 'bsr'):
        cond = 1 if base == 'bsr' else COND[base[1:]]
        d8, ext = branch(pc, num(a[0], labels), size == 's', op)
        return w(0x6000 | cond << 8 | d8) + ext
    if base == 's' + base[1:] and base[1:] in SCC and len(a) == 1 and reg(a[0]):
        return w(0x50C0 | SCC[base[1:]] << 8 | reg(a[0])[1])
    if base == 'moveq':
        v = num(a[0])
        assert -128 <= v < 128
        return w(0x7000 | reg(a[1])[1] << 9 | (v & 0xFF))
    if base in ('addq', 'subq'):
        v = num(a[0])
        assert 1 <= v <= 8
        m, r, ext = ea(a[1], size, labels)
        return w((0x5000 if base == 'addq' else 0x5100) | (v & 7) << 9 | SIZE[size] << 6 | m << 3 | r) + ext
    if base in ('move', 'movea'):
        sm, sr, sext = ea(a[0], size, labels)
        dm, dr, dext = ea(a[1], size, labels)
        return w(MOVE_SIZE[size] << 12 | dr << 9 | dm << 6 | sm << 3 | sr) + sext + dext
    if base in ('andi', 'ori', 'subi', 'addi', 'cmpi', 'eori'):
        opc = {'ori': 0x0000, 'andi': 0x0200, 'subi': 0x0400, 'addi': 0x0600, 'eori': 0x0A00, 'cmpi': 0x0C00}[base]
        m, r, ext = ea(a[1], size, labels)
        imm = num(a[0])
        immb = (imm & 0xFFFFFFFF).to_bytes(4, 'big') if size == 'l' else (imm & (0xFF if size == 'b' else 0xFFFF)).to_bytes(2, 'big')
        return w(opc | SIZE[size] << 6 | m << 3 | r) + immb + ext
    if base in ('add', 'sub', 'or', 'and', 'cmp') and reg(a[1]) and reg(a[1])[0] == 'd':
        opc = {'or': 0x8000, 'sub': 0x9000, 'cmp': 0xB000, 'and': 0xC000, 'add': 0xD000}[base]
        m, r, ext = ea(a[0], size, labels)
        return w(opc | reg(a[1])[1] << 9 | SIZE[size] << 6 | m << 3 | r) + ext
    if base in ('muls', 'mulu'):
        m, r, ext = ea(a[0], 'w', labels)
        return w((0xC1C0 if base == 'muls' else 0xC0C0) | reg(a[1])[1] << 9 | m << 3 | r) + ext
    if base in ('asr', 'asl', 'lsr', 'lsl') and a[0].startswith('#'):
        cnt = num(a[0])
        assert 1 <= cnt <= 8
        typ = 0 if base[0] == 'a' else 1
        dr = 1 if base[-1] == 'l' else 0
        return w(0xE000 | (cnt & 7) << 9 | dr << 8 | SIZE[size] << 6 | typ << 3 | reg(a[1])[1])
    if base == 'ext':
        return w((0x4880 if size == 'w' else 0x48C0) | reg(a[0])[1])
    if base in ('not', 'neg', 'clr', 'tst'):
        opc = {'not': 0x4600, 'neg': 0x4400, 'clr': 0x4200, 'tst': 0x4A00}[base]
        m, r, ext = ea(a[0], size, labels)
        return w(opc | SIZE[size] << 6 | m << 3 | r) + ext
    raise ValueError(f'0x{pc:X}: unsupported {op} {a}')


def main():
    src, orig, base, path = sys.argv[1], sys.argv[2], int(sys.argv[3], 16), sys.argv[4]
    data = open(orig, 'rb').read()
    for org, code in assemble(open(src)):
        old = data[org - base:org - base + len(code)]
        print(f'{path} {org:08X} {base:08X} {old.hex()} {code.hex()}')


if __name__ == '__main__':
    main()
