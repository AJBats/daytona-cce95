"""Debugger poke lists that apply patch files to a running CCE.

Packs the new bytes into aligned 32-bit pokes (16-bit at the edges) and
splits them into groups of at most 64, the debugger's limit per trigger.
Each group is installed with poke_breakpoint_set at one of TRIGGERS: the
car tick body and its first two steps, which run before any patched code
in the same tick, so a tick never runs half-patched code.

Per-car tables are copied into the car struct at race start, so patches to
them also poke the player car's copy (CAR_TABLES).

usage: hotpatch.py <patch> [patch ...]   prints one JSON list per trigger
"""
import json
import sys

TRIGGERS = ['0x0604D380', '0x06036CEC', '0x0604D580']
CAR = 0x0605224C
# table address -> car struct field holding the player car's (car 0) row
CAR_TABLES = {0x0604D1CC: 0x16C, 0x0604D310: 0x1B2, 0x0604D2A0: 0x14C, 0x0604D2A4: 0x150}


def pokes(paths):
    mem = {}
    for path in paths:
        for line in open(path):
            f = line.split('#', 1)[0].split()
            if f:
                addr, new = int(f[1], 16), bytes.fromhex(f[4])
                for o in range(0, len(new), 2):
                    mem[addr + o] = new[o:o + 2]
                if addr in CAR_TABLES:
                    for o in range(0, len(new), 2):
                        mem[CAR + CAR_TABLES[addr] + o] = new[o:o + 2]
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
