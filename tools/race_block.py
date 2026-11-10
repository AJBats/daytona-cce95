"""Race-time routines that don't fit RACE.BIN's caves (src/race_block.s) as a
block of SCREEN.BIN.

usage: race_block.py <cce extracted dir> <out dir>
  Adds the block to <out dir>/DAYTONA/SCREEN.BIN (after tools/vdp1x.py's).

The block holds the two-player window reflection (patches/reflection.s
leaves a trampoline at its old place, 0603CAD4) and the race's song in
Endurance (patches/endurance.s). CCE's block loader (06007D94, from the
race start at 0602927C) copies SCREEN.BIN's blocks in at every race start
but not in the attract, so each routine is reached through a trampoline in
RACE.BIN that checks the block's magic word, and nothing that runs before
the load or in the attract lives here: the render setup runs before it
(06029998), which is why the replay camera's selectors stay in RACE.BIN.

The block sits above vdp1x's block and work areas, in the zeros the main
program's image carries before its own code at 060191A8 (06018630-060191A7
in the file; nothing points there, and races don't write there). From
060191A8 on are the main program's functions that run between races (the
program flow, 0601927A): a block there wrecked the game after a race.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import sh2asm  # noqa: E402

BLOCK_AT = 0x06018800                   # tools/vdp1x.py keeps its block and work areas below
BLOCK_END = 0x060191A8                  # the main program's code from here on, run between races
MAGIC = 0x5232                          # the trampolines check it


def build():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'src', 'race_block.s')).read()
    (org, code), = sh2asm.assemble(src.splitlines())
    assert org == BLOCK_AT and struct.unpack_from('>H', code)[0] == MAGIC, hex(org)
    assert BLOCK_AT + len(code) <= BLOCK_END, f'{len(code)} bytes'
    return code + bytes(-len(code) % 4)


def main():
    out = sys.argv[2]
    code = build()
    path = os.path.join(out, 'DAYTONA', 'SCREEN.BIN')
    screen = open(path, 'rb').read()
    n = struct.unpack_from('>I', screen)[0]
    for i in range(n):
        size, at = struct.unpack_from('>II', screen, 4 + 8 * i)
        assert at + size <= BLOCK_AT or at >= BLOCK_END, f'SCREEN.BIN block at {at:08X} runs into ours'
    new = (struct.pack('>I', n + 1) + screen[4:4 + 8 * n] + struct.pack('>II', len(code), BLOCK_AT)
           + screen[4 + 8 * n:] + code)
    open(path, 'wb').write(new)
    print(f'race block: {len(code)} bytes at {BLOCK_AT:08X}, SCREEN.BIN {len(new)} bytes')


if __name__ == '__main__':
    main()
