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
