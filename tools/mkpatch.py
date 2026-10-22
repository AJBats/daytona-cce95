"""Write patches/<name>.patch from patches/<name>.s.

The .s file's leading comment block becomes the patch header; each .org
section becomes one patch line (old bytes from the original RACE.BIN).

usage: mkpatch.py <name> [...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import sh2asm  # noqa: E402

ORIG = 'extracted/cce/DAYTONA/RACE.BIN'
BASE = 0x06028000
DISC_PATH = 'DAYTONA/RACE.BIN'


def main():
    data = open(ORIG, 'rb').read()
    for name in sys.argv[1:]:
        src = f'patches/{name}.s'
        lines = open(src).read().splitlines()
        header = []
        for line in lines:
            if not line.startswith(';'):
                break
            header.append('#' + line[1:])
        out = header[:]
        for org, code in sh2asm.assemble(lines):
            old = data[org - BASE:org - BASE + len(code)]
            out.append(f'{DISC_PATH} {org:08X} {BASE:08X} {old.hex()} {code.hex()}')
        open(f'patches/{name}.patch', 'w').write('\n'.join(out) + '\n')
        print(f'patches/{name}.patch: {len(out) - len(header)} lines')


if __name__ == '__main__':
    main()
