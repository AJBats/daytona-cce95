"""Sound lab: hear one part of the car sound at a time, live or in a WAV.

usage:
  soundlab.py live dusa|cce [mix...]
      Install the lab in the MCP-run Mednafen (build/mcp_ipc), right after a
      race state loads; reads the original values and keeps them in
      build/soundlab_<game>.json.
  soundlab.py mix dusa|cce [mix...]
      Change the mix of the lab installed with `live`.
  soundlab.py record dusa|cce <state> <script> <frames> <out.wav> [mix...]
      Start a separate Mednafen (sound on at volume 0: it runs in real time,
      silently), load the state, install the lab, play the input script for
      <frames> frames, and write <out.wav> (Mednafen won't overwrite it) and
      <out>.trace.bin, a per-frame sample of the car sound inputs (DUSA: car
      struct 06078900, 0x100 bytes; CCE: rpm, throttle, km/h, gear longs at
      25A06F00).

mix: [music] [solo <part>...] [mute <part>...]
  DUSA parts: L0-L5 (engine layers), slip, brake (channels), peel, tone10,
    crowd, narrator, sfx (tones); crowd, narrator and sfx are off unless named.
  CCE parts: L0-L5 (engine layers), sfx (tone banks 1-2); sfx is off unless named.
  Groups: idle (L4 L5), engine (L0-L5). Music is off unless named.

How it works (docs/sound_lab.md): the debugger only writes work RAM, so a
code cave in WRAM-L runs before the game's car-tick sound routine and writes
each (address, byte) pair of a table (sound RAM and SCSP), every tick.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import record_replay  # noqa: E402

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUILD = os.path.join(PROJ, 'build')
MCP_IPC = os.path.join(BUILD, 'mcp_ipc')
EXE = os.path.join(PROJ, 'tools', 'mednafen', 'mednafen_gcc494.exe')
CUES = {
    'dusa': os.path.join(PROJ, 'external_resources', 'Daytona USA (USA)', 'Daytona USA (USA).cue'),
    'cce': os.path.join(BUILD, 'disc', 'cce.cue'),
}


def cave(table, routine):
    """mov.l table,r0 / loop: (addr, byte) pairs until addr 0 / jmp routine
    (assembled from docs/sound_lab.md's cave; position-independent)."""
    return (bytes.fromhex('d0046106211889026206affa2120d002402b0009')
            + struct.pack('>II', table, routine))


GAMES = {
    'dusa': {
        'cave': 0x0029F000, 'table': 0x0029F100, 'routine': 0x0602F7EA,
        'hooks': [0x06009254, 0x0600DFAC],
        'setup': [
            'poke_breakpoint 0602F7EA 2 0605DF94:0:32 0605DF98:0:32',  # resend engine and slip
            'poke 0600930E 00 09',                                      # timer
            'poke 0600D9F0 00 09', 'poke 0600DB80 00 09', 'poke 0600DB92 00 09',  # laps
        ],
        'laps': (0x06063F24, 0x06078B1C),       # count and car +0x21C: at least 1
        'music': [(0x25B00217, 0x1F), (0x25B00237, 0x0F)],
        'resend': [(0x25A04E07, 0xFF), (0x25A04E17, 0xFF)],
        'default_off': ['crowd', 'narrator', 'sfx'],
        'trace': (0x06078900, 0x100),
    },
    'cce': {
        'cave': 0x00210000, 'table': 0x00210100, 'routine': 0x06030AFA,
        'hooks': [0x060287B4, 0x06028C3C, 0x06034338],
        'setup': [],
        'laps': None,
        'music': [(0x25B00217, 0x1F), (0x25B00237, 0x0F)],
        'resend': [],
        'default_off': ['sfx'],
        'trace': (0x25A06F00, 0x10),
    },
}
GROUPS = {'idle': ['L4', 'L5'], 'engine': [f'L{k}' for k in range(6)]}


class Mednafen:
    def __init__(self, ipc):
        self.ipc = ipc
        record_replay.seq = int(time.time() * 100) % 100000000

    def send(self, cmd, keyword, timeout=60):
        return record_replay.send(self.ipc, cmd, keyword, timeout)

    def read(self, addr, size):
        path = os.path.join(BUILD, f'soundlab_read_{os.getpid()}.bin')
        self.send(f'dump_mem_bin {addr:08X} {size:X} {path}', 'dump_mem_bin')
        data = open(path, 'rb').read()
        os.remove(path)
        return data

    def poke(self, addr, data):
        self.send(f'poke {addr:08X} ' + ' '.join(f'{b:02X}' for b in data), 'ok poke')


def dusa_parts(m):
    """part -> [(address, original byte, byte when off)], read from sound RAM."""
    defs = m.read(0x25A04652, 0x60)
    parts = {f'L{k}': [(0x25A04652 + 12 * k, defs[12 * k], 0x80)] for k in range(6)}  # layer vmin
    parts['slip'] = [(0x25A0469E, defs[0x4C], 0x80)]
    parts['brake'] = [(0x25A046AE, defs[0x5C], 0x80)]
    tones = m.read(0x25A0322C, 61 * 16)

    def ar(ts):          # tone attack rate (tone +0xD); 0 = silent
        return [(0x25A0322C + 16 * t + 0xD, tones[16 * t + 0xD], 0x00) for t in ts]
    parts['peel'] = ar([16])                                 # wheelspin timer car +0x166
    parts['tone10'] = ar([10])                               # car +0xB8 = 44
    parts['crowd'] = ar([17])                                # Three Seven grandstand
    parts['narrator'] = ar([t for t in range(25, 61) if t != 36])   # program 3
    parts['sfx'] = ar([6, 7, 8, 9, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 24, 36])
    return parts


def cce_parts(m):
    tables = m.read(0x25A7F000, 6 * 0x80)
    parts = {f'L{k}': [(0x25A7F007 + 0x80 * k + i, tables[0x80 * k + 7 + i], 0xFF) for i in range(35)]
             for k in range(6)}                              # level by 256 rpm; FF = silent
    areas = m.read(0x25A00500, 0x80)
    sfx = []
    for e in range(0, len(areas), 8):                        # area map: type << 4 | id, address
        if areas[e] == 0xFF:
            break
        addr = struct.unpack_from('>I', areas, e)[0] & 0xFFFFFF
        if areas[e] >> 4 == 0 and areas[e] & 0xF:            # tone banks 1, 2, ...: not the engine
            head = m.read(0x25A00000 + addr, 0x40)
            voices = (struct.unpack_from('>H', head, 0)[0] - 8) // 2
            offs = struct.unpack_from(f'>{voices}H', m.read(0x25A00000 + addr + 8, 2 * voices))
            for o in offs:
                v = 0x25A00000 + addr + o
                layers = m.read(v + 2, 1)[0] + 1
                recs = m.read(v + 4, 0x20 * layers)
                for k in range(layers):
                    for b in (23, 24):                       # IMXL, DISDL/DIPAN
                        sfx.append((v + 4 + 0x20 * k + b, recs[0x20 * k + b], 0x00))
    parts['sfx'] = sfx
    return parts


def table(game, parts, music_on, mix):
    g = GAMES[game]
    mode, names = None, []
    for a in mix:
        if a in ('solo', 'mute'):
            mode = a
        elif a != 'music':
            names.append(a)
    expanded = []
    for n in names:
        expanded += GROUPS.get(n, [n])
    for n in expanded:
        if n not in parts:
            sys.exit(f'unknown part {n} (parts: {" ".join(parts)})')
    if mode == 'solo':
        off = [p for p in parts if p not in expanded]
    else:
        off = [p for p in g['default_off'] if p not in expanded] + (expanded if mode == 'mute' else [])
    pairs = [] if music_on else list(g['music'])
    pairs += [(a, mute if p in off else on) for p in parts for a, on, mute in parts[p]]
    pairs += g['resend']
    data = b''.join(struct.pack('>II', a, v) for a, v in pairs) + bytes(8)
    return data, off


def install(m, game, mix):
    """Read the originals, then poke the table, the cave, the setup and the hooks."""
    g = GAMES[game]
    parts = dusa_parts(m) if game == 'dusa' else cce_parts(m)
    data, off = table(game, parts, 'music' in mix, mix)
    m.poke(g['table'], data)
    m.poke(g['cave'], cave(g['table'], g['routine']))
    for c in g['setup']:
        m.send(c, 'ok poke_breakpoint' if c.startswith('poke_breakpoint') else 'ok poke')
    if g['laps']:
        count = struct.unpack('>I', m.read(g['laps'][0], 4))[0]
        for a in g['laps']:
            m.poke(a, struct.pack('>I', max(count, 1)))
    for h in g['hooks']:
        m.poke(h, struct.pack('>I', g['cave']))
    return parts, off


def mednafen_home():
    """A home for recording: the user's settings and firmware, sound volume 0."""
    home = os.path.join(BUILD, 'soundlab_home')
    user = os.path.expandvars(os.path.join('%USERPROFILE%', '.mednafen'))
    os.makedirs(os.path.join(home, 'firmware'), exist_ok=True)
    for f in os.listdir(os.path.join(user, 'firmware')):
        shutil.copy(os.path.join(user, 'firmware', f), os.path.join(home, 'firmware'))
    # bytes, split on \n only: the cfg holds UTF-8 names that str.splitlines breaks apart
    cfg = open(os.path.join(user, 'mednafen.cfg'), 'rb').read().split(b'\n')
    cfg = [b'sound.volume 0' if line.startswith(b'sound.volume ') else line for line in cfg]
    open(os.path.join(home, 'mednafen.cfg'), 'wb').write(b'\n'.join(cfg))
    return home


def record(game, state, script, frames, out, mix):
    out = os.path.abspath(out)
    if os.path.exists(out):
        sys.exit(f'{out} exists (Mednafen will not overwrite it)')
    ipc = os.path.join(BUILD, f'soundlab_ipc_{os.getpid()}')
    os.makedirs(ipc)
    env = dict(os.environ, MEDNAFEN_HOME=mednafen_home(), MEDNAFEN_ALLOWMULTI='1')
    proc = subprocess.Popen([EXE, '--sound', '1', '-soundrecord', out, '--automation', ipc, CUES[game]],
                            env=env, cwd=PROJ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ack = os.path.join(ipc, 'mednafen_ack.txt')
    deadline = time.time() + 60
    while not (os.path.exists(ack) and 'ready' in open(ack).read()):
        if proc.poll() is not None or time.time() > deadline:
            sys.exit('Mednafen did not start')
        time.sleep(0.2)
    m = Mednafen(ipc)
    m.send(f'load_state {os.path.abspath(state)}', 'ok load_state')
    parts, off = install(m, game, mix)
    m.send(f'input_playback {os.path.abspath(script)}', 'ok input_playback')
    addr, size = GAMES[game]['trace']
    m.send(f'mem_sample {addr:08X} {size:X} {frames} {out[:-4]}.trace.bin', 'done mem_sample',
           int(frames) / 30 + 60)
    m.send('quit', 'quit', 10)
    proc.wait(timeout=30)
    shutil.rmtree(ipc)
    print(f'{os.path.basename(out)}: off {" ".join(off) or "nothing"}; {os.path.getsize(out)} bytes')


def main():
    cmd, game = sys.argv[1], sys.argv[2]
    if game not in GAMES:
        sys.exit(__doc__)
    saved = os.path.join(BUILD, f'soundlab_{game}.json')
    if cmd == 'live':
        parts, off = install(Mednafen(MCP_IPC), game, sys.argv[3:])
        json.dump(parts, open(saved, 'w'))
        print('off:', ' '.join(off) or 'nothing')
    elif cmd == 'mix':
        parts = {p: [tuple(e) for e in v] for p, v in json.load(open(saved)).items()}
        data, off = table(game, parts, 'music' in sys.argv[3:], sys.argv[3:])
        Mednafen(MCP_IPC).poke(GAMES[game]['table'], data)
        print('off:', ' '.join(off) or 'nothing')
    elif cmd == 'record':
        record(game, *sys.argv[3:7], sys.argv[7:])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
