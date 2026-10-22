"""Minimal SH-2 assembler for code-cave patches.

Covers the instructions the patches use. Source syntax: one instruction or
directive per line, `;` comments, `label:` on its own line, `.org <hex>`
starting each section, `.align 4`, `.long <value|label>`, `.word <value>`.
Labels are shared across sections, so a call site can name a cave routine.
Branch and PC-relative displacements are computed from labels and checked.

usage: sh2asm.py <src.s> <orig.bin> <base> <disc path>
  Prints one patch line per section (old bytes read from orig.bin).
"""
import re
import sys

R = {f'r{i}': i for i in range(16)}

# mnemonic -> (operand pattern, encoder)
FIXED = {'rts': 0x000B, 'nop': 0x0009}
RN = {  # one register operand: base opcode with n in bits 8-11
    'shar': 0x4021, 'shll': 0x4000, 'shll2': 0x4008, 'shll8': 0x4018, 'shll16': 0x4028,
    'shlr8': 0x4019, 'shlr16': 0x4029, 'cmp/pz': 0x4011, 'cmp/pl': 0x4015,
    'movt': 0x0029, 'jsr': 0x400B, 'jmp': 0x402B,
}
RMRN = {  # rm,rn: base | n<<8 | m<<4
    'mov': 0x6003, 'add': 0x300C, 'sub': 0x3008, 'neg': 0x600B, 'tst': 0x2008,
    'cmp/hi': 0x3006, 'cmp/gt': 0x3007, 'cmp/ge': 0x3003, 'cmp/eq': 0x3000,
    'muls.w': 0x200F, 'swap.w': 0x6009, 'exts.w': 0x600F, 'and': 0x2009, 'or': 0x200B,
    'dmuls.l': 0x300D, 'xtrct': 0x200D, 'extu.w': 0x600D,
}


def num(s):
    s = s.strip().lstrip('#')
    return int(s, 0)


def assemble(lines):
    # pass 1: addresses
    items, labels, pc, orgs = [], {}, None, []
    for raw in lines:
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if line.endswith(':'):
            labels[line[:-1]] = pc
            continue
        op, _, args = line.partition(' ')
        args = [a.strip() for a in re.split(r',(?![^(]*\))', args)] if args.strip() else []
        if op == '.org':
            pc = int(args[0], 16)
            orgs.append(pc)
            continue
        if op == '.align':
            while pc % int(args[0]):
                items.append((pc, '.word', ['0x0009']))
                pc += 2
            continue
        items.append((pc, op, args))
        pc += 4 if op == '.long' else 2
    sections = {org: bytearray() for org in orgs}
    org = None
    for pc, op, args in items:
        org = max(o for o in orgs if o <= pc)
        sections[org] += encode(pc, op, args, labels)
    return [(o, bytes(b)) for o, b in sections.items()]


def disp(target, base, scale, bits, what):
    d, r = divmod(target - base, scale)
    lim = 1 << (bits - 1)
    if r or not -lim <= d < lim:
        raise ValueError(f'{what}: target 0x{target:08X} out of range')
    return d & ((1 << bits) - 1)


def encode(pc, op, a, labels):
    lab = lambda s: labels[s] if s in labels else num(s)
    if op == '.long':
        return lab(a[0]).to_bytes(4, 'big')
    if op == '.word':
        return (num(a[0]) & 0xFFFF).to_bytes(2, 'big')
    if op in FIXED:
        w = FIXED[op]
    elif op in RN:
        w = RN[op] | R[a[0].lstrip('@')] << 8
    elif op in ('bt', 'bf'):
        w = (0x8900 if op == 'bt' else 0x8B00) | disp(lab(a[0]), pc + 4, 2, 8, op)
    elif op in ('bra', 'bsr'):
        w = (0xA000 if op == 'bra' else 0xB000) | disp(lab(a[0]), pc + 4, 2, 12, op)
    elif op == 'sts.l' and a == ['pr', '@-r15']:
        w = 0x4F22
    elif op == 'lds.l' and a == ['@r15+', 'pr']:
        w = 0x4F26
    elif op == 'sts' and a[0] in ('macl', 'mach'):
        w = (0x001A if a[0] == 'macl' else 0x000A) | R[a[1]] << 8
    elif op == 'mov.b' and a[0].startswith('@(r0,'):
        w = 0x000C | R[a[1]] << 8 | R[a[0][5:-1]] << 4
    elif op == 'mov.l' and a[0].startswith('@(r0,'):
        w = 0x000E | R[a[1]] << 8 | R[a[0][5:-1]] << 4
    elif op == 'mov.l' and a[1].startswith('@(r0,'):
        w = 0x0006 | R[a[1][5:-1]] << 8 | R[a[0]] << 4
    elif op == 'mov' and a[0].startswith('#'):
        w = 0xE000 | R[a[1]] << 8 | (num(a[0]) & 0xFF)
        assert -128 <= num(a[0]) < 128
    elif op == 'add' and a[0].startswith('#'):
        w = 0x7000 | R[a[1]] << 8 | (num(a[0]) & 0xFF)
        assert -128 <= num(a[0]) < 128
    elif op in ('mov.l', 'mov.w') and a[0] in labels:  # PC-relative literal load
        base, scale = ((pc & ~3) + 4, 4) if op == 'mov.l' else (pc + 4, 2)
        d, r = divmod(labels[a[0]] - base, scale)
        if r or not 0 <= d < 256:
            raise ValueError(f'0x{pc:08X}: {op} literal {a[0]} out of range')
        w = (0xD000 if op == 'mov.l' else 0x9000) | R[a[1]] << 8 | d
    elif op == 'mov.l' and (m := re.fullmatch(r'@\((\d+),(r\d+)\)', a[1])):  # store
        d = int(m.group(1))
        assert d % 4 == 0 and d < 64
        w = 0x1000 | R[m.group(2)] << 8 | R[a[0]] << 4 | d // 4
    elif op == 'mov.l' and (m := re.fullmatch(r'@\((\d+),(r\d+)\)', a[0])):  # load
        d = int(m.group(1))
        assert d % 4 == 0 and d < 64
        w = 0x5000 | R[a[1]] << 8 | R[m.group(2)] << 4 | d // 4
    elif op in ('mov.w', 'mov.l') and a[1].startswith('@') and a[1][1:] in R:  # store @rn
        w = (0x2001 if op == 'mov.w' else 0x2002) | R[a[1][1:]] << 8 | R[a[0]] << 4
    elif op in ('mov.w', 'mov.l') and a[0].startswith('@') and a[0][1:] in R:
        w = (0x6001 if op == 'mov.w' else 0x6002) | R[a[1]] << 8 | R[a[0][1:]] << 4
    elif op in RMRN:
        w = RMRN[op] | R[a[1]] << 8 | R[a[0]] << 4
    else:
        raise ValueError(f'0x{pc:08X}: unsupported {op} {a}')
    return w.to_bytes(2, 'big')


def main():
    src, orig, base, path = sys.argv[1], sys.argv[2], int(sys.argv[3], 16), sys.argv[4]
    data = open(orig, 'rb').read()
    for org, code in assemble(open(src)):
        old = data[org - base:org - base + len(code)]
        print(f'{path} {org:08X} {base:08X} {old.hex()} {code.hex()}')


if __name__ == '__main__':
    main()
