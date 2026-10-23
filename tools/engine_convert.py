"""Put DUSA's engine sound into CCE's 1P race sound files.

usage: engine_convert.py <dusa extracted dir> <cce extracted dir> <out dir>
  Reads DUSA's GAMED.BIN (its race sound data, loaded at sound RAM 0x3000)
  and CCE's DAYTONA.SND, DAY3_1P.SND and DAY4_1P.SND (loaded at 0xB000);
  writes the three under <out dir>/DAYTONA and lists them in PATCHED.txt.
  Files keep their sizes (the disc keeps the original directory entries).

DUSA (docs/engine_sound.md): engine definition 0 has six layers, each a
looped 8-bit sample with a TL table and a pitch table indexed by
v = (rpm - 1800) x 128 / 5300 (1..127), active for a v range.

CCE: tone bank 0 (file +0, 0xE8E6 bytes) holds only the engine voice, and
the engine tables (file +0x74000, 0x800 bytes) one 0x80-byte block per
layer: +7 level[35] and +0x3A pitch[35] by i = rpm >> 8, +0x2A an offset by
throttle level. Written here:
  bank 0     CCE's header and mixer/VL/PEG/PLFO data, voice 0 with the six
             DUSA layers (and a seventh record that never plays, as the
             Sega format counts layers - 1), then DUSA's four samples
  tables     blocks 0-5 from DUSA's layers sampled at rpm = i x 256 (TL 255
             outside the layer's v range), throttle offsets 0xFF (no
             throttle effect, as in DUSA); blocks 6-14 empty, block 15
             (2P pans) kept
patches/engine_interp.s makes the driver interpolate between the 256-rpm
steps.
"""
import os
import struct
import sys

GAMED_BASE = 0x3000
FILES = ('DAYTONA/DAYTONA.SND', 'DAYTONA/DAY3_1P.SND', 'DAYTONA/DAY4_1P.SND')
BANK0_SIZE = 0xE8E6
TABLES_AT, BLOCK = 0x74000, 0x80
STEPS = 35
LFO = 0x71B4                    # DUSA's engine slots: pitch + amplitude LFO
DSP_INPUT = 0x002E              # slot +0x14: CCE's engine DSP send (ISEL 5, IMXL 6)
DIRECT = 0x903C                 # slot +0x16: CCE's engine direct level 4, centre


def dusa_engine(gamed):
    """DUSA engine definition 0 -> list of layer dicts."""
    L = lambda a: struct.unpack_from('>I', gamed, a - GAMED_BASE)[0]
    W = lambda a: struct.unpack_from('>H', gamed, a - GAMED_BASE)[0]
    B = lambda a: gamed[a - GAMED_BASE]
    tones = L(0x3000)
    d = L(L(0x3050) + 2)
    layers = []
    for k in range(W(d) + 1):
        p = d + 4 + 12 * k
        t = tones + 16 * (W(p) & 0x3FF)
        sa, end, loop, env = L(t) & 0x7FFFF, L(t + 4) & 0x7FFFFFFF, L(t + 8), L(t + 12)
        vmin, vmax = B(p + 2), B(p + 3)
        tl, pitch = L(p + 4), L(p + 8)
        layers.append({
            'sa': sa, 'lea': end - 1, 'lsa': loop - sa, 'env': env, 'vmin': vmin, 'vmax': vmax,
            'tl': [B(tl + v) for v in range(128)],
            'pitch': [W(pitch + 2 * v) for v in range(128)],
        })
    return layers


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


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    gamed = open(os.path.join(dusa, 'GAMED.BIN'), 'rb').read()
    layers = dusa_engine(gamed)

    for name in FILES:
        snd = bytearray(open(os.path.join(cce, name), 'rb').read())
        bank = bytearray(snd[:0x38])
        bank[0x36] = len(layers)                # engine module: layer count
        samples_at = 0x38 + 0x20 * (len(layers) + 1)
        samples, placed = bytearray(), {}
        for ly in layers:
            if ly['sa'] not in placed:
                placed[ly['sa']] = samples_at + len(samples)
                # the sample plus two bytes past the loop end, as in DUSA's RAM
                samples += gamed[ly['sa'] - GAMED_BASE:ly['sa'] - GAMED_BASE + ly['lea'] + 3]
        for ly in layers:
            sa = placed[ly['sa']]
            # Sega layer record: note range, slot regs 0-5 (8-bit, normal loop),
            # 6 bytes the driver sets (TL, modulation, pitch), LFO, DSP send, direct send
            bank += struct.pack('>BBHHHHHH6xHHH6x', 0x00, 0x7F, 0x0030 | sa >> 16, sa & 0xFFFF,
                                ly['lsa'], ly['lea'], ly['env'] >> 16, ly['env'] & 0xFFFF,
                                LFO, DSP_INPUT, DIRECT)
        bank += bytes([0x7F, 0x00]) + bytes(0x1E)  # note range 7F-00: never plays
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
                tables[b + 7 + i] = ly['tl'][v] if active else 0xFF
                pv = min(max(v, ly['vmin']), ly['vmax'])
                struct.pack_into('>H', tables, b + 0x3A + 2 * i, cce_pitch(ly['pitch'][pv]))
            tables[b + 0x2A:b + 0x3A] = b'\xff' * 16
        snd[TABLES_AT:TABLES_AT + len(tables)] = tables

        out = os.path.join(dst, name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(snd)

    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in FILES if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'engine: {len(layers)} DUSA layers, {len(placed)} samples ({len(samples)} bytes) '
          f'in bank 0 at +0x{samples_at:X}; {len(FILES)} sound files')


if __name__ == '__main__':
    main()
