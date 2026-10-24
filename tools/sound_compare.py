"""Compare DUSA and CCE95 recordings of the same car-sound part.

usage: sound_compare.py <wav dir> [part ...]
  For each part (default L0 L1 L2 L3 idle engine) reads dusa_<part>.wav and
  cce95_<part>.wav with their .trace.bin (tools/soundlab.py record) and writes
  compare_<part>.png (spectra by engine value v, side by side) and
  spectrogram_<part>.png, then prints a table: level, spectral centroid and
  strongest low peak per v band, DUSA vs CCE95. A part written
  <cce part>:<dusa part> compares cce95_<cce part> with dusa_<dusa part>, for
  a CCE95 variant (e.g. engine_dry:engine).

v is the engine value DUSA's sound driver uses, (rpm - 1800) x 128 / 5300
clamped to 1-127, from each game's own rpm (DUSA car +0xE4, CCE95 the rpm it
sends the driver); CCE95's engine tables are DUSA's sampled by that same v.
"""
import os
import struct
import sys
import wave

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RATE = 48000
SPF = RATE / 59.8261            # samples per NTSC Saturn frame
N = 4096                         # FFT window
BANDS = [(1, 1), (2, 16), (17, 32), (33, 48), (49, 64), (65, 80), (81, 96), (97, 112), (113, 127)]
FREQS = np.fft.rfftfreq(N, 1 / RATE)
LAG = 1                          # frames from the car tick to the sound
SETTLE = 30                      # frames before the lab's mix has taken hold


def v_of(rpm):
    rpm = np.clip(rpm, 1800, 8500)
    return np.clip((rpm - 1800) * 128 // 5300, 1, 127)


def load(path, game):
    w = wave.open(path)
    a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(float)
    t = open(path[:-4] + '.trace.bin', 'rb').read()
    if game == 'dusa':
        rpm = np.array([struct.unpack_from('>i', t, 0x100 * f + 0xE4)[0] for f in range(len(t) // 0x100)])
    else:
        rpm = np.array([struct.unpack_from('>i', t, 0x10 * f)[0] for f in range(len(t) // 0x10)])
    base = len(a) - len(rpm) * SPF          # the samples before the first traced frame
    return a, rpm, base


def frame_sample(base, f):
    return int(base + (f + LAG) * SPF)


def band_spectra(a, rpm, base):
    mono = a.mean(1)
    v = v_of(rpm)
    win = np.hanning(N)
    out = []
    for lo, hi in BANDS:
        acc, n, lvl, lr = np.zeros(len(FREQS)), 0, [], []
        for f in range(SETTLE, len(v) - 3):
            if not all(lo <= x <= hi for x in v[f - 3:f + 4]):
                continue
            s = frame_sample(base, f) - N // 2
            if s < 0 or s + N > len(mono):
                continue
            seg = mono[s:s + N]
            acc += np.abs(np.fft.rfft(seg * win)) ** 2
            lvl.append((seg ** 2).mean())
            st = a[s:s + N]
            lr.append(((st[:, 0] ** 2).mean() + 1e-9) / ((st[:, 1] ** 2).mean() + 1e-9))
            n += 1
        if n == 0:
            out.append(None)
            continue
        p = acc / n
        band = (FREQS > 20) & (FREQS < 12000)
        cent = (FREQS[band] * p[band]).sum() / p[band].sum()
        low = (FREQS > 20) & (FREQS < 1000)
        peak = FREQS[low][np.argmax(p[low])]
        out.append({'n': n, 'p': p, 'db': 10 * np.log10(np.mean(lvl) + 1e-9), 'cent': cent, 'peak': peak,
                    'lr_db': 10 * np.log10(np.mean(lr))})
    return out


def spectrogram(ax, a, rpm, base, title):
    mono = a.mean(1)
    hop = 1024
    win = np.hanning(N)
    cols = [np.abs(np.fft.rfft(mono[s:s + N] * win)) ** 2 for s in range(0, len(mono) - N, hop)]
    img = 10 * np.log10(np.array(cols).T + 1e-3)
    keep = FREQS < 4000
    t = np.arange(img.shape[1]) * hop / RATE
    ax.imshow(img[keep], origin='lower', aspect='auto', extent=[t[0], t[-1], 0, 4000],
              vmin=img[keep].max() - 70, vmax=img[keep].max(), cmap='magma')
    ft = (base + (np.arange(len(rpm)) + LAG) * SPF) / RATE
    ax2 = ax.twinx()
    ax2.plot(ft, rpm, color='cyan', lw=0.8)
    ax2.set_ylim(0, 11000)
    ax2.set_ylabel('rpm', color='cyan')
    ax.set_ylabel('Hz')
    ax.set_title(title)


def compare(wavdir, spec):
    part, _, dusa_part = spec.partition(':')
    d = load(os.path.join(wavdir, f'dusa_{dusa_part or part}.wav'), 'dusa')
    c = load(os.path.join(wavdir, f'cce95_{part}.wav'), 'cce')
    sd, sc = band_spectra(*d), band_spectra(*c)

    fig, axes = plt.subplots(3, 3, figsize=(15, 11), sharex=True)
    for ax, (lo, hi), x, y in zip(axes.flat, BANDS, sd, sc):
        for s, label, col in ((x, 'DUSA', 'tab:blue'), (y, 'CCE95', 'tab:orange')):
            if s:
                ax.semilogx(FREQS[1:], 10 * np.log10(s['p'][1:] + 1e-3), label=f'{label} ({s["n"]} fr)',
                            color=col, lw=0.8)
        ax.set_title(f'v {lo}-{hi}' if lo != hi else 'v 1 (idle)')
        ax.set_xlim(20, 12000)
        ax.grid(True, which='both', alpha=0.3)
        ax.legend(fontsize=7)
    fig.suptitle(f'{part}: average spectrum by engine value v (dB)')
    fig.tight_layout()
    fig.savefig(os.path.join(wavdir, f'compare_{part}.png'), dpi=90)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    spectrogram(axes[0], *d, f'DUSA {part}')
    spectrogram(axes[1], *c, f'CCE95 {part}')
    axes[1].set_xlabel('s')
    fig.tight_layout()
    fig.savefig(os.path.join(wavdir, f'spectrogram_{part}.png'), dpi=80)
    plt.close(fig)

    print(f'\n{part}      frames      level dB      centroid Hz      low peak Hz     L/R dB')
    for (lo, hi), x, y in zip(BANDS, sd, sc):
        name = f'v {lo}-{hi}' if lo != hi else 'v 1'
        if not x or not y:
            print(f'  {name:9s} DUSA {x["n"] if x else 0}, CCE95 {y["n"] if y else 0} frames: not both')
            continue
        print(f'  {name:9s} {x["n"]:4d}/{y["n"]:<4d}  {x["db"]:5.1f}/{y["db"]:5.1f} ({y["db"] - x["db"]:+5.1f})'
              f'  {x["cent"]:6.0f}/{y["cent"]:<6.0f}  {x["peak"]:5.0f}/{y["peak"]:<5.0f}'
              f'  {x["lr_db"]:+4.1f}/{y["lr_db"]:+4.1f}')


def main():
    wavdir = sys.argv[1]
    for part in sys.argv[2:] or ['L0', 'L1', 'L2', 'L3', 'idle', 'engine']:
        compare(wavdir, part)


if __name__ == '__main__':
    main()
