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
  corner_lab.py replay <dusa session> <ult state> <lap> <downshift> <phase> <out.bin> [lead] [home]
      Drive a DUSA pass into Ultimate, in a hidden Mednafen of its own. The
      state is a Time Attack race on the same course from the current disc,
      made with the same controller home (default build/mednafen_g29digital).
      Ultimate's car follows DUSA's recorded path each tick from DUSA sample
      <lap> (the lap's start, so the course grid follows), takes DUSA's whole
      state at <downshift> - <lead> (default 60), then runs open loop on
      DUSA's inputs: the d-pad as recorded, each gear DUSA took on an H gate
      (X Y Z C), the gas as DUSA's throttle moved; the brake isn't replayed.
      <phase> moves every input by that many frames (run -1, 0 and 1: the
      two games' ticks fall differently). Writes Ultimate's car every frame
      (0x400 bytes) to <out.bin>, beside it the inputs and the lead-in.
  corner_lab.py compare <dusa session> <downshift> <lead> <run.bin> ...
      DUSA's pass against replays of it: peak slide, lowest km/h, gears and
      how far apart the paths are.

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
    if open(os.path.join(ipc, 'mednafen_ack.txt')).read().startswith('shutdown'):
        print('Mednafen was closed: its logs are complete')     # files are closed at exit
    else:
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


def dusa_session(session):
    info = json.load(open(os.path.join(session, 'session.json')))
    if info['game'] != 'dusa':
        sys.exit(f'{session} is not a DUSA session')
    return info, open(os.path.join(session, 'car.bin'), 'rb').read()


# DUSA field -> Ultimate field, and how the value converts at 30 Hz: tick (a
# per-tick quantity, x 2/3), ticks (a tick counter, x 8/5); docs/conformance.md
STATE_FIELDS = [(0x28, 0x38, ''), (0x30, 0x3C, ''), (0x0C, 0x24, 'tick'), (0x08, 0x34, ''),
                (0x58, 0x64, ''), (0x5C, 0x68, ''), (0x178, 0x104, 'tick'), (0x154, 0x44, 'tick'),
                (0x60, 0xE8, ''), (0x64, 0xEC, ''), (0x140, 0xF4, ''), (0x144, 0xF8, ''),
                (0x10C, 0x70, ''), (0x110, 0x100, ''), (0xAC, 0x78, ''), (0xB0, 0x7C, ''),
                (0xD0, 0xAC, ''), (0x68, 0x80, ''), (0x84, 0x90, ''),
                (0xE0, 0xD0, ''), (0xE4, 0xD4, ''), (0xC4, 0xA4, ''), (0xC0, 0xA0, ''),
                (0xD8, 0xB8, 'ticks'), (0x10, 0x00, ''), (0x14, 0x04, ''), (0x18, 0x08, '')]
H_GATE = ['X', 'Y', 'Z', 'C']           # gears 1-4; gas B, brake A


def replay(dusa, state, lap, down, phase, out, lead=60, home=DEFAULT_HOME, frames=360):
    info, d = dusa_session(dusa)
    out = os.path.abspath(out)
    rel = down - lead
    sz = GAMES['dusa']['size']
    get = lambda f, o: struct.unpack_from('>i', d, f * sz + o)[0]
    gear = lambda f: struct.unpack_from('>H', d, f * sz + 0xDC)[0]

    # DUSA acts on a traced press a frame before the trace logs it
    events, steer = [], set()
    for line in open(os.path.join(dusa, 'inputs.txt')):
        parts = line.split()
        if len(parts) != 3 or not line.startswith('frame=') or parts[1] not in ('PRESS', 'RELEASE'):
            continue
        s = int(parts[0][6:]) - info['first_frame'] - 1
        act, btn = parts[1], parts[2]
        if btn in ('LEFT', 'RIGHT'):
            if s <= rel:
                (steer.add if act == 'PRESS' else steer.discard)(btn)
            elif s < rel + frames:
                events.append((s - rel + phase, act, btn))
        elif act == 'PRESS' and rel < s < rel + frames and btn != 'START':
            g0 = gear(s)
            g1 = next((gear(k) for k in range(s, s + 8) if gear(k) != g0), None)
            if g1 is not None:
                events += [(s - rel + phase, 'PRESS', H_GATE[g1]), (s - rel + phase + 6, 'RELEASE', H_GATE[g1])]
    # the throttle climbs while DUSA's gas is held and falls while it isn't
    thr = [get(k, 0x68) for k in range(rel, rel + frames + 3)]
    gas = thr[0] > 0
    for k in range(3, len(thr)):
        up = thr[k] > thr[k - 3] or thr[k] == 255
        if gas != up and (up or thr[k] < thr[k - 3] or thr[k] == 0):
            gas = up
            events.append((k - 3 + phase, 'PRESS' if up else 'RELEASE', 'B'))
    lines = [f'frame=1 PRESS {b}' for b in sorted(steer)] + (['frame=1 PRESS B'] if thr[0] > 0 else [])
    lines += [f'frame={max(f, 1)} {a} {b}' for f, a, b in sorted(events)]
    script = out[:-4] + '_inputs.txt'
    open(script, 'w').write('\n'.join(lines) + '\n')
    u32 = lambda v: v & 0xFFFFFFFF
    rows = ['x,y,z,trav,head'] + [','.join(f'{u32(get(f, o)):x}' for o in (0x10, 0x14, 0x18, 0x28, 0x30))
                                  for f in range(lap, rel + 1, 2)]
    lead_csv = out[:-4] + '_lead.csv'
    open(lead_csv, 'w').write('\n'.join(rows) + '\n')

    # a home of its own: Mednafen rewrites its cfg on exit
    run_dir = out[:-4] + '_run'
    own = os.path.join(run_dir, 'home')
    shutil.rmtree(run_dir, ignore_errors=True)
    shutil.copytree(home, own, ignore=shutil.ignore_patterns('mcs', 'sav', 'snaps', '*.lck'))
    ipc = os.path.join(run_dir, 'ipc')
    os.makedirs(ipc)
    proc = subprocess.Popen([EXE, '--sound', '0', '-video.frameskip', '0', '--automation', ipc, GAMES['ult']['cue']],
                            env=dict(os.environ, MEDNAFEN_HOME=own, MEDNAFEN_ALLOWMULTI='1'), cwd=PROJ,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=open(os.path.join(run_dir, 'stderr.txt'), 'w'))
    ack = os.path.join(ipc, 'mednafen_ack.txt')
    deadline = time.time() + 60
    while not (os.path.exists(ack) and 'ready' in open(ack).read()):
        if proc.poll() is not None or time.time() > deadline:
            sys.exit(f'Mednafen did not start; see {run_dir}/stderr.txt')
        time.sleep(0.2)
    poke = lambda addr, data: send(ipc, f'poke {addr:08X} ' + ' '.join(f'{b:02X}' for b in data), 'ok poke')
    car = GAMES['ult']['car']
    send(ipc, 'hide_window', 'ok hide_window')
    send(ipc, f'load_state {os.path.abspath(state)}', 'ok load_state')
    for off, mask in ((0x14, 0), (0x16, 0), (0x18, 0x100), (0x1A, 0x400), (0x1C, 0x40), (0x1E, 0x20),
                      (0x20, 0x10), (0x22, 0x200)):
        poke(0x0605273C + off, struct.pack('>H', mask))       # the key config: H gate
    send(ipc, 'input B', 'ok input')
    send(ipc, f'poke_playback_start 06035EE8 {car:08X} 0 -1 hold 5 x:0:32 y:4:32 z:8:32 trav:38:32 head:3C:32 '
              f'{lead_csv.replace(os.sep, "/")}', 'poke_playback')
    send(ipc, f'frame_advance {2 * (len(rows) - 1) + 2}', 'done frame_advance', 600)
    send(ipc, 'poke_playback_stop', 'poke_playback')
    send(ipc, 'input_release B', 'input_release')
    for doff, coff, kind in STATE_FIELDS:
        v = get(rel, doff)
        v = round(v * 2 / 3) if kind == 'tick' else round(v * 8 / 5) if kind == 'ticks' else v
        poke(car + coff, struct.pack('>I', u32(v)))
    poke(car + 0x17A, d[rel * sz + 0xDC:rel * sz + 0xE0])          # gear and the gearbox's word after it
    send(ipc, f'input_playback {script}', 'ok input_playback')
    send(ipc, f'mem_sample {car:08X} {GAMES["ult"]["size"]:X} {frames} {out}', 'done mem_sample', 300)
    send(ipc, 'quit', 'quit', 30)
    proc.wait(timeout=30)
    shutil.rmtree(run_dir, ignore_errors=True)
    print(f'{out}: {frames} frames from DUSA sample {rel}')


def compare(dusa, down, lead, runs):
    _, d = dusa_session(dusa)
    rel = down - lead
    dg, ug = GAMES['dusa'], GAMES['ult']

    def rec(data, g, k):
        o = k * g['size']
        get = lambda off: struct.unpack_from('>i', data, o + off)[0]
        return (struct.unpack_from('>H', data, o + g['gear'])[0] + 1, get(g['kmh']),
                angle(get(g['heading']) - get(g['travel'])) * 360 / 65536,
                get(g['pos']) / 65536, get(g['pos'] + 8) / 65536)
    datas = [open(r, 'rb').read() for r in runs]
    n = min(len(c) // ug['size'] for c in datas)
    dusa_rec = lambda k: rec(d[rel * dg['size']:], dg, k)

    def line(label, at):
        pk = max(range(n), key=lambda k: abs(at(k)[2]))
        lo = min(range(n), key=lambda k: at(k)[1])
        gears = [(at(k)[0], k) for k in range(n) if k == 0 or at(k)[0] != at(k - 1)[0]]
        print(f'{label:>16}: peak slide {at(pk)[2]:6.1f} at {pk:3d}, lowest {at(lo)[1]} km/h at {lo:3d}, '
              f'gears {" ".join(f"{g}@{k}" for g, k in gears)}')
    line('DUSA', dusa_rec)
    for r, c in zip(runs, datas):
        at = lambda k, c=c: rec(c, ug, k)
        line(os.path.basename(r)[:-4], at)
        apart = [((at(k)[3] - dusa_rec(k)[3]) ** 2 + (at(k)[4] - dusa_rec(k)[4]) ** 2) ** 0.5 for k in range(n)]
        print(f'{"":>16}  paths apart {apart[min(60, n - 1)]:.1f} at 60, {apart[min(120, n - 1)]:.1f} at 120, '
              f'{apart[min(180, n - 1)]:.1f} at 180')


def main():
    args = sys.argv[1:]
    if len(args) in (7, 8, 9) and args[0] == 'replay':
        replay(args[1], args[2], int(args[3]), int(args[4]), int(args[5]), args[6],
               *([int(args[7])] if len(args) > 7 else []), *(args[8:9]))
        return
    if len(args) >= 5 and args[0] == 'compare':
        compare(args[1], int(args[2]), int(args[3]), args[4:])
        return
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
