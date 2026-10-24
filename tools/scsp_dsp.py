"""SCSP DSP programs: list one, and measure what it does to each input.

usage: scsp_dsp.py list <image> [offset]
       scsp_dsp.py response <image> [offset] <rbl> <input> [seconds]
  <image> holds the DSP registers as the sound CPU loads them: COEF (64
  words) at +0, MADRS (32 words) at +0x80, MPRO (128 x 4 words) at +0x100,
  i.e. SCSP 0x700-0xBFF (DUSA copies [$3018] entry 0 there whole).
  list: one line per step that does something.
  response: an impulse into MIXS <input> (0-15), or EXTS 16/17, and the
  energy and decay of each EFREG output it reaches, from a direct run of the
  program (the SCSP's per-sample steps, from MAME's scspdsp.cpp; the 16-bit
  float memory format is kept as plain integers). rbl: ring buffer length
  0-3 (8K-64K words, common register 0x402 bits 7-8).
"""
import struct
import sys

import numpy as np


def load(path, off=0):
    d = open(path, 'rb').read()[off:off + 0x500]
    coef = [((w >> 3) - 0x2000 if w & 0x8000 else w >> 3) for w in struct.unpack_from('>64H', d, 0)]
    madrs = list(struct.unpack_from('>32H', d, 0x80))
    mpro = [struct.unpack_from('>4H', d, 0x100 + 8 * s) for s in range(128)]
    return coef, madrs, mpro


def fields(w):
    return {
        'TRA': (w[0] >> 8) & 0x7F, 'TWT': (w[0] >> 7) & 1, 'TWA': w[0] & 0x7F,
        'XSEL': (w[1] >> 15) & 1, 'YSEL': (w[1] >> 13) & 3, 'IRA': (w[1] >> 6) & 0x3F,
        'IWT': (w[1] >> 5) & 1, 'IWA': w[1] & 0x1F,
        'TABLE': (w[2] >> 15) & 1, 'MWT': (w[2] >> 14) & 1, 'MRD': (w[2] >> 13) & 1,
        'EWT': (w[2] >> 12) & 1, 'EWA': (w[2] >> 8) & 0xF, 'ADRL': (w[2] >> 7) & 1,
        'FRCL': (w[2] >> 6) & 1, 'SHIFT': (w[2] >> 4) & 3, 'YRL': (w[2] >> 3) & 1,
        'NEGB': (w[2] >> 2) & 1, 'ZERO': (w[2] >> 1) & 1, 'BSEL': w[2] & 1,
        'NOFL': (w[3] >> 15) & 1, 'COEF': (w[3] >> 9) & 0x3F, 'MASA': (w[3] >> 2) & 0x1F,
        'ADREB': (w[3] >> 1) & 1, 'NXADR': w[3] & 1,
    }


def ira_name(i):
    return f'MEMS{i}' if i < 0x20 else f'MIXS{i - 0x20}' if i < 0x30 else f'EXTS{i - 0x30}'


def listing(coef, madrs, mpro):
    for s, w in enumerate(mpro):
        if not any(w):
            continue
        f = fields(w)
        x = ira_name(f['IRA']) if f['XSEL'] else f'T[{f["TRA"]}]'
        y = ['FRC', f'C{f["COEF"]}={coef[f["COEF"]] / 4096:+.3f}', 'Yhi', 'Ylo'][f['YSEL']]
        b = '0' if f['ZERO'] else ('ACC' if f['BSEL'] else f'T[{f["TRA"]}]')
        parts = [f'{s:3d}: ACC = {x} * {y} {"-" if f["NEGB"] else "+"} {b}']
        if f['TWT']:
            parts.append(f'T[{f["TWA"]}]=sh')
        if f['MRD'] or f['MWT']:
            addr = f'M[{madrs[f["MASA"]]:04X}{"" if f["TABLE"] else "+DEC"}{"+ADRS" if f["ADREB"] else ""}{"+1" if f["NXADR"] else ""}]'
            if f['MRD']:
                parts.append(f'read {addr}')
            if f['MWT']:
                parts.append(f'{addr}=sh')
        if f['IWT']:
            parts.append(f'MEMS{f["IWA"]}=mem')
        if f['EWT']:
            parts.append(f'EFREG{f["EWA"]}+=sh')
        if f['YRL']:
            parts.append(f'Y={ira_name(f["IRA"])}')
        if f['FRCL']:
            parts.append('FRC=sh')
        if f['ADRL']:
            parts.append('ADRS=sh')
        print('  '.join(parts) + (f'  (in {ira_name(f["IRA"])})' if not f['XSEL'] and not f['YRL'] and f['IRA'] else ''))


def run(coef, madrs, mpro, rbl, inject, samples):
    """Impulse into one input; returns EFREG outputs [16][samples] (floats)."""
    mask = (0x2000 << rbl) - 1
    ram = np.zeros(mask + 1)
    temp = np.zeros(128)
    mems = np.zeros(32)
    efreg_out = np.zeros((16, samples))
    steps = [(s, fields(w)) for s, w in enumerate(mpro) if any(w)]
    last = steps[-1][0] if steps else -1
    steps = [(s, f) for s, f in steps if s <= last]
    acc = 0.0
    frc = y = adrs = 0.0
    memval = 0.0
    dec = 0
    for t in range(samples):
        mixs = np.zeros(18)
        if t == 0:
            mixs[inject] = 1.0
        efreg = np.zeros(16)
        for s, f in steps:
            ira = f['IRA']
            inputs = mems[ira] if ira < 0x20 else mixs[ira - 0x20] if ira < 0x32 else 0.0
            if f['IWT']:
                mems[f['IWA']] = memval
            if f['ZERO']:
                b = 0.0
            else:
                b = acc if f['BSEL'] else temp[(f['TRA'] + dec) & 0x7F]
                if f['NEGB']:
                    b = -b
            x = inputs if f['XSEL'] else temp[(f['TRA'] + dec) & 0x7F]
            yv = [frc, coef[f['COEF']] / 4096, y, y][f['YSEL']]
            if f['YRL']:
                y = inputs
            shifted = acc * (2 if f['SHIFT'] in (1, 2) else 1)
            if f['SHIFT'] in (0, 1):
                shifted = max(-1.0, min(1.0, shifted))
            acc = x * yv + b
            if f['TWT']:
                temp[(f['TWA'] + dec) & 0x7F] = shifted
            if f['FRCL']:
                frc = shifted
            if f['MRD'] or f['MWT']:
                a = madrs[f['MASA']]
                if not f['TABLE']:
                    a += dec
                if f['ADREB']:
                    a += int(adrs)
                if f['NXADR']:
                    a += 1
                a &= mask
                if f['MRD']:
                    memval = ram[a]
                if f['MWT']:
                    ram[a] = shifted
            if f['ADRL']:
                adrs = 0.0
            if f['EWT']:
                efreg[f['EWA']] += shifted
        efreg_out[:, t] = efreg
        dec = (dec - 1) & 0xFFFF
    return efreg_out


def response(coef, madrs, mpro, rbl, inject, seconds):
    rate = 44100
    out = run(coef, madrs, mpro, rbl, inject, int(rate * seconds))
    for e in range(16):
        o = out[e]
        energy = (o ** 2).sum()
        if energy < 1e-12:
            continue
        cum = np.cumsum((o ** 2)[::-1])[::-1] / energy
        t60 = np.argmax(cum < 1e-6) / rate if (cum < 1e-6).any() else None
        first = np.argmax(np.abs(o) > 1e-6 * np.abs(o).max()) / rate
        print(f'  EFREG{e}: energy {10 * np.log10(energy):+6.1f} dB, first at {first * 1000:6.1f} ms, '
              f'peak {o.max():+.3f}/{o.min():+.3f}, -60 dB at {t60 if t60 is None else round(t60, 3)} s')
    return out


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    off = int(args.pop(0), 16) if args and args[0].startswith('0x') else 0
    prog = load(path, off)
    if cmd == 'list':
        listing(*prog)
    elif cmd == 'response':
        rbl, inject = int(args[0]), int(args[1])
        response(*prog, rbl, inject, float(args[2]) if len(args) > 2 else 1.0)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
