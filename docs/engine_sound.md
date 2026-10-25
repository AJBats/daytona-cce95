# Engine sound: DUSA vs CCE

Goal: DUSA's engine sound on CCE95's player car (1P first).

Tools: the debugger now reads the SCSP slot registers at 25B00000-25B003FF
(as a CPU read returns them: KYONEX reads 0; fork commit 82d1e01), decoded by
tools/scsp_slots.py. tools/m68kdis.py disassembles the sound CPU's code.

## The two sound drivers

- DUSA: its own 68000 driver, SOUNDS.BIN at sound RAM 0 (work area a6 =
  0x2000), and per-screen data images loaded at 0x3000 (GAMED.BIN in races).
  The header at 0x3000 holds pointers: [$3000] tone table (16 bytes per
  tone), [$3050] engine definitions, [$3054] engine channel blocks.
- CCE: Sega's sound driver SDDRVS.TSK with an engine module added
  (68K 0x18EE-0x1D10, work 0x6F00-0x6FFF), and a sound file per mode loaded
  at 0xB000 (DAYTONA.SND, DAY3_1P.SND, DAY4_1P.SND in 1P races). Area map in
  races: tone bank 0 = the engine alone (0xB000, 0xE8E6 bytes), banks 1-2
  other sounds, engine tables (map type 4) at 0x7F000 (0x800 bytes, file
  offset 0x74000). All three 1P files have the same bank 0 and engine
  tables; the 2P files share a different set.

## DUSA: rpm -> engine

SH-2 0602F7EA (car tick, 20 Hz): v = (rpm - 1800) x 128 / 5300 clamped to
1..127, rpm = car +0xE4 clamped to 1800..8500 (so v is 127 from ~7060 rpm).
Sent only when it changes, as mailbox long 25A02C20 = A0 70 vv FF
(0601D5F4 id 1). Other ids: A1 70 = slip |+0x5C| >> 10 (0-7), AE 06 = a
flag on car +0 bit 14, AE 11 xx = one-shots.

Driver 0x16D4 (A0 70 vv on channel 0): channel block type 0 -> engine
definition; per layer: tone, active v range, TL table [v], pitch table [v]
(slot OCT/FNS word). Entering the range keys a slot on (LFO 0x71B4, direct
level 2, DSP input level 6); leaving it keys it off.

Engine type 0 (GAMED.BIN), all samples 8-bit:

| layer | sample (sound RAM) | loop | v range | pitch ratio v1 -> v127 | role |
|---|---|---|---|---|---|
| 0 | A 06100 | 0000-164D | 2-127 | 0.083 -> 0.359 | main |
| 1 | B 0794E | 00B4-194D | 5-127 | 0.166 -> 0.714 | main, octave up |
| 2 | C 0949C | 0000-1517 | 3-93 | 0.179 -> 0.473 | low/mid, fades out by v 93 |
| 3 | A 06100 | 0000-164D | 72-127 | as layer 1 | top end, fades in from v 80 |
| 4 | D 0ABB4 | 0000-144B | 1-63 | 0.250 -> 0.499 | idle, fades out by v 63 |
| 5 | D 0ABB4 | 0000-144B | 1-63 | 0.207 -> 0.389 | idle, detuned pair of 4 |

No throttle input: DUSA's engine depends on rpm only.

The driver applies a new v at once (no glide): each layer inside its range
gets TL[v] and pitch[v]; a layer leaving its range is keyed off, one
entering it is keyed on in a free slot. v = 0 keys the channel off.

### Idle

DUSA's rpm (+0xE4) comes from the driven wheels' speed: 0 at a standstill,
no idle rpm (1P Time Lap recordings: ~205 rpm per km/h in 1st, lower while
braking). Below ~1880 rpm v is 1, where only layers 4-5 are in range, so
the idle pair plays alone at TL 16: stopped, or crawling under ~9 km/h in
1st. From v 2 the rev layers key on; layer 2 is at full level by v 17
(~2500 rpm), the idle fades to TL 72 by v 56 and stops above v 63.

CCE95, braked to a stop: CCE's rpm is 500 (v 1); slots 28-29 (the idle
pair) are at TL 16 with DUSA's v 1 pitches (0.281, 0.209), the rev layers
at TL 255.

### Everything else 0602F7EA sends (player car, 20 Hz)

| message | from | driver |
|---|---|---|
| A0 70 v | rpm, above | channel 0, engine type 0 |
| A1 70 v | slip: \|+0x5C\| >> 10, 0-7 | channel 1, type 1: tone 4 (0C200), v 1-8 |
| A2 70 0/1 | 1 while +0x0C != 0 (moving) and brake pedal +0x84 (0-255) > 200; 0 ten ticks after that ends | channel 2, type 2: tone 5 (0CD58, loop to 0F21E), v 1-16 |
| AE 11 1E / 42, AE 11 1C / 40 | car +0x166 reaches 10 / 3 (when +0x1BC = 0; the second id when byte 0605D241 is set) | the peel-out: tone 16 (25E25, one-shot) |
| AE 11 1B / 3F | car +0xB8 = 44 | tone 10 (1AD72), not identified yet |
| AE 06 01 / 00 | entering / leaving per-course stretches of track (table 0602FD3C by course, +0x1EC within a range, +0x14 above 0x100000): none on course 0, two on course 1, one on course 2 (tunnels?) | DSP output mix preset 1 / 0 (table [$3014], 0x0F8E): preset 0 plays effect outputs 0-1 at level 2, preset 1 mutes them and plays outputs 2-3 at level 4 |

Channel 3 (A3 70, type 3) is never sent in a race; GAMED.BIN defines types
0-2 only. Neither channel 1 nor channel 2 is in CCE95.

AE 11 xx starts sequence xx of group 0x11 (table [$301C]): a note-on on one
MIDI channel, whose program (table [$3004], 8 bytes per note, word 0 = tone)
picks the tone. The channels' programs (driver table $c40, 16 bytes per
channel: +1 channel, +2 program): 9, A, E -> program 0, sound effects
(tones 6-24, 36, and 10, 16, 17 at the top); C -> program 3 (36 notes:
tones 25-35, 37-60, 17), the narrator and at least one wall hit (AE 11 37,
note 0x20, tone 57); D -> programs 1 and 2 at once, panned left and right
(notes 0-4: tones 17, 10, 16, 16, 16). So the 1B/1C/1E one-shots and their
3F/40/42 alternates play the same tones by two routes.

Car +0x166 is the peel-out timer (a straight launch from a standstill on
the Three Seven, 2026-10-24): it is set to 10 the tick wheelspin +0x110
goes positive, cycles 7 down to 4 while the wheels spin, then runs down to
0 once they stop. So the peel-out sound plays at the onset (10) and again
as the spin ends (3); in between, the wheels spinning in a straight line
make no other tyre sound (slip +0x5C stays 0). Confirmed by ear with every
sound on: peel-out entry, engine only, peel-out exit. Hard braking starts
the same timer (what else sets +0x166 is not traced yet).

Other ambience from the second car-tick routine 0602F99C: AE 11 19 (note
D 0 = tone 17, the looped 2AB9D) every 20 ticks while on course 0 with
+0x1EC in 1-30, i.e. the grandstand crowd; AE 11 10/11 and 12/13 (notes
A 12 / 13 on and off = tones 19 and 20, looped) are wall scrapes, armed by
the wall-contact code (06030C48 / 06030CDC set timers 0602FD9B / 0602FD9C).

### By ear, one part at a time

[sound_lab.md](sound_lab.md): what each part sounds like alone (the user's
notes from a live lab in the debugger), every listening note so far, and
how the lab works. The slip channel is to be ported faithfully.

### Mix

| | DUSA engine slots | CCE95 engine slots |
|---|---|---|
| direct level | 2 (the same as every other DUSA sound) | 4 (most other CCE sounds: 7) |
| DSP send | ISEL 0, IMXL 6 | ISEL 5, IMXL 6 (CCE's DSP program) |

DUSA's other sounds send little to the DSP (ISEL 1 IMXL 3, ISEL 2 IMXL 0),
so its DSP program works mostly on the engine.

Everything else about the voices is the same in both games (sample bytes,
loops, envelope, LFO, pitch and level tables: checked register by register
and byte by byte), so this routing is what differs.

The DSP programs (tools/scsp_dsp.py lists one and runs an impulse through
it): DUSA's is [$3018] entry 0 (sound RAM 3DE8, copied to SCSP 700-BFF;
ring buffer RBL 2 at 70000). CCE's race program is the area map's type 2
block (75A96, a 0x40-byte "Q_demo5.EXB" header, then the same 0x500-byte
image). With each game's race output mix (EFSDL/EFPAN):

| | DUSA (input 0, mix preset 0) | CCE95 (input 5, bank 0 mixer) |
|---|---|---|
| direct | level 2 | level 4 |
| DSP copy | 0.5 x (engine + 1.6 x input 1), DC-blocked, to EFREG6 at level 3 | 2nd-order low-pass to EFREG4 at level 4 |
| reverb | 64 ms pre-delay, ~1 s decay, EFREG0/1 at level 2 left/right | none (CCE's echo, EFREG2/3, is at level 0 in races) |
| tunnel echo | EFREG2/3, ~3 s, level 0 (4 in mix preset 1) | - |

So CCE95 plays the engine 12 dB hotter in the chip's mix, about 4 dB
heavier below ~1 kHz (the low-passed copy), and dry; DUSA's is flat with a
quiet reverb about 23 dB under the direct sound. CCE's other race sounds
send to input 4 (the echo, muted) so they are dry too; the race uses
CCE's DSP only for the engine's low-pass.

Recordings (docs/sound_lab.md, build/snd/wav): each layer alone over the
same drive in both games. Pitches match; CCE95 is 0.5-2 dB quieter in the
WAVs; DUSA carries more 1-5 kHz (spectral centroid 10-30% higher, up to
2x near the limiter) and a reverb tail of about 2 s after the sound stops
(CCE95 stops dead). CCE95 also shows broadband clicks on sharp rpm drops
(wall bounces) that DUSA's recordings don't.

## CCE: rpm -> engine

SH-2 06030AFA (car tick, 30 Hz) writes 4 longs to 25A06F00: rpm (car
+0xD4), throttle level, km/h (+0x34), gear (+0x17A). Throttle level =
(+0x80 >> 5) + 8 when byte [[06052094] + 0x2C] > 1 (2 in Time Attack, both
transmissions), else + 0; 7 (+8) when car +0x5C = 2.

68K engine module (1P: up to 8 layers on slots 24-31): index i = rpm >> 8
(0..34, rpm clamped below 0x2300 -> 0x2200), recomputed when i or the
throttle level changes. Per layer, 0x80 bytes at 0x7F000 + n x 0x80: +0
pointer to the layer's tone (bank 0 voice 0, filled by the driver), +7
level[35] by i, +0x2A throttle offset[16], +0x3A pitch[35] (0x2000 + octave
x 0x400 + FNS). TL = level[i] - offset - 1 (offset sign-extended; 0xFF ->
TL = level[i]). CCE's own engine: 8 layers, 5 samples, the throttle level
picking layers in or out.

## Differences that matter for the transplant

- Resolution: CCE's tables have 35 rpm steps of 256; DUSA's 128 steps of
  ~41 rpm. DUSA's pitch spans x4.3 over v 1-127, which CCE's ~20 steps over
  the same rpm would turn into ~1.3-semitone jumps.
- DUSA sets a pitch+amplitude LFO (0x71B4) on every engine slot.
- Mixing: DUSA engine slots have direct level 2 and DSP input level 6;
  CCE's have direct level 4 and their own DSP sends. The DSP programs
  differ.

## Transplant (first version)

- tools/engine_convert.py (make disc) rewrites bank 0 and the engine
  tables of the three 1P race files: DUSA's six layers and four samples,
  tables sampled from DUSA's at rpm = i x 256, TL 255 outside a layer's v
  range, throttle offsets 0xFF. DUSA's LFO; CCE's engine sends (DSP 0x002E,
  direct 0x903C) for now.
- patches/engine_interp.s: the driver keeps the whole rpm and interpolates
  pitch and level between steps. Space from the MIDI CC18/CC20 handler,
  whose rpm table becomes a multiply with the same results. The 2P files
  keep CCE's engine, now interpolated too.
- Checked in the emulator: from the rolling start (rpm 7000) slots 24-29
  hold DUSA's samples, loops and LFO, and TL/pitch match DUSA's tables at
  v 125.
- Arcade race (15 s at 15th of 40, drones passing): every other sound
  plays from banks 1-2 (slots 0-12); only the engine slots read bank 0.
  CCE's drones have no engine sound, only a pass-by whoosh.
- By ear (the user, against DUSA's Time Lap): very similar.
- Mix (2026-10-24, after the sound lab's drag comparison): bank 0's
  mixer plays EFREG4, the engine's low-passed copy, at level 0 instead of
  4, and the level tables are 9 TL steps (+3.4 dB) louder. The engine's DSP
  send stays, so CCE's tunnel echo still hears it; the tunnel only
  rewrites EFREG2/3 (traced over a 3-7 lap), so EFREG4 stays off through
  it. On the same drive, CCE95 is within 1 dB of DUSA in every phase from
  idle to the stop. The user's verdict: a great match.
- Tunnel echo (2026-10-25, the user heard none under Three Seven's cover,
  on a real Saturn): CCE switches it on from the ground's surface type
  (type 2, road under a roof; docs/conformance.md), and DUSA's ground
  under CCE95 had no type 2 since 2026-10-24. tools/col_convert.py now
  marks DUSA's polygons under CCE's roofs. Recorded through the rolling
  start from a fresh boot, the cover (x -24 to -48) lifts the whole mix
  3 dB in CCE95, as it lifts CCE's 2.5-3 dB. DUSA itself has no echo on
  Three Seven (its AE 06 stretches are on courses 1 and 2).
