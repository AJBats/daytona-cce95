"""VDP1's time over a lap of each course, measured in Mednafen with the Saturn
timing the Tomb Raider project calibrated against a real Saturn.

usage: vdp1_lap.py <disc cue> <name> [course ...]
  Writes build/vdp1cost/<name>_<course>/: f000.csv... (a VDP1 cost log every
  STEP frames: a row per command with its cycles, lines, pixels and texels),
  vram.bin, and a screenshot every 20 logs. Courses: t7 dino sea np desert
  (all by default). Then prints each course's frame costs.

The Mednafen is the Tomb Raider project's fork (TombRaiderSaturn
tools/mednafen, copied to tools/mednafen/mednafen_tr.exe), run beside the
debugger with its own home (build/mednafen_tr_home: the debugger's
mednafen.cfg and firmware) and automation folder (build/mcp_tr), with that
project's calibrated costs (its tools/mednafen_timing.py): a texel 20/16 of
a cycle more, a gouraud pixel 14/16, a line 262/16; the SH-2's MAC and
multiply waits; both caches emulated. Its command vdp1_cost_log writes the
next plot's costs.

A lap: from a race just after the start, the player car is put each tick
(06035EE8, the camera yaw routine, before the camera reads the car) where
a drone was at that tick, recorded over the first minute of the same race
(build/vdp1cost/path_<course>.csv, kept, so builds compare on one path):
position, pitch, yaw and roll, and travel and heading (+0x38, +0x3C) as the
drone's yaw, so the chase camera drives the drone's line. The races come
from the Arcade course select (a state made from boot with the menu inputs
below, once per disc), with the automatic gearbox.

VDP1's share of a frame: it starts a list at the frame change (VBlank-OUT)
and the kernel copies the next list over it at the VBlank-IN two fields on
(06047B90), 486.5 of 525 lines: 92.7%.
"""
import csv
import glob
import os
import struct
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import record_replay  # noqa: E402

EXE = os.path.join(ROOT, 'tools', 'mednafen', 'mednafen_tr.exe')
HOME = os.path.join(ROOT, 'build', 'mednafen_tr_home')
IPC = os.environ.get('VDP1_LAP_IPC', os.path.join(ROOT, 'build', 'mcp_tr'))     # another to run two at once
OUT = os.path.join(ROOT, 'build', 'vdp1cost')
CALIBRATED = ['-ss.vdp1.cost.texel', '20', '-ss.vdp1.cost.tex_pixel', '0', '-ss.vdp1.cost.gouraud', '14',
              '-ss.vdp1.cost.pixel', '0', '-ss.vdp1.cost.line', '262', '-ss.sh2.cost.mac_w', '8',
              '-ss.sh2.cost.mac_wait', '2', '-ss.sh2.cost.mul_l', '4', '-ss.sh2.cost.dmul', '3',
              '-ss.dbg_cem', 'full']
COURSES = ['t7', 'dino', 'sea', 'np', 'desert']
LOGS, STEP = 190, 10
F = 28636360 // 30
BUDGET = 0.927
DRONES, DRONE_SIZE, DRONE_COUNT = 0x060FC000, 0x200, 32
PLAYER = 0x0605224C
# From boot to the main menu with TIME ATTACK lit (deterministic clock): the frames each
# button is pressed and released. Then UP and C give the Arcade course select.
MENU = [(197, 201, 'START'), (961, 968, 'START'), (2003, 2007, 'START'), (2331, 2336, 'START'),
        (2429, 2435, 'DOWN'), (2443, 2451, 'DOWN'), (2553, 2559, 'UP'), (2629, 2635, 'UP'),
        (2714, 2720, 'DOWN'), (2727, 2736, 'DOWN'), (3042, 3049, 'DOWN'), (3056, 3063, 'DOWN'),
        (3074, 3079, 'UP'), (3085, 3092, 'UP')]


class Mednafen:
    def __init__(self, cue):
        os.makedirs(IPC, exist_ok=True)
        for n in ('mednafen_action.txt', 'mednafen_ack.txt'):
            if os.path.exists(os.path.join(IPC, n)):
                os.remove(os.path.join(IPC, n))
        if not os.path.exists(HOME):
            src = os.environ.get('MEDNAFEN_HOME', os.path.expanduser('~/.mednafen'))
            os.makedirs(os.path.join(HOME, 'firmware'))
            open(os.path.join(HOME, 'mednafen.cfg'), 'wb').write(open(os.path.join(src, 'mednafen.cfg'), 'rb').read())
            for n in os.listdir(os.path.join(src, 'firmware')):
                open(os.path.join(HOME, 'firmware', n), 'wb').write(open(os.path.join(src, 'firmware', n), 'rb').read())
        env = dict(os.environ, MEDNAFEN_HOME=HOME, MEDNAFEN_ALLOWMULTI='1')
        self.err = open(os.path.join(IPC, 'stderr.txt'), 'w')
        self.proc = subprocess.Popen([EXE, '--sound', '0', '-cd.image_memcache', '1'] + CALIBRATED +
                                     ['--automation', IPC, os.path.abspath(cue)],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=self.err, env=env)
        record_replay.seq = int.from_bytes(os.urandom(3), 'big')
        time.sleep(4)

    def send(self, cmd, key, timeout=600):
        if self.proc.poll() is not None:
            sys.exit(f'Mednafen exited: see {self.err.name}')
        return record_replay.send(IPC, cmd, key, timeout)

    def frames(self, n):
        self.send(f'frame_advance {n}', 'done frame_advance')

    def tap(self, button, after):
        self.send(f'input {button}', 'input')
        self.frames(6)
        self.send(f'input_release {button}', 'input_release')
        self.frames(after)

    def quit(self):
        self.send('quit', 'quit', 30)
        self.proc.wait(timeout=30)


def course_select(m, state):
    """The Arcade course select, from boot (the menu inputs played back by the emulator, frame exact)."""
    script = os.path.join(IPC, 'menu.txt')
    with open(script, 'w') as f:
        for down, up, button in MENU:
            f.write(f'frame={down} PRESS {button}\nframe={up} RELEASE {button}\n')
    m.send('deterministic', 'deterministic')
    m.send(f'input_playback {script}', 'input_playback')
    m.frames(3120)
    m.send('input_playback_stop', 'input_playback')
    m.send('input_clear', 'input')
    m.tap('UP', 30)
    m.tap('C', 400)
    m.send(f'screenshot {state[:-4]}.png', 'screenshot')
    m.send(f'save_state {state}', 'save_state')


def race(m, cs_state, c, state):
    m.send(f'load_state {cs_state}', 'load_state')
    m.frames(2)
    for _ in range(c):
        m.tap('DOWN', 30)
    m.tap('C', 60)      # course
    m.tap('C', 200)     # car
    m.tap('C', 60)      # automatic
    m.frames(1150)
    m.send(f'screenshot {state[:-4]}.png', 'screenshot')
    m.send(f'save_state {state}', 'save_state')


def drone_path(m, state, path):
    """The farthest-travelling drone over the first minute, as playback rows."""
    m.send(f'load_state {state}', 'load_state')
    dump = os.path.join(IPC, 'drones.bin')
    rows = []
    for _ in range(1000):
        m.frames(2)
        m.send(f'dump_mem_bin {DRONES:08X} {DRONE_SIZE * DRONE_COUNT:X} {dump}', 'dump_mem_bin')
        d = open(dump, 'rb').read()
        rows.append([struct.unpack_from('>3iHHh', d, k * DRONE_SIZE) for k in range(DRONE_COUNT)])
    a = np.array(rows, np.int64)
    k = int(np.argmax(np.abs(np.diff(a[:, :, :3] / 65536.0, axis=0)).sum(axis=(0, 2))))
    word = lambda v, bits=32: f'{int(v) & ((1 << bits) - 1):x}'
    yaw32 = lambda v: (int(v) ^ 0x8000) - 0x8000
    with open(path, 'w') as f:
        f.write('x,y,z,ang,roll,trav,head\n')
        for x, y, z, pitch, yaw, roll in a[:, k]:
            f.write(f'{word(x)},{word(y)},{word(z)},{word((int(pitch) << 16) | int(yaw))},{word(roll, 16)},'
                    f'{word(yaw32(yaw))},{word(yaw32(yaw))}\n')


def lap(m, state, path, out):
    os.makedirs(out, exist_ok=True)
    m.send(f'load_state {state}', 'load_state')
    m.send(f'poke_playback_start 06035EE8 {PLAYER:08X} 0 -1 hold 7 x:0:32 y:4:32 z:8:32 ang:C:32 '
           f'roll:10:16 trav:38:32 head:3C:32 {path}', 'poke_playback')
    m.send(f'dump_region vdp1_vram {os.path.join(out, "vram.bin")}', 'dump_region')
    for i in range(LOGS):
        m.send(f'vdp1_cost_log {os.path.join(out, f"f{i:03d}.csv")}', 'vdp1_cost_log')
        m.frames(STEP)
        if i % 20 == 0:
            m.send(f'screenshot {os.path.join(out, f"f{i:03d}.png")}', 'screenshot')
    m.send('poke_playback_stop', 'poke_playback')


def summary(out):
    costs = sorted(sum(int(r['cycles']) for r in csv.DictReader(open(p)))
                   for p in glob.glob(os.path.join(out, 'f*.csv')))
    n = len(costs)
    over = sum(1 for c in costs if c > BUDGET * F)
    return (f'mean {100 * sum(costs) / n / F:.1f}%, 90th {100 * costs[int(n * 0.9)] / F:.1f}%, '
            f'max {100 * costs[-1] / F:.1f}% of a frame; {over} of {n} over VDP1\'s {100 * BUDGET:.1f}%')


def main():
    cue, name = sys.argv[1], sys.argv[2]
    courses = sys.argv[3:] or COURSES
    states = os.path.join(OUT, f'{name}_states')
    os.makedirs(states, exist_ok=True)
    m = Mednafen(cue)
    try:
        cs_state = os.path.join(states, 'course_select.mcs')
        if not os.path.exists(cs_state):
            course_select(m, cs_state)
        for course in courses:
            c = COURSES.index(course)
            state = os.path.join(states, f'{course}.mcs')
            if not os.path.exists(state):
                race(m, cs_state, c, state)
            path = os.path.join(OUT, f'path_{course}.csv')
            if not os.path.exists(path):
                drone_path(m, state, path)
            out = os.path.join(OUT, f'{name}_{course}')
            lap(m, state, path, out)
            print(f'{name} {course}: {summary(out)}', flush=True)
    finally:
        m.quit()


if __name__ == '__main__':
    main()
