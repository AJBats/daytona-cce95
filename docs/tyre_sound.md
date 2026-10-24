# Tyre sounds: DUSA vs CCE

Goal: DUSA's tyre sounds on CCE95, made by CCE's own sound system (as the
engine was, docs/engine_sound.md). The user's notes on each DUSA sound are in
docs/sound_lab.md; DUSA's slip channel is to be ported faithfully.

Car fields (DUSA / CCE, from the handling work): slip angle +0x5C / +0x68,
brake pedal +0x84 / +0x90, wheelspin +0x110 / +0x100, grip +0x10C / +0x70.

## DUSA (car tick 0602F7EA, 20 Hz; docs/engine_sound.md)

Slip and brake are channels of the same kind as the engine: a looped sample
with TL and pitch tables indexed by a value v, keyed on while v is in range.

| sound | when | sample | by v |
|---|---|---|---|
| slip (channel 1, type 1) | v = \|slip\| >> 10, 0-7; on from v 1 | tone 4, 0C200, 0x958 bytes, looped whole | TL 4 6 8 12 14 16 18, pitch 7800 780A 7818 7820 786C 788E 78B0 (v 1-7): higher and a little quieter as the slide grows |
| brake (channel 2, type 2) | v 1 while moving with the brake pedal > 200, back to 0 ten ticks after | tone 5, 0CD58, 0x59CA bytes, loop from F21E | only v 1 is sent: TL 0, pitch 7800 |
| peel-out | one-shot when the timer +0x166 reaches 10 (wheelspin onset, hard braking) and 3 (the spin ending) | tone 16, 25E25, 0x4D78 bytes, not looped, AR 11 | - |

## CCE

Sound effects are sequences: StartSeq 06007900 sends command 01 with a
control number, bank and song (sound RAM 25A00700); StopSeq 06007926 stops a
control number. The car's effect sounds come from 06037E28.

Traced over the user's drag take with every sound on. The drag itself had
no slide on purpose (a straight line), only a standing-start wheelspin and
hard braking to a stop; the setup before it had one slide under braking.

| song (bank 0) | when | code |
|---|---|---|
| 17, loop | on while moving on the ground with either axle's grip (+0x6C, +0x70) under 1.0; off at full grip. No change with how hard the car slides | 06039014 (state in car +0x1C3) |
| 19, one-shot | each time event flag +0x30 bit 13 is set: hard braking, and every 6 frames through a wheelspin launch | 06039014 |
| 18, one-shot | as the car stops on the brakes (6 km/h or less in the take; the countdown at +0x198 that fires it is not read yet) | 06038D6E |
| 27, one-shot | a contact event: flag +0x30 bit 6 on the ground, with +0x170 set and +0x30 bit 3 (the same path plays song 6 or 3 otherwise). Not a tyre sound | 06038E2A, in 06038DD8 |

On the straight, flat out at 200-307 km/h with no slide, song 17 switched
on and off a dozen times: the rear grip dips to 0.84-0.99 under power.
The slip angle stayed under 430 there, below DUSA's slip channel threshold
(1024), so DUSA is silent through the same drag. Through the launch
wheelspin song 17 plays throughout, and song 19 retriggers every 6 frames
for 1.1 s.

## Donuts (2026-10-24)

The user did donuts in both games, each between two pauses: a launch into
full lock, held, released, a second donut, then braking to a stop. Each
part is recorded alone over the same drive in build/snd/donut (DUSA from
dusa_donut_1900.mcs, CCE95 from cce_donut_1460.mcs; every replay follows
the live drive to the end). CCE95's tyre sounds are lab parts now:
squeal, screech, stop (soundlab.py, CCE_TYRES).

At full lock both games pin the slip angle at the clamp (13312), so DUSA's
slip channel sits at v 7; v 2-6 only pass by, a tick or two each, as the
slide builds and dies (an audible quick sweep).

| | DUSA | CCE95 |
|---|---|---|
| slide | slip loop, tonal (bands at ~0.9, 1.8, 2.7 kHz), 4 dB under the engine at v 7. v 1 to v 7: 5.5 dB quieter, pitch +15% (peak 773 to 891 Hz), as its tables say | squeal loop ~7 dB under the engine, plus the screech retriggered every 6 frames the whole time, pulsing 45-62 dB, noisy up to 6 kHz |
| wheelspin onset and end | peel-out one-shot, ~58 dB | screech, as above |
| braking to a stop | brake loop, ~3 dB over the engine | squeal and screech |
| at the stop | - | song 18 keys on but is silent: its sample address is the start of tone bank 1 |

A sound from tone bank 2 (582AE, then 71738 about 2 s later) also played
three times during CCE95's donuts (bank 1 song 5). Not a tyre sound.

## Space

The 1P sound files keep their sizes. Free in a race: 35 KB at the end of
the engine bank (10B00-19900) and 8 KB at the end of bank 1 (3AD00-3CE00).
DUSA's slip and brake samples need 25.4 KB, the peel-out 19.8 KB.

The 1P engine module drives up to 8 slots (24-31); DUSA's engine uses 6.
