"""Write patches/<name>.patch from patches/<name>.s.

The .s file's leading comment block becomes the patch header; each .org
section becomes one patch line (old bytes from the original file). Sources
patch RACE.BIN (SH-2) unless they name another file with
`.target <disc path> <load base> m68k`, as the sound driver patches do.

usage: mkpatch.py <name> [...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import m68kasm  # noqa: E402
import sh2asm  # noqa: E402

EXTRACTED = 'extracted/cce'
DEFAULT = ('DAYTONA/RACE.BIN', 0x06028000, sh2asm)


def main():
    for name in sys.argv[1:]:
        src = f'patches/{name}.s'
        lines = open(src).read().splitlines()
        header = []
        for line in lines:
            if not line.startswith(';'):
                break
            header.append('#' + line[1:])
        disc_path, base, asm = DEFAULT
        targets = [line.split() for line in lines if line.startswith('.target')]
        if targets:
            _, disc_path, base, cpu = targets[0]
            base, asm = int(base, 16), {'m68k': m68kasm, 'sh2': sh2asm}[cpu]
            lines = [line for line in lines if not line.startswith('.target')]
        data = open(os.path.join(EXTRACTED, disc_path), 'rb').read()
        out = header[:]
        for org, code in asm.assemble(lines):
            old = data[org - base:org - base + len(code)]
            out.append(f'{disc_path} {org:08X} {base:08X} {old.hex()} {code.hex()}')
        open(f'patches/{name}.patch', 'w').write('\n'.join(out) + '\n')
        print(f'patches/{name}.patch: {len(out) - len(header)} lines')


if __name__ == '__main__':
    main()
