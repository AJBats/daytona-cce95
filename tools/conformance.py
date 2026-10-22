"""Score CCE runs against a DUSA reference for one scripted manoeuvre.

Only quantities measured the same way in both games are compared, so the
20 Hz / 30 Hz difference in internal units can't leak in:
  heading      car facing angle (16-bit angle, 0x10000 = 360 deg)
  travel       direction of the velocity vector (same units)
  slide        heading - travel, the visible drift angle
  speed        km/h lost since the sync frame (removes entry-speed mismatch)
  path         x/y position relative to the start of the window
Runs are aligned on a sync frame (the first scripted input of the
manoeuvre) and compared over a fixed window after it.

usage: conformance.py <dusa.bin> <dusa_sync> <window> <cce.bin>:<sync>:<label> [...]
"""
import math
import struct
import sys

LAYOUT = {
    'dusa': dict(size=768, heading=0x30, travel=0x28, kmh=0x08, x=0x10, y=0x18),
    'cce': dict(size=1024, heading=0x3C, travel=0x38, kmh=0x34, x=0x00, y=0x08),
}


def angle(a):
    a = (a & 0xFFFF) * 360.0 / 65536.0
    return a - 360.0 if a > 180.0 else a


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def series(path, game, sync, window):
    L = LAYOUT[game]
    data = open(path, 'rb').read()
    g = lambda f, o: struct.unpack_from('>i', data, f * L['size'] + o)[0]
    h0, x0, y0 = angle(g(sync, L['heading'])), g(sync, L['x']) / 65536, g(sync, L['y']) / 65536
    k0 = g(sync, L['kmh'])
    turned = 0.0
    prev = h0
    out = []
    for t in range(window):
        f = sync + t
        h, v = angle(g(f, L['heading'])), angle(g(f, L['travel']))
        turned += wrap(h - prev)
        prev = h
        out.append(dict(
            heading=turned,
            slide=wrap(h - v),
            speed=g(f, L['kmh']) - k0,
            x=g(f, L['x']) / 65536 - x0,
            y=g(f, L['y']) / 65536 - y0,
        ))
    return out


def rms(vals):
    return math.sqrt(sum(v * v for v in vals) / len(vals))


def score(ref, run):
    return dict(
        heading=rms([a['heading'] - b['heading'] for a, b in zip(ref, run)]),
        slide=rms([wrap(a['slide'] - b['slide']) for a, b in zip(ref, run)]),
        speed=rms([a['speed'] - b['speed'] for a, b in zip(ref, run)]),
        path=rms([math.hypot(a['x'] - b['x'], a['y'] - b['y']) for a, b in zip(ref, run)]),
    )


def summary(s):
    peak = max(s, key=lambda r: abs(r['slide']))
    t_peak = s.index(peak) / 60
    return f"peak slide {peak['slide']:6.1f} deg @ {t_peak:4.2f}s, turned {s[-1]['heading']:6.1f} deg, speed lost {-s[-1]['speed']} km/h"


def main():
    ref_path, ref_sync, window = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    ref = series(ref_path, 'dusa', ref_sync, window)
    print(f'reference DUSA: {summary(ref)}')
    print(f"{'build':10s} {'heading':>8s} {'slide':>8s} {'speed':>8s} {'path':>8s}   (RMS error vs DUSA: deg, deg, km/h lost, track units)")
    for spec in sys.argv[4:]:
        path, sync, label = spec.split(':')
        run = series(path, 'cce', int(sync), window)
        sc = score(ref, run)
        print(f"{label:10s} {sc['heading']:8.1f} {sc['slide']:8.1f} {sc['speed']:8.1f} {sc['path']:8.2f}   {summary(run)}")


if __name__ == '__main__':
    main()
