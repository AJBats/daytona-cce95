"""SH-2 disassembler with PC-relative literal resolution.

usage: sh2dis.py <binary> <load_base> <start> [end]
  Addresses are hex. Without end, stops at the first rts (plus delay slot).
"""
import re
import struct
import sys

import capstone

MD = capstone.Cs(capstone.CS_ARCH_SH, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_SH2)


def disasm(data, base, start, end=None):
    out = []
    pc = start
    stop_after = None
    while True:
        if end is not None and pc >= end:
            break
        off = pc - base
        if off < 0 or off + 2 > len(data):
            break
        word = struct.unpack_from('>H', data, off)[0]
        ins = next(MD.disasm(data[off:off + 2], pc), None)
        text = f'{ins.mnemonic:8s} {ins.op_str}' if ins else f'.word    0x{word:04x}'
        note = ''
        if ins and ins.mnemonic in ('mov.l', 'mov.w', 'mova') and '@(' in ins.op_str and 'pc' in ins.op_str:
            pass
        # capstone renders pc-relative loads as an absolute address
        m = re.match(r'(mov\.[lw])\s+0x([0-9a-f]+),', text)
        if m and ins:
            lit = int(m.group(2), 16)
            lo = lit - base
            if 0 <= lo + 4 <= len(data):
                if m.group(1) == 'mov.l':
                    note = f'  ; =0x{struct.unpack_from(">I", data, lo)[0]:08x}'
                else:
                    note = f'  ; =0x{struct.unpack_from(">h", data, lo)[0] & 0xffff:04x}'
        out.append(f'{pc:08x}: {word:04x}  {text}{note}')
        if stop_after is not None and pc >= stop_after:
            break
        if end is None and ins and ins.mnemonic == 'rts':
            stop_after = pc + 2
        pc += 2
    return out


def main():
    path, base, start = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
    end = int(sys.argv[4], 16) if len(sys.argv) > 4 else None
    data = open(path, 'rb').read()
    print('\n'.join(disasm(data, base, start, end)))


if __name__ == '__main__':
    main()
