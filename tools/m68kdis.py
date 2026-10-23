"""68000 disassembler for the sound CPU's code (sound RAM images).

usage: m68kdis.py <binary> <load_base> <start> [end]
  Addresses are hex. Without end, stops at the first rts/rte/jmp/bra.
"""
import sys

import capstone

MD = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000 | capstone.CS_MODE_BIG_ENDIAN)


def disasm(data, base, start, end=None):
    out = []
    pc = start
    while end is None or pc < end:
        off = pc - base
        if off < 0 or off + 2 > len(data):
            break
        ins = next(MD.disasm(data[off:off + 10], pc), None)
        if ins is None:
            out.append(f'{pc:06x}: {data[off:off + 2].hex():20s} dc.w     0x{data[off:off + 2].hex()}')
            pc += 2
            continue
        out.append(f'{pc:06x}: {ins.bytes.hex():20s} {ins.mnemonic:8s} {ins.op_str}')
        pc += ins.size
        if end is None and ins.mnemonic in ('rts', 'rte', 'jmp', 'bra', 'bra.s', 'bra.w'):
            break
    return out


def main():
    path, base, start = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
    end = int(sys.argv[4], 16) if len(sys.argv) > 4 else None
    data = open(path, 'rb').read()
    print('\n'.join(disasm(data, base, start, end)))


if __name__ == '__main__':
    main()
