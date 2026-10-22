"""Rebuild a pad button script from a DUSA car-struct recording.

DUSA updates the car every 3 frames. At each tick the struct shows:
  +0xAC steering ramp: < 0 while LEFT held, > 0 while RIGHT held, 0 released
  +0x68 throttle (C): rises or stays at 255 while held, falls when released
  +0x84 brake (B): rises or stays at 255 while held, falls when released
Events are emitted relative to the first tick where the car moves, plus
`lead` frames so the press is down before the game samples it.

usage: inputscript.py <recording.bin> <out.txt> [lead]
Output lines: frame=<n> PRESS|RELEASE <BUTTON>, n relative to motion start.
"""
import struct
import sys

N = 768


def main():
    rec, out = sys.argv[1], sys.argv[2]
    lead = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    d = open(rec, 'rb').read()
    frames = len(d) // N
    g = lambda f, o: struct.unpack_from('>i', d, f * N + o)[0]

    x0 = g(0, 0x10)
    start = next(f for f in range(frames) if g(f, 0x10) != x0)
    ticks = [f for f in range(start, frames - 1)
             if any(g(f, o) != g(f - 1, o) for o in (0x10, 0x18, 0x68, 0x84, 0xAC)) or (f - start) % 3 == 0]
    ticks = list(range(start, frames, 3))

    state = {'LEFT': False, 'RIGHT': False, 'B': False, 'C': True}
    events = []
    prev_t, prev_b = g(start - 1, 0x68), g(start - 1, 0x84)
    for t in ticks:
        steer, thr, brk = g(t, 0xAC), g(t, 0x68), g(t, 0x84)
        want = {
            'LEFT': steer < 0,
            'RIGHT': steer > 0,
            'B': brk > 0 and brk >= prev_b,
            'C': thr > 0 and thr >= prev_t,
        }
        for btn, on in want.items():
            if on != state[btn]:
                events.append((t - start - lead, 'PRESS' if on else 'RELEASE', btn))
                state[btn] = on
        prev_t, prev_b = thr, brk
    with open(out, 'w') as f:
        f.write(f'# from {rec}: motion starts at frame {start}; frames relative to it\n')
        for fr, kind, btn in events:
            f.write(f'frame={fr} {kind} {btn}\n')
    print(f'motion start {start}, {len(events)} events -> {out}')


if __name__ == '__main__':
    main()
