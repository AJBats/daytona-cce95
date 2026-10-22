"""Debugger poke lists that apply patch files to a running CCE.

Packs the new bytes into aligned 32-bit pokes (16-bit at the edges) and
splits them into groups of at most 64, the debugger's limit per trigger.
Each group is installed with poke_breakpoint_set at one of TRIGGERS: PCs
that run every tick before the patched code (input step and wheel step
come before the core step).

usage: hotpatch.py <patch> [patch ...]   prints one JSON list per trigger
"""
import json
import sys

TRIGGERS = ['0x0604D758', '0x06035F48', '0x0604D6B8']


def pokes(paths):
    mem = {}
    for path in paths:
        for line in open(path):
            f = line.split('#', 1)[0].split()
            if f:
                addr, new = int(f[1], 16), bytes.fromhex(f[4])
                for o in range(0, len(new), 2):
                    mem[addr + o] = new[o:o + 2]
    out, done = [], set()
    for a in sorted(mem):
        if a in done:
            continue
        if a % 4 == 0 and a + 2 in mem:
            out.append({'addr': f'0x{a:08X}', 'value': f'0x{(mem[a] + mem[a + 2]).hex().upper()}', 'width': 32})
            done |= {a, a + 2}
        else:
            out.append({'addr': f'0x{a:08X}', 'value': f'0x{mem[a].hex().upper()}', 'width': 16})
            done.add(a)
    return out


def main():
    p = pokes(sys.argv[1:])
    groups = [p[i:i + 64] for i in range(0, len(p), 64)]
    if len(groups) > len(TRIGGERS):
        sys.exit('too many pokes')
    for trig, g in zip(TRIGGERS, groups):
        print(trig, json.dumps(g, separators=(',', ':')))


if __name__ == '__main__':
    main()
