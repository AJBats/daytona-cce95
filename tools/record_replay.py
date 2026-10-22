"""Run an input replay in a Mednafen instance started with -qtrecord.

Screenshots taken between frame steps let the emulator run extra frames that
the input playback doesn't count, so replays desync. Instead, launch a
separate Mednafen with `-qtrecord <file.mov> --automation <ipc>` and drive
it here: every emulated frame lands in the movie.

usage: record_replay.py <ipc_dir> <state.mcs> <script.txt> <frames> [hotpatch.txt]
  hotpatch.txt: tools/hotpatch.py output, installed before the state loads.
"""
import json
import os
import sys
import time

seq = 1000


def send(ipc, cmd, keyword, timeout=60):
    global seq
    seq += 1
    action, ack = os.path.join(ipc, 'mednafen_action.txt'), os.path.join(ipc, 'mednafen_ack.txt')
    try:
        last = open(ack).read().strip()
    except OSError:
        last = None
    with open(action + '.tmp', 'w', newline='\n') as f:
        f.write(f'# {seq}{"." * (seq % 16)}\n{cmd}\n')
    os.replace(action + '.tmp', action)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            content = open(ack).read().strip()
        except OSError:
            content = None
        if content and content != last:
            if keyword in content:
                return content
            if content.startswith('error'):
                sys.exit(f'{cmd[:60]}: {content}')
        time.sleep(0.01)
    sys.exit(f'{cmd[:60]}: timed out')


def main():
    ipc, state, script, frames = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    once = []
    if len(sys.argv) > 5:
        for line in open(sys.argv[5]):
            trig, pokes = line.split(' ', 1)
            if trig == 'once':
                once = pokes.split()
                continue
            parts = [f'poke_breakpoint {trig[2:]} {len(json.loads(pokes))}']
            parts += [f'{p["addr"][2:]}:{p["value"][2:]}:{p["width"]}' for p in json.loads(pokes)]
            print(send(ipc, ' '.join(parts), 'ok poke_breakpoint'))
    print(send(ipc, f'load_state {os.path.abspath(state)}', 'ok load_state'))
    for word in once:
        addr, data = word.split(':')
        send(ipc, f'poke {addr} ' + ' '.join(data[i:i + 2] for i in range(0, len(data), 2)), 'ok poke')
    print(send(ipc, f'input_playback {os.path.abspath(script)}', 'ok input_playback'))
    print(send(ipc, f'frame_advance {frames}', 'done frame_advance', 600))


if __name__ == '__main__':
    main()
