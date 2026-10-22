"""RMS per-tick error vs DUSA for forced CCE runs (see teacher.py).

usage: forced_errors.py <dusa.bin> <offset> <first_tick> <ticks> <label>=<forced.bin> [...]
"""
import math
import struct
import sys

import teacher as T


def main():
    dusa, offset, c0, ticks = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    get = T.dusa_reader(dusa)
    runs = [a.split('=', 1) for a in sys.argv[5:]]
    wrap = lambda x: ((x + 0x8000) & 0xFFFF) - 0x8000
    rms = lambda v: math.sqrt(sum(x * x for x in v) / len(v))
    table = {}
    for label, path in runs:
        X = open(path, 'rb').read()
        cg = lambda f, o: struct.unpack_from('>i', X, (f - c0) * 1024 + o)[0]
        e = {k: [] for k in ('slide rate', 'heading step', 'slip', 'yaw', 'travel', 'lat force (M)', 'grip')}
        for i in range(1, ticks):
            c = c0 + 2 * i
            d = T.dusa_at(get, c + offset)
            e['slide rate'].append(cg(c, 0x104) * 1.5 - d['rate178'])
            e['heading step'].append(cg(c, 0x44) * 1.5 - d['slrate154'])
            e['slip'].append(cg(c, 0x68) - d['slip5C'])
            e['yaw'].append(cg(c, 0x64) - d['yaw58'])
            e['travel'].append(wrap(cg(c, 0x38) - d['travel']))
            e['lat force (M)'].append((cg(c, 0xE8) - d['latF']) / 1e6)
            e['grip'].append(cg(c, 0x70) - d['grip'])
        table[label] = {k: rms(v) for k, v in e.items()}
    print(f"{'RMS error vs DUSA':16s}" + ''.join(f'{l:>14s}' for l, _ in runs))
    for k in table[runs[0][0]]:
        print(f'{k:16s}' + ''.join(f'{table[l][k]:14.1f}' for l, _ in runs))


if __name__ == '__main__':
    main()
