"""Check that fix_sector reproduces the EDC/ECC of real sectors."""
import sys

from cdimage import Image, SECTOR, fix_sector


def main():
    img = Image(sys.argv[1])
    total = len(img.raw) // SECTOR
    for lba in list(range(0, total, max(1, total // 500))) + [16, total - 1]:
        orig = bytes(img.raw[lba * SECTOR:(lba + 1) * SECTOR])
        if orig[15] != 1:
            continue
        if fix_sector(bytearray(orig)) != orig:
            sys.exit(f'FAIL: sector {lba} EDC/ECC mismatch')
    print('PASS: EDC/ECC regenerated identically')


if __name__ == '__main__':
    main()
