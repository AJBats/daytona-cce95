"""Decode SCSP slot registers (0x25B00000-0x25B003FF, as a CPU read returns them).

usage: scsp_slots.py <dump> [frame]
  <dump> is a read of 0x400 bytes, or a sample_memory blob of N x 0x400
  bytes; frame picks one sample (default: the last). Lists every slot that
  has a start address or is keyed on.
"""
import struct
import sys

SLOT = 0x20


def decode(regs):
    """regs: 16 big-endian words of one slot."""
    w = regs
    oct_ = (w[8] >> 11) & 0xF
    if oct_ & 8:
        oct_ -= 16
    fns = (w[8] >> 0) & 0x3FF
    return {
        'key': (w[0] >> 11) & 1,
        'sbctl': (w[0] >> 9) & 3,
        'ssctl': (w[0] >> 7) & 3,
        'lpctl': (w[0] >> 5) & 3,
        'pcm8': (w[0] >> 4) & 1,
        'sa': ((w[0] & 0xF) << 16) | w[1],
        'lsa': w[2],
        'lea': w[3],
        'ar': w[4] & 0x1F,
        'd1r': (w[4] >> 6) & 0x1F,
        'd2r': (w[4] >> 11) & 0x1F,
        'rr': w[5] & 0x1F,
        'dl': (w[5] >> 5) & 0x1F,
        'tl': w[6] & 0xFF,
        'sdir': (w[6] >> 8) & 1,
        'oct': oct_,
        'fns': fns,
        'ratio': 2.0 ** oct_ * (1 + fns / 1024),
        'lfo': w[9],
        'disdl': (w[11] >> 13) & 7,
        'dipan': (w[11] >> 8) & 0x1F,
        'efsdl': (w[11] >> 5) & 7,
        'efpan': w[11] & 0x1F,
    }


def slots(blob):
    out = []
    for n in range(32):
        regs = struct.unpack_from('>16H', blob, n * SLOT)
        out.append(decode(regs))
    return out


def fmt(n, s):
    return (f'{n:2d} key={s["key"]} sa={s["sa"]:05X} lsa={s["lsa"]:04X} lea={s["lea"]:04X} '
            f'{"8" if s["pcm8"] else "16"}bit lp={s["lpctl"]} tl={s["tl"]:3d} '
            f'oct={s["oct"]:+d} fns={s["fns"]:4d} ratio={s["ratio"]:.4f} '
            f'ar={s["ar"]} d1r={s["d1r"]} dl={s["dl"]} d2r={s["d2r"]} rr={s["rr"]} '
            f'di={s["disdl"]}/{s["dipan"]:2d} ef={s["efsdl"]}/{s["efpan"]:2d} lfo={s["lfo"]:04X}')


def main():
    data = open(sys.argv[1], 'rb').read()
    frames = len(data) // 0x400
    f = int(sys.argv[2]) if len(sys.argv) > 2 else frames - 1
    for n, s in enumerate(slots(data[f * 0x400:(f + 1) * 0x400])):
        if s['sa'] or s['key']:
            print(fmt(n, s))


if __name__ == '__main__':
    main()
