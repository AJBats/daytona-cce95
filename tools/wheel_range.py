"""Set how far a PC wheel turns for the Saturn Arcade Racer's full lock in Mednafen.

Mednafen stretches the PC wheel's whole range over the Saturn wheel's. Each
binding takes an optional scale (4.12 fixed point, 4096 = 1.0; Mednafen
clamps the result), so a 900 degree wheel reaches the Arcade Racer's full lock
at `degrees` with scale 4096 x 900 / degrees. This rewrites the scale on the
wheel's two steering bindings in a Mednafen home's cfg.

usage: wheel_range.py <degrees> [--pc-wheel 900] [--home build/mednafen_wheel] [--port 1]

Close that Mednafen first: it writes its cfg back when it exits.
"""
import argparse
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('degrees', type=float, help="lock to lock on the PC wheel for the Saturn wheel's full lock")
    ap.add_argument('--pc-wheel', type=float, default=900.0, help="the PC wheel's own lock to lock (G29: 900)")
    ap.add_argument('--home', default=os.path.join(os.path.dirname(__file__), '..', 'build', 'mednafen_wheel'))
    ap.add_argument('--port', type=int, default=1)
    a = ap.parse_args()

    lock = os.path.join(a.home, 'mednafen.lck')
    if os.path.exists(lock):
        try:
            os.remove(lock)          # a stale lock; a running Mednafen holds it open
        except PermissionError:
            sys.exit(f'Mednafen is running on {os.path.abspath(a.home)}: close it first')

    scale = round(4096 * a.pc_wheel / a.degrees)
    if not 4096 <= scale <= 65535:
        sys.exit(f'{a.degrees:g} degrees needs scale {scale}; Mednafen takes 4096-65535 '
                 f'({a.pc_wheel * 4096 / 65535:.0f} to {a.pc_wheel:g} degrees)')
    path = os.path.join(a.home, 'mednafen.cfg')
    lines = open(path, 'rb').read().split(b'\n')
    done = 0
    for i, line in enumerate(lines):
        for side in (b'analog_left', b'analog_right'):
            key = b'ss.input.port%d.wheel.%s ' % (a.port, side)
            if line.startswith(key):
                specs = line[len(key):].decode().split(' || ')
                out = []
                for spec in specs:
                    parts = spec.split()
                    if len(parts) >= 3 and re.match(r'abs_\d+[-+]', parts[2]):
                        parts = parts[:3] + [str(scale)]
                    out.append(' '.join(parts))
                lines[i] = key + ' || '.join(out).encode()
                done += 1
    if done != 2:
        sys.exit(f'found {done} of the 2 steering bindings in {path}')
    open(path, 'wb').write(b'\n'.join(lines))
    print(f'Saturn full lock at {a.degrees:g} of the PC wheel\'s {a.pc_wheel:g} degrees (scale {scale}) in {path}')


if __name__ == '__main__':
    main()
