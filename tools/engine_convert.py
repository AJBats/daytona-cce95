"""Put DUSA's engine and tyre sounds into CCE's race sound files.

usage: engine_convert.py <dusa extracted dir> <cce extracted dir> <out dir>
  Reads DUSA's GAMED.BIN (its race sound data, loaded at sound RAM 0x3000)
  and CCE's race sound files (loaded at 0xB000): DAYTONA.SND, DAY3_1P.SND
  and DAY4_1P.SND for 1P, DAYT2P, DAY3_2P and DAY4_2P and their mono (M)
  versions for 2P; writes them under <out dir>/DAYTONA and lists them in
  PATCHED.txt. Files keep their sizes (the disc keeps the original
  directory entries).

DUSA (docs/engine_sound.md): engine definition 0 has six layers, each a
looped 8-bit sample with a TL table and a pitch table indexed by
v = (rpm - 1800) x 128 / 5300 (1..127), active for a v range. Definitions
1 and 2 are the slip and brake channels, one layer each, indexed by their
own v; the peel-out is tone 16, a one-shot (docs/tyre_sound.md).

CCE: tone bank 0 (file +0, 0xE8E6 bytes) holds only the engine voice, and
the engine tables (file +0x74000, 0x800 bytes) one 0x80-byte block per
layer: +7 level[35] and +0x3A pitch[35] by i = rpm >> 8, +0x2A an offset by
throttle level. Written here:
  bank 0     CCE's header and mixer/VL/PEG/PLFO data; voice 0 with the six
             DUSA engine layers, then slip, brake and the peel-out left and
             right (and a record that never plays, as the Sega format counts
             layers - 1); at +0x1A0 patches/tyre_sound_bank0.s, the driver
             side of the tyre sounds; then DUSA's samples. The mixer's
             EFREG4 output off.
  tables     blocks 0-5 from DUSA's engine layers sampled at rpm = i x 256
             (TL 255 outside the layer's v range), GAIN louder; blocks 6-9
             the tyre sounds by their v; throttle offsets 0xFF (no throttle
             effect, as in DUSA); blocks 10-14 empty, block 15 (2P pans)
             kept

The mix matches DUSA's as measured on the same drive in both games
(docs/sound_lab.md): CCE's DSP plays a low-passed copy of the engine on
EFREG4, which DUSA doesn't have, so that output is off. The engine still
sends to the DSP, so CCE's tunnel echo (EFREG2/3) still hears it. The tyre
sounds get the same overall lift as the engine (direct level 2 -> 5 and
TL + TYRE_TL instead of 2 -> 4 and TL - GAIN, since their TLs go down to 0);
slip and brake send to the DSP as the engine does. The peel-out sends
nothing to the DSP, as in DUSA, and so gets 3 dB less: part of the engine's
lift makes up for DUSA's DSP copy of it (PEEL_TL).

2P files (docs/two_player.md): the same engine and samples for both
players, with patches/sound_2p_bank0.s as the code and one peel-out record,
centred, which that code pans to the player's side as it does the rest. Its
engine slot plan switches one slot between layers 4 and 3 at step
SWITCH_STEP, which needs both tables silent there.

The three samples don't all fit beside the engine's: the brake sample is
stored at half its rate (it has 44 dB less above a quarter of its rate),
with its pitch words an octave down to play at the same speed. The
SCSP's linear interpolation then leaves images of it 34 dB down at 8-16
kHz that DUSA's full-rate sample doesn't have.

patches/engine_interp.s makes the driver interpolate between the 256-rpm
steps.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import m68kasm  # noqa: E402

GAMED_BASE = 0x3000
FILES = ('DAYTONA/DAYTONA.SND', 'DAYTONA/DAY3_1P.SND', 'DAYTONA/DAY4_1P.SND')
FILES_2P = ('DAYTONA/DAYT2P.SND', 'DAYTONA/DAY3_2P.SND', 'DAYTONA/DAY4_2P.SND',
            'DAYTONA/DAYT2PM.SND', 'DAYTONA/DAY3_2PM.SND', 'DAYTONA/DAY4_2PM.SND')
BANK0_SIZE = 0xE8E6
TABLES_AT, BLOCK = 0x74000, 0x80
STEPS = 35
LFO = 0x71B4                    # DUSA's engine slots: pitch + amplitude LFO
DSP_INPUT = 0x002E              # slot +0x14: CCE's engine DSP send (ISEL 5, IMXL 6)
DIRECT = 0x903C                 # slot +0x16: CCE's engine direct level 4, centre
GAIN = 9                        # TL steps of 0.375 dB: +3.4 dB, to DUSA's level
EFREG4_SDL = 4                  # bank 0 mixer byte for EFREG4 (EFSDL/EFPAN), after its mixer offset
TYRES_SRC = os.path.join(os.path.dirname(__file__), '..', 'patches', 'tyre_sound_bank0.s')
SRC_2P = os.path.join(os.path.dirname(__file__), '..', 'patches', 'sound_2p_bank0.s')
SWITCH_STEP = 18                # 2P: the slot shared by engine layers 4 (below) and 3
BANK0_AT = 0xB000
TYRE_TL = 7                     # with direct level 5: the engine's +15.4 dB over DUSA's registers
TYRE_DIRECT = {'centre': 0xA000, 'left': 0xBF00, 'right': 0xAF00}   # direct level 5, DIPAN
PEEL_LFO, PEEL_DSP = 0x5000, 0x0010     # DUSA's peel-out slots: no LFO depth, no DSP send
# The engine's lift includes DUSA's DSP copy of it; the peel-out sends nothing
# to the DSP in DUSA, so it needs 3 dB less (measured on the user's donut)
PEEL_TL = TYRE_TL + 8
# DUSA plays the peel-out from its sequences on two slots, panned left and
# right; their TL and pitch, read from DUSA's slots (Time Lap, the user's
# donut, docs/tyre_sound.md), for the onset (v 1) and the end (v 2)
PEEL = {'left': [(9, 0x79A8), (7, 0x7800)], 'right': [(9, 0x79AD), (7, 0x7803)]}


def dusa_def(gamed, n):
    """DUSA engine-channel definition n (0 engine, 1 slip, 2 brake) -> list of layer dicts."""
    L = lambda a: struct.unpack_from('>I', gamed, a - GAMED_BASE)[0]
    W = lambda a: struct.unpack_from('>H', gamed, a - GAMED_BASE)[0]
    B = lambda a: gamed[a - GAMED_BASE]
    d = L(L(0x3050) + 2 + 4 * n)
    layers = []
    for k in range(W(d) + 1):
        p = d + 4 + 12 * k
        ly = dusa_tone(gamed, W(p) & 0x3FF)
        tl, pitch = L(p + 4), L(p + 8)
        ly.update({
            'vmin': B(p + 2), 'vmax': B(p + 3),
            'tl': [B(tl + v) for v in range(128)],
            'pitch': [W(pitch + 2 * v) for v in range(128)],
        })
        layers.append(ly)
    return layers


def dusa_tone(gamed, n):
    """DUSA tone n (table at [$3000], 16 bytes each) -> sample address, loop, envelope."""
    L = lambda a: struct.unpack_from('>I', gamed, a - GAMED_BASE)[0]
    t = L(0x3000) + 16 * n
    sa, end, loop, env = L(t) & 0x7FFFF, L(t + 4), L(t + 8), L(t + 12)
    return {'sa': sa, 'lea': (end & 0x7FFFFFFF) - 1, 'lsa': loop - sa, 'looped': end >> 31, 'env': env,
            'data': gamed[sa - GAMED_BASE:sa - GAMED_BASE + (end & 0x7FFFFFFF)]}


def halve(data, lsa, lea):
    """8-bit sample, loop lsa..lea (both even), at half the rate: low-pass at
    a quarter of the rate, the loop filtered round its seam -> (data, lsa, lea)."""
    s = np.frombuffer(data, np.int8).astype(float)
    pad = 31
    k = np.arange(-pad, pad + 1)
    h = 0.46 * np.sinc(0.46 * k) * np.blackman(2 * pad + 1)    # cut-off 0.23 of the rate
    h /= h.sum()
    loop = s[lsa:lea + 1]
    attack = np.convolve(np.concatenate([np.zeros(pad), s[:lsa], loop[:pad]]), h, 'valid')
    loop = np.convolve(np.concatenate([loop[-pad:], loop, loop[:pad]]), h, 'valid')
    out = np.concatenate([attack[::2], loop[::2], loop[:4:2]])   # two samples past the loop end
    out = np.clip(np.round(out), -128, 127).astype(np.int8)
    return out.tobytes(), lsa // 2, lsa // 2 + (lea - lsa + 1) // 2 - 1


def octave_down(w):
    """DUSA slot pitch word (OCT << 11 | FNS) an octave lower: the same sound
    from a sample at half the rate."""
    return (w - 0x0800) & 0x7FFF


def dusa_v(rpm):
    """DUSA 0602F7EA: engine value sent to the sound driver."""
    rpm = min(max(rpm, 1800), 8500)
    return min(max((rpm - 1800) * 128 // 5300, 1), 127)


def cce_pitch(w):
    """DUSA slot pitch word (OCT << 11 | FNS) -> CCE table word (0x2000 + OCT x 0x400 + FNS)."""
    octave = (w >> 11) & 0xF
    if octave & 8:
        octave -= 16
    return 0x2000 + octave * 0x400 + (w & 0x3FF)


def tyre_layers(gamed, two_player=False):
    """DUSA's slip, brake and peel-out as layers of CCE's engine voice: sample,
    record values and, by v, (TL, DUSA pitch word) for the table block. 2P:
    one peel-out, centred (the code pans it), one voice to each side as in 1P."""
    slip, brake = dusa_def(gamed, 1)[0], dusa_def(gamed, 2)[0]
    brake['stored'], brake['lsa'], brake['lea'] = halve(brake['data'], brake['lsa'], brake['lea'])
    brake['pitch'] = [octave_down(w) for w in brake['pitch']]
    out = []
    for ly in (slip, brake):    # v 1-7 (slip), v 1 (brake): DUSA's TL and pitch by v
        out.append(dict(ly, lfo=LFO, dsp=DSP_INPUT, direct=TYRE_DIRECT['centre'],
                        by_v={v: (ly['tl'][v] + TYRE_TL, ly['pitch'][v]) for v in range(1, 8 if ly is slip else 2)}))
    peel = dusa_tone(gamed, 16)
    for side in (('left',) if two_player else ('left', 'right')):
        out.append(dict(peel, lfo=PEEL_LFO, dsp=PEEL_DSP, direct=TYRE_DIRECT['centre' if two_player else side],
                        by_v={v + 1: (tl + PEEL_TL, p) for v, (tl, p) in enumerate(PEEL[side])}))
    return out


def convert(name, snd, gamed, layers, tyres, src):
    """One race sound file: bank 0 (records, the code from src, samples) and
    the engine tables -> (file bytes, report, tables)."""
    (code_org, code), = m68kasm.assemble(open(src))
    code_at = code_org - BANK0_AT
    bank = bytearray(snd[:0x38])
    bank[0x36] = len(layers) + len(tyres)   # engine module: its table blocks
    bank[struct.unpack_from('>H', bank, 0)[0] + EFREG4_SDL] = 0x00
    samples_at = (code_at + len(code) + 3) & ~3
    samples, placed = bytearray(), {}
    for ly in layers + tyres:
        if ly['sa'] not in placed:
            placed[ly['sa']] = samples_at + len(samples)
            # the sample plus two bytes past the loop end, as in DUSA's RAM
            samples += ly.get('stored') or gamed[ly['sa'] - GAMED_BASE:ly['sa'] - GAMED_BASE + ly['lea'] + 3]
    for ly in layers + tyres:
        sa = placed[ly['sa']]
        # Sega layer record: note range, slot regs 0-5 (8-bit; normal loop or none),
        # 6 bytes the driver sets (TL, modulation, pitch), LFO, DSP send, direct send
        loop = 0x0020 if ly.get('looped', 1) else 0x0000
        bank += struct.pack('>BBHHHHHH6xHHH6x', 0x00, 0x7F, 0x0010 | loop | sa >> 16, sa & 0xFFFF,
                            ly['lsa'], ly['lea'], ly['env'] >> 16, ly['env'] & 0xFFFF,
                            ly.get('lfo', LFO), ly.get('dsp', DSP_INPUT), ly.get('direct', DIRECT))
    bank += bytes([0x7F, 0x00]) + bytes(0x1E)  # note range 7F-00: never plays
    if len(bank) > code_at:
        sys.exit(f'{name}: layer records run into the code at +0x{code_at:X}')
    bank += bytes(code_at - len(bank)) + code
    bank += bytes(samples_at - len(bank)) + samples
    if len(bank) > BANK0_SIZE:
        sys.exit(f'{name}: engine bank needs {len(bank) - BANK0_SIZE} more bytes')
    snd[:BANK0_SIZE] = bank + bytes(BANK0_SIZE - len(bank))

    tables = bytearray(BLOCK * 15) + snd[TABLES_AT + BLOCK * 15:TABLES_AT + BLOCK * 16]
    for k, ly in enumerate(layers):
        b = BLOCK * k
        tables[b + 4:b + 7] = f'{k:02d}-'.encode()
        for i in range(STEPS):
            v = dusa_v(i * 256)
            active = ly['vmin'] <= v <= ly['vmax']
            tables[b + 7 + i] = ly['tl'][v] - GAIN if active else 0xFF
            pv = min(max(v, ly['vmin']), ly['vmax'])
            struct.pack_into('>H', tables, b + 0x3A + 2 * i, cce_pitch(ly['pitch'][pv]))
        tables[b + 0x2A:b + 0x3A] = b'\xff' * 16
    for k, ly in enumerate(tyres, len(layers)):
        b = BLOCK * k
        tables[b + 4:b + 7] = f'{k:02d}-'.encode()
        last = max(ly['by_v'])
        for i in range(STEPS):
            tl, pitch = ly['by_v'].get(i, (None, ly['by_v'][min(max(i, 1), last)][1]))
            tables[b + 7 + i] = 0xFF if tl is None else tl
            struct.pack_into('>H', tables, b + 0x3A + 2 * i, cce_pitch(pitch))
        tables[b + 0x2A:b + 0x3A] = b'\xff' * 16
    snd[TABLES_AT:TABLES_AT + len(tables)] = tables
    report = (f'{len(placed)} samples ({len(samples)} bytes) in bank 0 at +0x{samples_at:X}, '
              f'{BANK0_SIZE - samples_at - len(samples)} bytes free; code at +0x{code_at:X}')
    return snd, report, tables


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    gamed = open(os.path.join(dusa, 'GAMED.BIN'), 'rb').read()
    layers = dusa_def(gamed, 0)
    reports = {}
    for files, tyres, src in ((FILES, tyre_layers(gamed), TYRES_SRC),
                              (FILES_2P, tyre_layers(gamed, two_player=True), SRC_2P)):
        for name in files:
            snd = bytearray(open(os.path.join(cce, name), 'rb').read())
            snd, reports[files], tables = convert(name, snd, gamed, layers, tyres, src)
            if files is FILES_2P:
                # the slot shared by layers 4 and 3 switches where both are silent
                tl = lambda k, i: tables[BLOCK * k + 7 + i]
                assert all(tl(4, i) == 0xFF for i in range(SWITCH_STEP, STEPS)), 'layer 4 past the switch'
                assert all(tl(3, i) == 0xFF for i in range(SWITCH_STEP + 1)), 'layer 3 before the switch'
            out = os.path.join(dst, name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, 'wb').write(snd)

    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in FILES + FILES_2P if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'engine: {len(layers)} DUSA layers; 1P tyres: slip, brake (half rate), peel-out x2; '
          f'{reports[FILES]}; 2P: {reports[FILES_2P]}; {len(FILES)} + {len(FILES_2P)} sound files')


if __name__ == '__main__':
    main()
