"""Poke list that puts a running CCE into a given patch level.

Reads patches/*.patch in order and emits JSON for the debugger's
poke_breakpoint_set: patches 1..level get their new bytes, later patches
get their original bytes. Applied to a save state, this turns it into any
build without re-driving.

usage: pokes.py <level> <patch> [patch ...]
"""
import json
import sys


def entries(patch):
    for line in open(patch):
        line = line.split('#', 1)[0].strip()
        if line:
            _, addr, _, old, new = line.split()
            yield int(addr, 16), bytes.fromhex(old), bytes.fromhex(new)


def main():
    level = int(sys.argv[1])
    pokes = []
    for i, patch in enumerate(sys.argv[2:], 1):
        for addr, old, new in entries(patch):
            data = new if i <= level else old
            for off in range(0, len(data), 2):
                word = int.from_bytes(data[off:off + 2], 'big')
                pokes.append({'addr': f'0x{addr + off:08X}', 'value': f'0x{word:04X}', 'width': 16})
    print(json.dumps(pokes))


if __name__ == '__main__':
    main()
