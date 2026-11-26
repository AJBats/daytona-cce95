"""Record the player's own drives through a corner, in DUSA or Ultimate, to compare the two.

usage:
  corner_lab.py play dusa|ult [home]
      Start a visible Mednafen on the game with the player's controller home
      (default build/mednafen_g29digital) and hand it over, running from boot.
      From the first frame it logs the controller (input_trace) and samples
      the player's car every frame (mem_sample), into a new session folder
      build/corner_lab/<game>_<time>/. The player drives the menus and the
      race; the home's save state keys set up and retry the approach, and
      every state load starts a new segment.
  corner_lab.py stop dusa|ult
      Close the logs of that game's latest session and copy the save states
      the player made into the session folder. Mednafen keeps running.
  corner_lab.py summary <session> [first last]
      Each segment (boot, then one per state load) of the session, and in it
      every gear change: frame, gear, km/h, position, slide angle; then the
      segment's lowest km/h and largest slide. Optional sample range.

Car records (both games use the same world coordinates; angles are 16-bit,
0x10000 to the turn; the slide angle is heading minus direction of travel):
  DUSA  06078900, 0x300 bytes: km/h +08, x y z +10 +14 +18, travel +28,
        heading +30, gear +DC (0-3)
  Ultimate (CCE's player car)  0605224C, 0x400 bytes: x y z +00 +04 +08,
        km/h +34, travel +38, heading +3C, gear +17A (0-3)
"""
import glob
import json
import os
import shutil
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import record_replay  # noqa: E402
from record_replay import send  # noqa: E402

# Mednafen ignores a command whose header repeats the last one, and every run
# of this script talks to the same emulator: number commands from the clock
record_replay.seq = int(time.time() * 100) % 10**9

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUILD = os.path.join(PROJ, 'build')
LAB = os.path.join(BUILD, 'corner_lab')
EXE = os.path.join(PROJ, 'tools', 'mednafen', 'mednafen_gcc494.exe')
DEFAULT_HOME = os.path.join(BUILD, 'mednafen_g29digital')

GAMES = {
    'dusa': {
        'cue': os.path.join(PROJ, 'external_resources', 'Daytona USA (USA)', 'Daytona USA (USA).cue'),
        'car': 0x06078900, 'size': 0x300,
        'kmh': 0x08, 'pos': 0x10, 'travel': 0x28, 'heading': 0x30, 'gear': 0xDC,
    },
    'ult': {
        'cue': os.path.join(BUILD, 'disc', 'cce.cue'),
        'car': 0x0605224C, 'size': 0x400,
        'kmh': 0x34, 'pos': 0x00, 'travel': 0x38, 'heading': 0x3C, 'gear': 0x17A,
    },
}
SAMPLE_FRAMES = 60 * 60 * 120       # two hours; `stop` ends it sooner


def latest(game):
    found = sorted(glob.glob(os.path.join(LAB, f'{game}_*')))
    if not found:
        sys.exit(f'no {game} session in {LAB}')
    return found[-1]


def play(game, home):
    g = GAMES[game]
    home = os.path.abspath(home)
    session = os.path.join(LAB, time.strftime(f'{game}_%Y%m%d_%H%M%S'))
    ipc = os.path.join(session, 'ipc')
    os.makedirs(ipc)
    # no frameskip: the input trace and the sampler count drawn frames, so a
    # skipped frame would shift the samples against the buttons
    proc = subprocess.Popen(
        [EXE, '--sound', '1', '-video.frameskip', '0', '--automation', ipc, g['cue']],
        env=dict(os.environ, MEDNAFEN_HOME=home, MEDNAFEN_ALLOWMULTI='1'), cwd=PROJ,
        stdout=open(os.path.join(session, 'stdout.txt'), 'w'),
        stderr=open(os.path.join(session, 'stderr.txt'), 'w'))
    ack = os.path.join(ipc, 'mednafen_ack.txt')
    deadline = time.time() + 60
    while not (os.path.exists(ack) and 'ready' in open(ack).read()):
        if proc.poll() is not None or time.time() > deadline:
            sys.exit(f'Mednafen did not start; see {session}/stderr.txt')
        time.sleep(0.2)
    send(ipc, 'show_window', 'ok show_window')
    send(ipc, f'input_trace {os.path.join(session, "inputs.txt")}', 'ok input_trace')
    first = int(send(ipc, 'status', 'status').split('frame=')[1].split()[0])
    # mem_sample also sets the emulator running
    send(ipc, f'mem_sample {g["car"]:08X} {g["size"]:X} {SAMPLE_FRAMES} {os.path.join(session, "car.bin")}',
         'ok mem_sample')
    json.dump({'game': game, 'home': home, 'cue': g['cue'], 'pid': proc.pid, 'first_frame': first,
               'started': time.time()}, open(os.path.join(session, 'session.json'), 'w'), indent=1)
    print(f'{game} running in {session} (pid {proc.pid}), car samples from frame {first}')


def stop(game):
    session = latest(game)
    info = json.load(open(os.path.join(session, 'session.json')))
    ipc = os.path.join(session, 'ipc')
    print(send(ipc, 'mem_sample_stop', 'mem_sample_stop', 10))
    send(ipc, 'input_trace_stop', 'ok input_trace_stop', 10)
    for path in glob.glob(os.path.join(info['home'], 'mcs', '*')):
        if os.path.getmtime(path) >= info['started']:
            shutil.copy2(path, session)
            print('kept', os.path.basename(path))


def angle(v):
    return ((v + 0x8000) & 0xFFFF) - 0x8000


def summary(session, first=None, last=None):
    info = json.load(open(os.path.join(session, 'session.json')))
    g = GAMES[info['game']]
    data = open(os.path.join(session, 'car.bin'), 'rb').read()
    n = len(data) // g['size']
    loads = [0]
    for line in open(os.path.join(session, 'inputs.txt')):
        if 'SYSCMD LOAD_STATE' in line:
            loads.append(int(line.split()[0][6:]) - info['first_frame'])
    loads.append(n)
    first = 0 if first is None else first
    last = n if last is None else last

    def rec(i):
        o = i * g['size']
        get = lambda off: struct.unpack_from('>i', data, o + off)[0]
        x, _, z = (struct.unpack_from('>i', data, o + g['pos'] + 4 * k)[0] / 65536 for k in range(3))
        slide = angle(get(g['heading']) - get(g['travel'])) * 360 / 65536
        gear = struct.unpack_from('>H', data, o + g['gear'])[0]
        return gear, get(g['kmh']), x, z, slide

    print(f'{session}: {n} samples, {len(loads) - 2} state loads')
    for s, e in zip(loads, loads[1:]):
        s, e = max(s, first), min(e, last)
        if s >= e:
            continue
        print(f'segment {s}-{e}')
        prev, low, wide = None, None, (0, s)
        for i in range(s, e):
            gear, kmh, x, z, slide = rec(i)
            if gear != prev:
                print(f'  {i - s:6d}  gear {gear + 1}  {kmh:4d} km/h  x {x:8.1f} z {z:8.1f}  slide {slide:6.1f}')
                prev = gear
            if kmh > 0 and (low is None or kmh < low[0]):
                low = (kmh, i - s)
            if abs(slide) > abs(wide[0]) and kmh > 30:
                wide = (slide, i - s)
        if low:
            print(f'  lowest {low[0]} km/h at {low[1]}, largest slide {wide[0]:.1f} deg at {wide[1]}')


def main():
    args = sys.argv[1:]
    if len(args) in (2, 3) and args[0] == 'play' and args[1] in GAMES:
        play(args[1], args[2] if len(args) == 3 else DEFAULT_HOME)
    elif len(args) == 2 and args[0] == 'stop' and args[1] in GAMES:
        stop(args[1])
    elif len(args) in (2, 4) and args[0] == 'summary':
        summary(args[1], *map(int, args[2:]))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
