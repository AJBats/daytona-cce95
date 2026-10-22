# Conformance: how close is CCE to DUSA?

Two measures, kept for every patch.

## 1. Code fidelity

Each difference in docs/driving_model.md has a status: converted (DUSA
logic/values with stated 20→30 Hz rules), approximated, CCE behaviour kept,
or not examined. A patch is only allowed if it moves a row to converted or
approximated; tuning by feel is not allowed.

Conversion rules: per-tick increment ×2/3, per-tick acceleration ×4/9,
per-tick multiplier m → m^(2/3), tick count ×3/2.

| Patch | Row | Status |
|---|---|---|
| 1 steering | steering ramp | converted |
| 2 slide_rate | slide-rate clamp | converted |
| 3 wheelspin | spin decay converted; grip floor restored to DUSA | converted |
| 4 grip_recovery | recovery multiplier, two timers | converted |
| 5 lateral_force_filter | lateral force smoothing | approximated (step 0.1875 vs 0.175) |
| 6 high_speed_grip_loss | high-speed grip loss | converted (pad variant only) |

## 2. Behaviour: scripted power slide at turn 3

The user's DUSA slide was recorded (build/dusa_flying_rec2.bin) and turned
into a button script with tools/inputscript.py (lead 3 frames). Replayed in
DUSA it reproduces the recording on every compared field for 470 frames.
The same script (pedal buttons swapped) is replayed in each CCE build from
build/states/cce_p6_flying.mcs, hot-patched to each level with
tools/pokes.py, and the brake press is aligned to DUSA's braking point
(x = -190). Scored by tools/conformance.py over 4 s from the brake press.

Known mismatch: CCE reaches the braking point at 294 km/h vs DUSA 309, and
0.6 units further left. Speed is scored as km/h lost to remove the offset.

RMS error vs DUSA (lower is closer):

| build | heading (deg) | slide angle (deg) | speed lost (km/h) | path (units) | peak slide | turned | speed lost |
|---|---|---|---|---|---|---|---|
| DUSA | – | – | – | – | 54.1° @ 1.80 s | 148.8° | 46 |
| stock | 49.0 | 31.3 | 84.7 | 39.7 | -54.7° @ 2.50 s (spun) | 125.3° | 236 |
| p1 | 30.7 | 20.6 | 62.2 | 24.8 | -39.2° @ 3.03 s | 139.2° | 178 |
| p1–2 | 21.9 | 19.0 | 10.8 | 16.2 | 36.2° @ 1.00 s | 176.8° | 64 |
| p1–3 | 21.1 | 22.1 | 12.1 | 15.9 | 41.2° @ 3.80 s | 194.3° | 67 |
| p1–4 | 21.1 | 22.1 | 12.1 | 15.9 | same as p1–3 | | |
| p1–5 | 15.6 | 12.0 | 7.9 | 15.9 | 38.5° @ 1.73 s | 174.1° | 62 |
| p1–6 | 14.3 | 10.1 | 6.7 | 16.9 | 40.9° @ 1.77 s | 171.9° | 60 |

Notes:
- Patch 3 made the slide angle and speed slightly worse in this test; it
  stays under review.
- Patch 4 had no effect on this manoeuvre (its code paths aren't hit).
- Remaining gap: peak slide 41° vs 54° at the right time; CCE turns ~23°
  more over the window and loses ~14 km/h more.

## Whole-run scores are chaotic

Re-running the seven builds from a speed-matched CCE state (313 vs 309 km/h
at the braking point, build/states/cce_p6_flying2.mcs) flipped the ranking:
p1–3/p1–4 slid like DUSA, p1–5/p1–6 spun. The slide sits on a slide/spin
knife edge, so whole-run scores mostly say which side a build lands on.

## 3. State forcing (tools/teacher.py)

DUSA's recorded state is converted to CCE layout/units and poked into CCE's
car before every CCE tick (`poke_playback_start`, trigger 0x0604D380), then
CCE's one-tick result is compared with DUSA over the same 2 frames. CCE is
reset every tick, so differences can't compound.

Practicalities found while building it:
- CCE ticks on even frames, DUSA on frames == 2 (mod 3); CCE frame c ~ DUSA
  frame c + 71 for this slide. In the sample, the output of forced row r is
  at index 2r (the first row is applied on the first sampled frame).
- Writing CCE position 0x08 alone corrupts it and stops the car update (CCE
  keeps another position copy); position is left to CCE.
- Gear/rpm are left to CCE (different gear numbering).
- Poke triggers survive load_state: always clear them.

Forced fields: heading, travel, speed, km/h, yaw 0x64, slip 0x68, slide rate
0x104, heading step 0x44, lateral force 0xE8/0xEC, grip limits 0xF4/0xF8,
grip 0x70, wheelspin 0x100, steering 0x78/0x7C/0xAC, throttle 0x80, brake
0x90.

Findings on the turn-3 slide (patches 1–6):
- Speed change under braking matches tick for tick.
- Front-wheel input (DUSA 0x40 / CCE 0x14) matches.
- Heading step (0x154 / 0x44) matches without steering but is 30–70% lower
  with the wheel turned (incl. countersteer): e.g. 836 vs 532, 580 vs 152.
- Slide rate (0x178 / 0x104) is larger in magnitude in CCE and hits CCE's
  clamp where DUSA's doesn't.
- Hypothesis "Hornet yaw gain 0x3A0 should be 0x52F" rejected: forcing with
  0x52F makes per-tick RMS error 4–8x worse (rate 167 -> 654, heading step
  169 -> 1423).

## Caveat (2026-10-22): poke_playback byte order

32-bit columns written by `poke_playback_start` reached the CPU byte-reversed
in at least some cases (the gain field read as 0xA0xx after writing
0x03A0052F), while `read_memory` showed the intended bytes. Static
`poke_breakpoint_set` pokes (16- and 32-bit) were read correctly. All forced
results above (per-tick tables, and the two gain-test rejections) are
unreliable until re-run on the fixed debugger.

Register-log findings that don't depend on playback pokes still stand: in
the core step DUSA's grip-limited rotation term (r6, logged at 0602D61E)
sits at 120 through the slide while CCE's (06036146) is mostly 0. Both
compute atan(grip force / speed^2); CCE's Hornet rear gain 0x3A0 gives ~70%
of the 30 Hz-converted DUSA value, and CCE's atan routine (06047E0C) shifts
its numerator left 16 bits, so the converted gain would overflow there.
DUSA also falls back to a per-car minimum (+0x7F) when the table gives 0;
CCE has no fallback.

## Re-run on the fixed debugger (poke_playback byte order fixed)

Verified: the CPU reads playback-poked values correctly (gain 0x052F read at
0603605A on every tick, including the first).

Forced per-tick RMS error vs DUSA, turn-3 slide, p1–6 base:

| | as-is | rear gain 0x52F only | both gains 0x52F |
|---|---|---|---|
| slide rate | 174.5 | 169.8 | 103.7 |
| heading step | 164.2 | 191.7 | 177.0 |
| slip | 99.2 | 1040.3 | 51.7 |
| yaw | 373.3 | 1063.6 | 292.1 |
| travel | 255.1 | 1730.9 | 189.1 |
| lateral force (M) | 43.6 | 40.9 | 37.2 |
| grip | 2151 | 2941 | 1996 |

The earlier "gain rejected" results were artefacts of the byte-order bug.
The two gains go together (DUSA's Hornet uses 0x1180 for both). No atan
overflow at 0x52F: numerator ~0x22AB here, ~0x3400 at the largest grip limit.

## Patch 7: Hornet rotation gains (patches/hornet_yaw_gain.patch)

Per-car data, Hornet only: 0x3A0/0x3A0 -> 0x52F/0x52F. Other cars' gains are
untouched (no DUSA counterparts to convert from).

Closed-loop replay of the slide (chaotic, indicative only):

| build | heading | slide | speed lost | path | peak slide | turned | speed lost |
|---|---|---|---|---|---|---|---|
| p1–6 | 45.7 | 27.4 | 95.1 | 39.6 | -52.3° @ 2.77 s | 117° | 269 |
| p1–6 + gain | 34.9 | 29.6 | 10.9 | 5.9 | 63.0° @ 1.83 s | 232° | 69 |

Best path and speed match so far; peak slide at the right time but ~9° too
large, and the car keeps rotating (232° vs DUSA 149°). Heading step and
slide rate remain the largest per-tick errors.

## Patch 8: rotation term computed DUSA's way (patches/rotation_atan.patch)

The first patch that adds code. The core step's r6 = atan(gripR * grip *
gain / v^2) now runs a replacement routine (patches/rotation_atan.s) in a
dead function at 06032918; the call's literal (0603611C) points at it.
It reproduces DUSA's rounding to 1/256 atan steps and its per-car minimum
(5, Hornet), then converts to 30 Hz (x2/3). DUSA's atan table equals every
second entry of CCE's (all 257 values).

Cave choice: 06032918 (408 bytes, 116 used) has no branch to it in
RACE.BIN, no pointer to it in any file on the disc, and was never executed
in a CDL run of a race (build/cdl_race37.bin). It is code inside RACE.BIN,
so it is loaded for every track.

Forced per-tick RMS error vs DUSA (same run as above):

| | p1–7 | p1–8 |
|---|---|---|
| slide rate | 103.7 | 86.4 |
| heading step | 177.0 | 174.6 |
| slip | 51.7 | 38.3 |
| yaw | 292.1 | 296.9 |
| travel | 189.1 | 196.8 |
| lateral force (M) | 37.2 | 38.9 |

Closed-loop replay, 240 frames:

| build | heading | slide | speed lost | path | peak slide | turned |
|---|---|---|---|---|---|---|
| DUSA | | | | | 54.1° @ 1.80 s | 149° |
| p1–7 | 34.9 | 29.6 | 10.9 | 5.90 | 63.0° @ 1.83 s | 232° |
| p1–8 | 25.2 | 20.3 | 10.2 | 5.42 | 54.2° @ 1.83 s | 212° |

Peak slide now matches; heading tracks DUSA to 1.8 s. Still open: the
entry lag (heading 6.8° vs 15.0° at 0.4 s, unchanged) and the slide not
recovering after 2 s (stays 31–42° while DUSA's returns to 0).

Note: forced runs must start from a paused emulator; loading the state
while it runs lets frames pass before the playback starts and the run is
invalid.
