"""Record DUSA's Three Seven attract demo: every car, every 20 Hz tick.

usage: attract_record.py <out.npz>
  Boots DUSA (external_resources, tools/soundlab.py's debugger) with no
  input, samples its car array every frame through the first demo, and
  writes, per scene: the tick each car array was sampled at (DUSA's frame
  number) and per car: flags (+0), position (+16, 16.16), pitch, yaw and
  roll (+28, +32, +36, 0x10000 a turn) and speed (+0x0A).

DUSA's demo (docs/attract.md, "Camera work") is three staged scenes. Its
cars move once a tick (every third frame); at a scene's start every car is
placed afresh, so the scenes are cut where every active car jumps. The
cars are DUSA's drones: AI driving, with contacts between them (turn 1 in
scene 1) and a cheaper mode while off camera (flat, angles held), so they
are recorded rather than modelled. The demo runs the same every time.
"""
import os
import shutil
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import soundlab  # noqa: E402

CARS = 0x06078900
STRIDE = 0x268
N_CARS = 21
FIRST, LAST = 1200, 4020        # boot frames: before the first scene's cut to past the third's end


def sample():
    home = soundlab.mednafen_home()
    proc, ipc = soundlab.start('dusa', dict(os.environ, MEDNAFEN_HOME=home, MEDNAFEN_ALLOWMULTI='1'))
    m = soundlab.Mednafen(ipc)
    path = os.path.join(ipc, 'cars.bin')
    try:
        m.send('deterministic', 'ok deterministic')
        m.send(f'run_to_frame {FIRST}', 'done run_to_frame', 900)
        m.send(f'mem_sample {CARS:08X} {N_CARS * STRIDE:X} {LAST - FIRST} {path}', 'done mem_sample', 1800)
        data = open(path, 'rb').read()
    finally:
        m.send('quit', 'quit', 10)
        proc.wait(timeout=30)
        shutil.rmtree(ipc, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    return np.frombuffer(data, np.uint8).reshape(-1, N_CARS * STRIDE)


def decode(raw):
    n = len(raw)
    flags = np.zeros((n, N_CARS), np.int64)
    pose = np.zeros((n, N_CARS, 6), np.int64)
    speed = np.zeros((n, N_CARS), np.int64)
    for f in range(n):
        b = raw[f].tobytes()
        for c in range(N_CARS):
            o = c * STRIDE
            flags[f, c] = struct.unpack_from('>I', b, o)[0]
            pose[f, c, :3] = struct.unpack_from('>3i', b, o + 16)
            pose[f, c, 3:] = [v & 0xFFFF for v in struct.unpack_from('>3i', b, o + 28)]
            speed[f, c] = struct.unpack_from('>h', b, o + 0x0A)[0]
    return flags, pose, speed


def main():
    out = sys.argv[1]
    flags, pose, speed = decode(sample())
    moved = np.any(pose[1:, :, :3] != pose[:-1, :, :3], axis=(1, 2))
    ticks = np.nonzero(moved)[0] + 1                  # rows where a tick's update landed
    jump = np.linalg.norm((pose[ticks[1:], :, :3] - pose[ticks[:-1], :, :3]) / 65536, axis=2)
    active = flags[ticks[1:]] != 0
    cut = [i + 1 for i in range(len(jump)) if np.all(jump[i][active[i]] > 20)]
    starts = [cut[0]] + cut[1:]
    ends = cut[1:] + [len(ticks)]
    save = {}
    for s, (a, b) in enumerate(zip(starts, ends)):
        rows = ticks[a:b]
        save[f'frames{s}'] = rows + FIRST
        save[f'flags{s}'] = flags[rows]
        save[f'pose{s}'] = pose[rows]
        save[f'speed{s}'] = speed[rows]
        print(f'scene {s + 1}: {len(rows)} ticks from frame {rows[0] + FIRST}, '
              f'{int(np.sum(flags[rows[0]] != 0))} cars active')
    np.savez_compressed(out, scenes=len(starts), **save)


if __name__ == '__main__':
    main()
