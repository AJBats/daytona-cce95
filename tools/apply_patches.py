"""Apply byte patches to extracted CCE files.

Each patch file (patches/*.patch) holds lines of
    <disc path> <load address> <load base> <expected hex> <new hex>  # comment
The expected bytes are checked before writing so a patch can never land on
the wrong data. Patched files are written under <outdir>, mirroring disc paths, and listed in
<outdir>/PATCHED.txt; only listed files go onto the disc, so files left over
from an earlier patch set are ignored rather than deleted.

usage: apply_patches.py <extracted_dir> <outdir> <patch> [...]
"""
import os
import sys


def main():
    src, out = sys.argv[1], sys.argv[2]
    files = {}
    for patch in sys.argv[3:]:
        for n, line in enumerate(open(patch), 1):
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            path, addr, base, old, new = line.split()
            old, new = bytes.fromhex(old), bytes.fromhex(new)
            if len(old) != len(new):
                sys.exit(f'{patch}:{n}: old/new length differ')
            if path not in files:
                files[path] = bytearray(open(os.path.join(src, path), 'rb').read())
            off = int(addr, 16) - int(base, 16)
            have = bytes(files[path][off:off + len(old)])
            if have != old:
                sys.exit(f'{patch}:{n}: expected {old.hex()} at {addr}, found {have.hex()}')
            files[path][off:off + len(new)] = new
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'PATCHED.txt'), 'w') as f:
        f.write(''.join(p + '\n' for p in sorted(files)))
    for path, data in files.items():
        dst = os.path.join(out, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(data)
        print(f'wrote {dst}')


if __name__ == '__main__':
    main()
