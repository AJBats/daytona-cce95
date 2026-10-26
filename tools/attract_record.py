"""Record DUSA's attract demos on its three courses: every car, every 20 Hz tick.

usage: attract_record.py <out.npz>
  Boots DUSA (external_resources, tools/soundlab.py's debugger) with no
  input, samples its car array every frame through each of the first three
  demos (Three Seven, Dinosaur Canyon, Seaside Galaxy, in that order), and
  writes, per course c and scene s (keys c<c>_frames<s> and so on): the
  frame each car array was sampled at (DUSA's frame number) and per car:
  flags (+0), position (+16, 16.16), pitch, yaw and roll (+28, +32, +36,
  0x10000 a turn) and speed (+0x0A); c<c>_scenes is the scene count.

DUSA's demos (docs/attract.md, "Camera work") are staged scenes: three on
Three Seven, one on Dinosaur Canyon, four on Seaside Galaxy. Its cars move
once a tick (every third frame). A demo's first scene starts on the first
tick of its attract state 3 (DUSA places the cars once before, in state 2);
at a later scene's start the scene's cars are placed afresh, so it is cut
where at least 8 cars jump and every active car does (single cars also
jump mid-scene as they come back from the cheap mode below). The cars are
DUSA's drones: AI driving, with contacts between them (turn 1 in Three
Seven's first scene) and a cheaper mode while off camera (flat, angles
held), so they are recorded rather than modelled. The demos run the same
every time.
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
# boot frames: from before each demo's first scene to past its end (DUSA's
# attract state 0605AD10 goes 4 -> 5 at 4009, 8091, 12057), the frame its
# state goes 2 -> 3, and the scenes it plays
DEMOS = [(1200, 4020, 1244, 3), (5280, 8100, 5326, 1), (9430, 12065, 9472, 4)]


def sample():
    home = soundlab.mednafen_home()
    proc, ipc = soundlab.start('dusa', dict(os.environ, MEDNAFEN_HOME=home, MEDNAFEN_ALLOWMULTI='1'))
    m = soundlab.Mednafen(ipc)
    out = []
    try:
        m.send('deterministic', 'ok deterministic')
        for d, (first, last, _, _) in enumerate(DEMOS):
            path = os.path.join(ipc, f'cars{d}.bin')
            m.send(f'run_to_frame {first}', 'done run_to_frame', 900)
            m.send(f'mem_sample {CARS:08X} {N_CARS * STRIDE:X} {last - first} {path}', 'done mem_sample', 1800)
            out.append(np.frombuffer(open(path, 'rb').read(), np.uint8).reshape(-1, N_CARS * STRIDE))
    finally:
        m.send('quit', 'quit', 10)
        proc.wait(timeout=30)
        shutil.rmtree(ipc, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    return out


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
    save = {'courses': len(DEMOS)}
    for c, ((first, _, state3, n_scenes), raw) in enumerate(zip(DEMOS, sample())):
        flags, pose, speed = decode(raw)
        moved = np.any(pose[1:, :, :3] != pose[:-1, :, :3], axis=(1, 2))
        ticks = np.nonzero(moved)[0] + 1                  # rows where a tick's update landed
        start = int(np.nonzero(ticks + first >= state3)[0][0])
        jump = np.linalg.norm((pose[ticks[1:], :, :3] - pose[ticks[:-1], :, :3]) / 65536, axis=2) > 20
        active = flags[ticks[1:]] != 0
        cut = [start] + [i + 1 for i in range(start, len(jump))
                         if jump[i].sum() >= 8 and np.all(jump[i][active[i]])]
        if len(cut) != n_scenes:
            sys.exit(f'course {c}: {len(cut)} scene starts found, {n_scenes} expected')
        ends = cut[1:] + [len(ticks)]
        for s, (a, b) in enumerate(zip(cut, ends)):
            rows = ticks[a:b]
            save[f'c{c}_frames{s}'] = rows + first
            save[f'c{c}_flags{s}'] = flags[rows]
            save[f'c{c}_pose{s}'] = pose[rows]
            save[f'c{c}_speed{s}'] = speed[rows]
            print(f'course {c} scene {s + 1}: {len(rows)} ticks from frame {rows[0] + first}, '
                  f'{int(np.sum(flags[rows[0]] != 0))} cars active')
        save[f'c{c}_scenes'] = n_scenes
    np.savez_compressed(out, **save)


if __name__ == '__main__':
    main()
