"""State forcing: run CCE's physics one tick at a time from DUSA's state.

DUSA's recorded car state is converted to CCE's layout and units, poked
into CCE's car before every CCE tick (poke_playback at the car update root),
and CCE's one-tick result is compared with what DUSA did over the same wall
time. Because CCE is reset to DUSA's state every tick, differences can't
compound: each one is the physics code disagreeing on that tick.

Timing: CCE ticks every 2 frames, DUSA every 3. DUSA's state between its
ticks is linearly interpolated (angles unwrapped; counters held).
A CCE frame c corresponds to DUSA frame c + offset.

usage:
  teacher.py prep  <dusa.bin> <offset> <first_cce_tick> <ticks> <out.csv> <columns.json>
  teacher.py score <dusa.bin> <offset> <first_cce_tick> <ticks> <cce_forced.bin> <sample_start_frame>
"""
import json
import struct
import sys

DN, CN = 768, 1024

# name, dusa off, cce off, cce width, kind
#   same: identical units; tick: per-tick quantity (x2/3 at 30 Hz);
#   ticks: tick counter (x3/2); angle: 16-bit angle
# Gear and rpm are left to CCE: its gear numbering differs and rpm is
# recomputed from speed every tick.
# Position (DUSA 0x10/0x18, CCE 0x00/0x08) is left to CCE: writing CCE's
# 0x08 on its own corrupts it and stops the car update (CCE keeps another
# copy of the position), and position only sets which road the car is on.
FIELDS = [
    ('travel', 0x28, 0x38, 32, 'angle'),
    ('heading', 0x30, 0x3C, 32, 'angle'),
    ('speed', 0x0C, 0x24, 32, 'tick'),
    ('kmh', 0x08, 0x34, 32, 'same'),
    ('yaw58', 0x58, 0x64, 32, 'same'),
    ('slip5C', 0x5C, 0x68, 32, 'same'),
    ('rate178', 0x178, 0x104, 32, 'tick'),
    ('slrate154', 0x154, 0x44, 32, 'tick'),
    ('latF', 0x60, 0xE8, 32, 'same'),
    ('latR', 0x64, 0xEC, 32, 'same'),
    ('gripF', 0x140, 0xF4, 32, 'same'),
    ('gripR', 0x144, 0xF8, 32, 'same'),
    ('grip', 0x10C, 0x70, 32, 'same'),
    ('spin', 0x110, 0x100, 32, 'same'),
    ('steer', 0xAC, 0x78, 32, 'same'),
    ('steerB0', 0xB0, 0x7C, 32, 'same'),
    ('whlang', 0xD0, 0xAC, 32, 'same'),
    ('thr', 0x68, 0x80, 32, 'same'),
    ('brk', 0x84, 0x90, 32, 'same'),
]


def dusa_reader(path):
    d = open(path, 'rb').read()

    def get(f, off, width=32):
        if width == 16:
            return struct.unpack_from('>h', d, f * DN + off + 2)[0]
        return struct.unpack_from('>i', d, f * DN + off)[0]
    return get


def dusa_at(get, frame):
    """DUSA state at a (possibly fractional) frame, in DUSA units."""
    # DUSA ticks land on frames == 2 mod 3; the state shown at frame f is the latest tick's
    k0 = int(frame) - ((int(frame) - 2) % 3)
    k1 = k0 + 3
    a = (frame - k0) / 3.0
    out = {}
    for name, doff, _, _, kind in FIELDS:
        v0, v1 = get(k0, doff), get(k1, doff)
        if kind == 'ticks':
            out[name] = v0
        elif kind == 'angle':
            d = ((v1 - v0 + 0x8000) & 0xFFFF) - 0x8000
            out[name] = v0 + round(d * a)
        else:
            out[name] = round(v0 + (v1 - v0) * a)
    return out


def to_cce(s):
    out = {}
    for name, _, _, _, kind in FIELDS:
        v = s[name]
        if kind == 'tick':
            v = round(v * 2 / 3)
        elif kind == 'ticks':
            v = round(v * 3 / 2)
        out[name] = v
    return out


def prep(dusa, offset, c0, ticks, csv_path, cols_path):
    get = dusa_reader(dusa)
    with open(csv_path, 'w') as f:
        f.write(','.join(f'+0x{coff:03X}' for _, _, coff, _, _ in FIELDS) + '\n')
        for i in range(ticks):
            c = c0 + 2 * i
            s = to_cce(dusa_at(get, c - 2 + offset))
            f.write(','.join(f'0x{s[n] & 0xFFFFFFFF:08X}' for n, *_ in FIELDS) + '\n')
    cols = []
    for name, _, coff, width, _ in FIELDS:
        col = {'csv_column': f'+0x{coff:03X}', 'offset': coff, 'width': width}
        if width == 16:
            col['byte_slice'] = [2, 4]
        cols.append(col)
    json.dump(cols, open(cols_path, 'w'))
    print(f'{ticks} rows -> {csv_path}; columns -> {cols_path}')


def score(dusa, offset, c0, ticks, forced, s0):
    get = dusa_reader(dusa)
    cd = open(forced, 'rb').read()
    cget = lambda f, off, w: (struct.unpack_from('>h', cd, (f - s0) * CN + off)[0] if w == 16
                              else struct.unpack_from('>i', cd, (f - s0) * CN + off)[0])
    show = ['heading', 'travel', 'slip5C', 'yaw58', 'rate178', 'latF', 'latR', 'gripR', 'grip', 'spin', 'speed', 'whlang']
    print('Per-tick change over 2 frames: DUSA / CCE (CCE converted to DUSA units). t = s from first tick')
    print(f"{'t':>5s} " + ' '.join(f'{n:>17s}' for n in show))
    for i in range(1, ticks):
        c = c0 + 2 * i
        pre = dusa_at(get, c - 2 + offset)
        post = dusa_at(get, c + offset)
        row = []
        for name in show:
            _, _, coff, w, kind = next(x for x in FIELDS if x[0] == name)
            cpost = cget(c, coff, w)
            if kind == 'tick':
                cpost = cpost * 3 / 2
            dd = post[name] - pre[name]
            dc = cpost - pre[name]
            if kind == 'angle':
                dd = ((dd + 0x8000) & 0xFFFF) - 0x8000
                dc = ((int(dc) + 0x8000) & 0xFFFF) - 0x8000
            row.append(f'{dd:8.0f}/{dc:8.0f}')
        print(f'{(c - c0) / 60:5.2f} ' + ' '.join(row))


def main():
    mode = sys.argv[1]
    dusa, offset, c0, ticks = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    if mode == 'prep':
        prep(dusa, offset, c0, ticks, sys.argv[6], sys.argv[7])
    else:
        score(dusa, offset, c0, ticks, sys.argv[6], int(sys.argv[7]))


if __name__ == '__main__':
    main()
