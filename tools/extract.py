"""Extract every file from a disc's data track and write a manifest.

usage: extract.py <track01.bin> <outdir>
"""
import os
import sys

from cdimage import Image


def main():
    img = Image(sys.argv[1])
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'MANIFEST.txt'), 'w') as man:
        man.write('# path lba size\n')
        for path, lba, size in img.files():
            dst = os.path.join(out, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as f:
                f.write(img.read(lba, (size + 2047) // 2048)[:size])
            man.write(f'{path} {lba} {size}\n')
    with open(os.path.join(out, 'IP.BIN'), 'wb') as f:
        f.write(img.read(0, 16))


if __name__ == '__main__':
    main()
