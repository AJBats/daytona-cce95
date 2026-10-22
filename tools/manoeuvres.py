"""Scripted manoeuvres for the level back straight (Three Seven, after turn 1).

Run from build/states/dusa_bs_7s.mcs and cce_p*_bs_7s.mcs (187 km/h, 3rd):
load, advance 2 frames, start the script, sample 150 frames. Writes one
input script per game (DUSA: gas C, brake B; CCE: gas B, brake C).

usage: manoeuvres.py <outdir>
"""
import os
import sys

MANOEUVRES = {
    'flick': [(0, 'PRESS', 'GAS'), (0, 'PRESS', 'LEFT'), (30, 'RELEASE', 'LEFT')],
    'weave': [(0, 'PRESS', 'GAS'), (0, 'PRESS', 'LEFT'), (20, 'RELEASE', 'LEFT'),
              (20, 'PRESS', 'RIGHT'), (45, 'RELEASE', 'RIGHT')],
    'lift': [(0, 'PRESS', 'LEFT'), (60, 'RELEASE', 'LEFT')],
    'brakeslide': [(0, 'PRESS', 'BRAKE'), (3, 'PRESS', 'LEFT'), (18, 'RELEASE', 'BRAKE'),
                   (18, 'PRESS', 'GAS'), (45, 'RELEASE', 'LEFT'), (51, 'PRESS', 'RIGHT'),
                   (75, 'RELEASE', 'RIGHT')],
    # gentle set: stays off the walls for 1.5 s
    'tap': [(0, 'PRESS', 'GAS'), (0, 'PRESS', 'LEFT'), (12, 'RELEASE', 'LEFT')],
    'tap2': [(0, 'PRESS', 'GAS'), (0, 'PRESS', 'LEFT'), (18, 'RELEASE', 'LEFT'),
             (18, 'PRESS', 'RIGHT'), (30, 'RELEASE', 'RIGHT')],
    'bslide': [(0, 'PRESS', 'BRAKE'), (2, 'PRESS', 'LEFT'), (12, 'RELEASE', 'BRAKE'),
               (12, 'PRESS', 'GAS'), (24, 'RELEASE', 'LEFT'), (30, 'PRESS', 'RIGHT'),
               (42, 'RELEASE', 'RIGHT')],
    # braking, straight line (inputs after frame 0: the playback tool's
    # frame-0 event lands a frame late in CCE)
    'btap': [(6, 'PRESS', 'BRAKE'), (18, 'RELEASE', 'BRAKE')],
    'bhold': [(6, 'PRESS', 'BRAKE'), (66, 'RELEASE', 'BRAKE')],
}
BUTTONS = {'dusa': {'GAS': 'C', 'BRAKE': 'B'}, 'cce': {'GAS': 'B', 'BRAKE': 'C'}}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, events in MANOEUVRES.items():
        for game, buttons in BUTTONS.items():
            with open(os.path.join(out, f'{name}_{game}.txt'), 'w') as f:
                f.write(f'# back straight manoeuvre {name} ({game} buttons)\n')
                for frame, kind, button in events:
                    f.write(f'frame={frame} {kind} {buttons.get(button, button)}\n')


if __name__ == '__main__':
    main()
