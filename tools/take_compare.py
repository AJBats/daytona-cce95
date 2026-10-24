"""Compare DUSA and CCE95 recordings of the player's own drives, event by event.

usage: take_compare.py <wav dir> <dusa take.txt> <cce take.txt> [part ...]
  Reads dusa_<part>.wav / cce95_<part>.wav (+ .trace.bin) recorded from the
  two takes (tools/soundlab.py take / record; default parts engine L0 L1 L2
  L3 idle) and lines the drives up on the events both share: the launch
  (the throttle press held longest), the lift, the brake after it, and the
  stop (speed 0). Between events, time is stretched linearly, so the drag
  and the stop line up even though the two runs differ in length.
  Writes take_<part>.png: rpm, level and spectral centroid over the aligned
  drive, and the two spectrograms; prints level and centroid per phase.
"""
import os
import struct
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from sound_compare import LAG, RATE, SPF, load  # noqa: E402

GAS = {'dusa': 'C', 'cce': 'B'}
BRAKE = {'dusa': {'B'}, 'cce': {'A', 'C'}}
N = 2048


def events(script, game, speed):
    """Trace frames of the launch, lift, brake and stop (a trace frame is a
    frame of the take: the replay is shifted to match it)."""
    pressed, held, brakes, starts = {}, [], [], []
    for line in open(script):
        if not line.startswith('frame='):
            continue
        f, kind, button = line.split()
        f = int(f[6:])
        if kind == 'PRESS':
            pressed[button] = f
            if button in BRAKE[game]:
                brakes.append(f)
            elif button == 'START':
                starts.append(f)
        elif button in pressed:
            start = pressed.pop(button)
            held.append((f - start, start, f, button))
    _, launch, lift, _ = max(h for h in held if h[3] == GAS[game])
    brake = min(b for b in brakes if b >= lift)
    stop = next(f for f in range(brake, len(speed)) if speed[f] == 0)
    # the player's closing bookend: in DUSA the lab's music comes back while paused
    end = min([p for p in starts if p > stop] + [len(speed)])
    return {'launch': launch, 'lift': lift, 'brake': brake, 'stop': stop, 'end': end}


def features(a, rpm, base):
    mono = a.mean(1)
    win = np.hanning(N)
    freqs = np.fft.rfftfreq(N, 1 / RATE)
    lvl, cent = [], []
    for f in range(len(rpm)):
        s = int(base + (f + LAG) * SPF) - N // 2
        seg = mono[max(s, 0):max(s, 0) + N]
        if len(seg) < N:
            lvl.append(np.nan)
            cent.append(np.nan)
            continue
        p = np.abs(np.fft.rfft(seg * win)) ** 2
        lvl.append(10 * np.log10((seg ** 2).mean() + 1e-9))
        band = (freqs > 20) & (freqs < 12000)
        cent.append((freqs[band] * p[band]).sum() / (p[band].sum() + 1e-9))
    return np.array(lvl), np.array(cent)


def warp(ev, frames):
    """Frame -> aligned time: before launch in seconds from launch (negative),
    launch..lift 0..10, lift..brake 10..11, brake..stop 11..15, after stop 15+ s."""
    marks = [(ev['launch'], 0.0), (ev['lift'], 10.0), (ev['brake'], 11.0), (ev['stop'], 15.0)]
    out = []
    for f in frames:
        if f <= marks[0][0]:
            out.append((f - marks[0][0]) / 59.83)
        elif f >= marks[-1][0]:
            out.append(15.0 + (f - marks[-1][0]) / 59.83)
        else:
            for (f0, t0), (f1, t1) in zip(marks, marks[1:]):
                if f0 <= f <= f1:
                    out.append(t0 + (t1 - t0) * (f - f0) / max(f1 - f0, 1))
                    break
    return np.array(out)


def speed_of(path, game):
    t = open(path[:-4] + '.trace.bin', 'rb').read()
    if game == 'dusa':
        return [struct.unpack_from('>i', t, 0x100 * f + 0x0C)[0] for f in range(len(t) // 0x100)]
    return [struct.unpack_from('>i', t, 0x10 * f + 8)[0] for f in range(len(t) // 0x10)]


def compare(wavdir, takes, part):
    runs = {}
    for game, prefix in (('dusa', 'dusa'), ('cce', 'cce95')):
        path = os.path.join(wavdir, f'{prefix}_{part}.wav')
        a, rpm, base = load(path, game)
        ev = events(takes[game], game, speed_of(path, game))
        lvl, cent = features(a, rpm, base)
        runs[game] = {'a': a, 'rpm': rpm, 'base': base, 'ev': ev, 'lvl': lvl, 'cent': cent,
                      't': warp(ev, range(len(rpm)))}

    fig, ax = plt.subplots(5, 1, figsize=(15, 16), sharex=False)
    for game, col in (('dusa', 'tab:blue'), ('cce', 'tab:orange')):
        r = runs[game]
        label = 'DUSA' if game == 'dusa' else 'CCE95'
        ax[0].plot(r['t'], r['rpm'], color=col, lw=0.8, label=label)
        ax[1].plot(r['t'], r['lvl'], color=col, lw=0.6, label=label)
        ax[2].plot(r['t'], r['cent'], color=col, lw=0.6, label=label)
    for i, (title, ylim) in enumerate((('rpm', (0, 11000)), ('level dB', None), ('spectral centroid Hz', (0, 3000)))):
        ax[i].set_title(f'{part}: {title} (launch 0, lift 10, brake 11, stop 15)')
        if ylim:
            ax[i].set_ylim(*ylim)
        ax[i].set_xlim(-3, 17)
        ax[i].grid(alpha=0.3)
        ax[i].legend()
        for x in (0, 10, 11, 15):
            ax[i].axvline(x, color='grey', lw=0.5)
    for k, game in ((3, 'dusa'), (4, 'cce')):
        r = runs[game]
        mono = r['a'].mean(1)
        hop = 1024
        win = np.hanning(N)
        starts = list(range(0, len(mono) - N, hop))
        cols = np.array([np.abs(np.fft.rfft(mono[s:s + N] * win)) ** 2 for s in starts]).T
        freqs = np.fft.rfftfreq(N, 1 / RATE)
        keep = freqs < 4000
        img = 10 * np.log10(cols[keep] + 1e-3)
        frames = [(s + N / 2 - r['base']) / SPF - LAG for s in starts]
        tt = warp(r['ev'], [min(max(int(f), 0), len(r['rpm']) - 1) for f in frames])
        ax[k].pcolormesh(tt, freqs[keep], img, shading='auto', cmap='magma', vmin=img.max() - 70, vmax=img.max())
        ax[k].set_xlim(-3, 17)
        ax[k].set_title(f'{"DUSA" if game == "dusa" else "CCE95"} {part} spectrogram (aligned time)')
        ax[k].set_ylabel('Hz')
    fig.tight_layout()
    fig.savefig(os.path.join(wavdir, f'take_{part}.png'), dpi=75)
    plt.close(fig)

    print(f'\n{part}: events DUSA {runs["dusa"]["ev"]}  CCE95 {runs["cce"]["ev"]}')
    print('  phase              level dB DUSA/CCE95 (diff)   centroid Hz DUSA/CCE95')
    # idle: the last second before launch, after CCE95's opening pause and DUSA's held brake
    for name, lo, hi in (('idle before launch', -1.0, 0.0), ('launch, 1st half', 0.0, 5.0),
                         ('drag, 2nd half', 5.0, 10.0), ('braking', 11.0, 15.0), ('stopped', 15.2, 17.0)):
        vals = []
        for game in ('dusa', 'cce'):
            r = runs[game]
            m = (r['t'] >= lo) & (r['t'] < hi) & ~np.isnan(r['lvl']) & (np.arange(len(r['t'])) < r['ev']['end'])
            vals.append((10 * np.log10(np.mean(10 ** (r['lvl'][m] / 10))) if m.any() else np.nan,
                         np.nanmean(r['cent'][m]) if m.any() else np.nan))
        (ld, cd), (lc, cc) = vals
        print(f'  {name:18s} {ld:6.1f}/{lc:6.1f} ({lc - ld:+5.1f})          {cd:6.0f}/{cc:6.0f}')


def main():
    wavdir, dusa_take, cce_take = sys.argv[1:4]
    for part in sys.argv[4:] or ['engine', 'L0', 'L1', 'L2', 'L3', 'idle']:
        compare(wavdir, {'dusa': dusa_take, 'cce': cce_take}, part)


if __name__ == '__main__':
    main()
