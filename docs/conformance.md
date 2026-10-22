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

## Patch 9: steering deadzone (patches/steer_deadzone.patch)

Frame-by-frame on the replay: the press reaches the steering ramp 3 frames
later in both games, but DUSA's scaled steer (0xB0) and wheel angle move on
that same tick, while CCE's (0x7C, 0xAC) wait one more tick. Cause: the
ramp -> steer deadzone, 5 in DUSA and 12 in CCE; CCE's first 30 Hz ramp
step is 11, so it fell inside. Restored DUSA's mapping exactly
((|ramp| - 5) * 17 / 10, same as * 255 / 150).

Closed-loop replay:

| build | window | heading | slide | speed lost | path |
|---|---|---|---|---|---|
| p1–8 | 2 s | 5.5 | 3.1 | 4.1 | 4.10 |
| p1–9 | 2 s | 5.1 | 2.9 | 2.5 | 2.36 |
| p1–8 | 4 s | 25.2 | 20.3 | 10.2 | 5.42 |
| p1–9 | 4 s | 29.3 | 22.9 | 8.0 | 4.37 |

Path gap at 1.0 s: 4.79 -> 2.95; at 2.0 s: 4.76 -> 0.92. The 4 s heading
and slide scores are dominated by the slide not recovering after 2 s.

## Patches 10–11: front rotation term, yaw smoothing, wheel filter

Forced run extended to 150 ticks (build/teacher_long_gain.csv) to cover
the slide recovery. With patches 1–9, CCE's heading step ran ~250 too high
per tick from 1.9 s on, with yaw ~200 too close to zero after each tick.

Patch 10 (in patches/rotation_atan.patch, source rotation_atan.s): the
core step's second atan (front, sets yaw +0x64) gets the same DUSA
treatment as the rear one (rounding, minimum +0x7E = 7), kept as an angle
(no tick conversion); its scaling shift goes back from >>7 to DUSA's >>8;
and DUSA's yaw smoothing (yaw = t - (t - yaw)/8 per tick), dropped by
CCE, is restored at 30 Hz as /4.

Patch 11 (patches/wheel_filter.patch, source wheel_filter.s): the pad
wheel-angle filter halved the gap per 30 Hz tick (DUSA: per 20 Hz tick).
Now keeps 0.630 of the gap per tick. A 1/8 of the wheel angle feeds the
front input, so the faster wheel was adding ~60 to front + yaw - slip,
which drives the heading step (~2x).

Forced per-tick RMS error (150 ticks):

| | p1–9 | +10 | +11 |
|---|---|---|---|
| slide rate | 115.0 | 109.7 | 109.7 |
| heading step | 134.9 | 162.9 | 131.6 |
| slip | 57.6 | 53.9 | 53.9 |
| yaw | 287.0 | 213.1 | 192.5 |
| travel | 173.2 | 188.5 | 166.4 |
| lateral force (M) | 34.5 | 37.1 | 32.5 |

Closed-loop replay:

| build | window | heading | slide | speed lost | path | peak slide | turned |
|---|---|---|---|---|---|---|---|
| DUSA | 4 s | | | | | 54.1° @ 1.80 s | 149° |
| p1–9 | 2 s | 5.1 | 2.9 | 2.5 | 2.36 | | |
| p1–11 | 2 s | 3.8 | 2.9 | 1.6 | 2.36 | | |
| p1–9 | 4 s | 29.3 | 22.9 | 8.0 | 4.37 | 58.6° @ 1.83 s | 220° |
| p1–11 | 4 s | 10.1 | 7.8 | 52.0 | 7.79 | 54.0° @ 1.80 s | 160° |

The slide now recovers: 0° at 2.8 s (DUSA 3.0 s), heading 135.7° vs
135.9° at 2.0 s. Afterwards CCE straightens past DUSA (heading 122° vs
144° at 3.0 s) and the replay runs into the wall (the 4 s speed and path
scores).

Debugger note: poke_breakpoint_set takes at most 64 pokes per trigger;
pack 32-bit pokes and split across trigger PCs (0x06035F48, 0x0604D758).

## Patch 12: self-straightening; yaw smoothing factor revisited

After the slide (3.07–3.20 s, forced), DUSA's heading moves +40 per 30 Hz
tick with no heading step: its straightening pull (60 per 20 Hz tick,
saturated). CCE: 0. CCE had retuned it (window 6° -> 5°, 2 -> 4 ticks,
pull 60 -> 16). patches/straightening.patch restores DUSA's at 30 Hz
(6°, 3 ticks, 40). It now engages in the forced run, a few ticks later
than DUSA's: CCE's road-direction field (+0x48) comes from CCE's own course
data and steps differently from DUSA's (+0x25C), which resets the counter.

Yaw smoothing: of the two 30 Hz equivalents of DUSA's per-tick 1/8 (see
rotation_atan.s), matching the lag (3/17) beats matching the decay (1/4)
in the forced test; the same comparison for the wheel filter does not
(kept at decay-matched 0.370):

| forced RMS | yaw 1/4 | yaw 3/17 | yaw 3/17 + wheel lag-matched |
|---|---|---|---|
| heading step | 131.6 | 107.1 | 109.1 |
| travel | 166.4 | 150.2 | 151.3 |
| yaw | 192.5 | 202.4 | 207.8 |
| lateral force (M) | 32.5 | 29.3 | 29.4 |

Closed loop (p1–12, yaw 3/17): 2 s window heading 2.9, slide 3.2, path
2.11 (best yet); peak slide 51.1° (DUSA 54.1°). After the slide CCE's
heading still falls back (125° vs 144° at 3.0 s) and the replay still
hits the outside wall: in CCE the slide closes by the heading swinging
back, in DUSA by the direction of travel catching up.

Hot-patching: tools/hotpatch.py packs patch files into poke lists for the
debugger (64 per trigger).

## Recovery window after patch 12: physics agrees, the track does not

Forced, 2.0–3.2 s: heading step, heading and direction-of-travel changes
now agree tick for tick except at the ticks where an input changes (20 Hz
vs 30 Hz input sampling, interpolation). Integration inputs (front, yaw,
slip) agree to within a few units.

The remaining systematic difference is acceleration after the slide (CCE
10–30% more, 1.6–2.7 s). Its source is the slope force (DUSA +0xF4, CCE
+0xD8 = sin(slope) x 0x6400000 / 2, same code and constant), fed by the
slope angle (DUSA +0x1C, CCE +0x0C) that comes from the course data. At
the same places on the closed-loop path, CCE's slope is 1.5–3x DUSA's
through the exit of turn 3 and lasts ~0.5 s longer:

| t | DUSA (x, z) slope | CCE (x, z) slope |
|---|---|---|
| 1.00 s | (-264, 136) -651 | (-266, 138) -1055 |
| 1.50 s | (-292, 115) -1814 | (-294, 116) -2840 |
| 2.00 s | (-304, 83) -1696 | (-307, 83) -4129 |
| 2.50 s | (-297, 49) -244 | (-300, 49) -1775 |
| 2.75 s | (-286, 34) 0 | (-291, 34) -508 |

So Three Seven's turn 3 is shaped differently in CCE's course data. The
same inputs can't produce the same path past this point, whatever the
driving model; closed-loop replays here measure track + physics.

## Back straight manoeuvres (level road, same inputs, p1–12)

tools/manoeuvres.py: flick, weave, lift-off turn, brake-slide from the
*_bs_7s states (187 km/h). The road is level in both games here (slope 0;
DUSA shows brief 122–244 bumps). All four reach the wall at ~0.9–1.0 s, so
only the first ~0.8 s compares handling.

RMS vs DUSA over 45 frames (heading deg, slide deg, km/h, path units):

| | heading | slide | speed | path |
|---|---|---|---|---|
| flick | 2.8 | 1.1 | 0.8 | 1.19 |
| weave | 3.8 | 1.2 | 0.7 | 1.41 |
| lift | 2.4 | 1.0 | 1.5 | 1.18 |
| brakeslide | 3.2 | 1.7 | 3.0 | 1.09 |

Systematic differences:
- Turn-in: CCE's heading trails by ~3.5° from 0.3 s, then turns at the
  same rate (flick: 10.2 vs 14.1 at 0.3 s, 20.0 vs 23.3 at 0.5 s). In this
  run the press reached DUSA's tick at frame 3 and CCE's at frame 4; the
  wheel angle then trails by about one DUSA tick. Fitting the 30 Hz filter
  coefficients to DUSA's step responses (averaged over input phase) gives
  the decay-matched values already used for the ramp (0.097) and the wheel
  (0.357 vs 0.370), so the filters alone don't explain it.
- Brake-slide: CCE rotates ~8% slower (0.4–0.8 s: 32.4° vs 35.0°) with a
  smaller slide angle (22.7° vs 26.7° at 0.8 s).
- Weave: CCE ends the counter-steer at -8.2° vs DUSA -3.6°; DUSA then
  self-straightens (inside its 6° window), CCE is outside it and stays.

## Gentle back-straight manoeuvres, phase-averaged (p1–12 and after)

tools/manoeuvres.py adds tap (12-frame left), tap2 (left then right) and
bslide (short brake + turn + gas + countersteer), which stay off the walls
for ~1.3 s. Each is run at 3 input phases in DUSA (start offset 2/3/4
frames) and 2 in CCE, and averaged, so tick quantisation averages out.

Findings with p1–12:
- tap: DUSA ends at +10.8° (9.3–13.9), CCE +5.9° and then creeps back to
  +3.9°. CCE's turn builds more slowly over the first 0.2 s and stays inside
  the 6° straightening window, so the pull (40/tick) eats it; DUSA's heading
  leaves the window and holds.
- bslide: CCE rotates far less (34.8° vs 48.0° at 0.8 s) and its rear
  wheelspin stops at 0.47 s while DUSA's holds. The wheelspin gate
  (drive x (1 - rpm/cap) / (grip x rear limit) >= threshold) passed in DUSA
  and failed in CCE: CCE's denominator was ~1.6x DUSA's because its rear
  tyres had less lateral load.

Patch 13 (hornet_rear_stiffness.patch): CCE scales lateral force per axle
(per-car table 0604D2A0: Hornet front 0x320, rear 0x2BC); DUSA uses one
value for both (the rear target is a copy of the front). Rear set to 0x320.
bslide heading at 0.9 s: 36.9° -> 43.7° (DUSA 54.2°).

Patch 14 (wheelspin_thresholds.patch): Hornet's per-gear wheelspin
thresholds back to DUSA's (3rd 20971 -> 20480, 4th 23162 -> 21114).
Neutral on these runs.

Parked (patches/parked/grip_filter.*): converting the 1/4-per-tick grip
limit filter to 30 Hz (0.175) made bslide worse. With CCE's 1/4 at 30 Hz
the limits already track DUSA's closely, and DUSA's move even faster after
the brake release, so the targets differ (likely the braking force: CCE
loses 7 km/h vs DUSA 11 in the brake phase). Investigate before patching.

hotpatch.py now triggers at the tick body and its first two steps, so a
tick never runs half-patched code, and pokes the player car's copies of
patched per-car tables.
