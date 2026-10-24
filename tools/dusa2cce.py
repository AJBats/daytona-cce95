"""Put CCE95's car where DUSA's was and play DUSA's buttons from there.

usage:
  dusa2cce.py place <cce state> <dusa trace.bin> <index> <out state>
      Load a CCE95 state near the spot (same course, same direction) and
      set the car to DUSA's at trace index <index> of a soundlab recording
      (car struct 06078900, 0x200 bytes a frame); save <out state>.
  dusa2cce.py inputs <dusa take.txt> <index> <out script>
      DUSA's buttons from that moment on, as a CCE script from <out state>:
      by function (DUSA C gas -> CCE B, B brake -> A), buttons held at that
      moment pressed at frame 0.

Both games use the same world coordinates. CCE keeps the car's position
three times (06051FAC, the car at 0605224C, 060527DC: x, y, z), so all
three move; writing only the car's leaves a stale copy that stops the car
update (docs/conformance.md). Angles, speed (per tick: x 2/3 at 30 Hz),
km/h, slip and yaw are the handling work's field pairs (tools/teacher.py).
Gear and rpm are left to CCE, which recomputes rpm from speed every tick.
A trace index i holds DUSA after frame i + 1 of the replay, and the take
event at frame F first shows at index F, so events from frame index + 1 on
follow, at frame - (index + 1).

Turn 3 of Three Seven this way (docs/tyre_sound.md): the path stays within
~3 units of DUSA's through the whole slide.
"""
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import soundlab  # noqa: E402

CAR = 0x0605224C
POSITIONS = (0x06051FAC, CAR, 0x060527DC)
# CCE offset: (DUSA offset, scale)
FIELDS = {0x3C: (0x30, 1), 0x38: (0x28, 1), 0x24: (0x0C, 2 / 3), 0x34: (0x08, 1), 0x68: (0x5C, 1), 0x64: (0x58, 1)}
BUTTONS = {'C': 'B', 'B': 'A', 'LEFT': 'LEFT', 'RIGHT': 'RIGHT', 'UP': 'UP', 'DOWN': 'DOWN', 'START': 'START'}


def place(state, trace, index, out):
    t = open(trace, 'rb').read()
    get = lambda o: struct.unpack_from('>i', t, 0x200 * index + o)[0]
    home = soundlab.mednafen_home()
    proc, ipc = soundlab.start('cce', dict(os.environ, MEDNAFEN_HOME=home, MEDNAFEN_ALLOWMULTI='1'))
    m = soundlab.Mednafen(ipc)
    m.send('load_state ' + os.path.abspath(state), 'ok load_state')
    car = m.read(CAR, 0x40)
    print('CCE95 was at', struct.unpack_from('>3i', car, 0), 'km/h', struct.unpack_from('>i', car, 0x34)[0])
    pos = struct.pack('>3i', get(0x10), get(0x14), get(0x18))
    for base in POSITIONS:
        m.poke(base, pos)
    for coff, (doff, scale) in FIELDS.items():
        m.poke(CAR + coff, struct.pack('>i', round(get(doff) * scale)))
    print('now at DUSA\'s', struct.unpack('>3i', pos), 'km/h', get(0x08))
    m.send('save_state ' + os.path.abspath(out), 'save_state')
    m.send('quit', 'quit', 10)
    proc.wait(timeout=30)
    shutil.rmtree(ipc)
    shutil.rmtree(home)


def inputs(take, index, out):
    shift = index + 1
    held, events = set(), []
    for line in open(take):
        if not line.startswith('frame='):
            continue
        f, kind, button = line.split()
        f = int(f[6:])
        if f < shift:
            (held.add if kind == 'PRESS' else held.discard)(button)
        else:
            events.append(f'frame={f - shift} {kind} {BUTTONS[button]}')
    lines = [f'# {os.path.basename(take)} from frame {shift} (DUSA trace index {index}), for CCE95',
             '# by function: DUSA C gas -> CCE B, B brake -> A']
    lines += [f'frame=0 PRESS {BUTTONS[b]}' for b in sorted(held)] + events
    open(out, 'w').write('\n'.join(lines) + '\n')
    print(f'{out}: {len(lines) - 2} events, held at the start: {" ".join(sorted(held)) or "nothing"}')


def main():
    if len(sys.argv) == 6 and sys.argv[1] == 'place':
        place(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif len(sys.argv) == 5 and sys.argv[1] == 'inputs':
        inputs(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
