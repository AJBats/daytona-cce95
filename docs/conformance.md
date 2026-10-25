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

## Why a quick tap turns CCE less (input timing)

Phase-averaged tap (12-frame left press), integrals over the run:
ramp DUSA -463 / CCE -341, front wheel 21393 / 15471, front+yaw-slip
6640 / 4458; heading change 2527 / 1418. The gap starts at the input.

- Per unit of time while held, the ramp, deadzone and wheel filter match
  (a 0.40 wheel coefficient instead of 0.37 changes little).
- With the press away from the playback's first frame (build/bs/tapd_*):
  CCE sees the 12-frame press for exactly 12 frames in both phases (press
  and release latency 2/2 and 3/3). DUSA sees it for 12, 15 and 15 frames
  over its three tick phases (press latency 3/2/1, release 3/5/4). DUSA's
  pad word (06063D98) itself holds LEFT for exactly 12 frames; the extra
  comes from where its 20 Hz car tick reads it. Over all phases DUSA turns
  a 12-frame tap into 4.67 steering ticks (14 frames) on average.
- A smaller turn also keeps CCE's heading inside the 6° straightening
  window, so the pull removes more of it.
- The playback tool's first event (frame 0) lands a frame late in CCE;
  scripts should press after frame 0.

So ~25% of the tap gap is DUSA's input sampling, not its physics.

## Patch 15: DUSA steering input timing (patches/steer_hold.patch)

DUSA's tick sees LEFT/RIGHT if held in any frame since its previous tick.
CCE's steering now gets the pad word OR'ed with the previous tick's word
(routine in the cave; pedals and gears untouched; one slot per key config,
two in all, so each player in 2-player play has their own hold).

12-frame tap, steering frames / ramp sum:

| | phases | frames | ramp sum |
|---|---|---|---|
| DUSA | 3 | 12, 15, 15 (14) | -405, -579, -579 (-521) |
| CCE before | 2 | 12, 12 | -392 |
| CCE patch 15 | 2 | 14, 14 | -506 |

Hot-patching note: the routine keeps state in the cave (two slots of key
config and previous word at 0603C5B8), so those words must not be re-poked
every tick.

In 2-player play (Three Seven, 12-frame LEFT tap on one pad after P2's
start lockout ends), each car steers for 14 frames with the same ramp
(-11 ... -57) and the other car doesn't move; the slots hold P1's key
config 0605273C and P2's 06052764.

## Patch 16: brake pedal (patches/brake_pedal.patch)

Straight-line braking on the back straight (btap: 12-frame brake tap,
bhold: 1 s), phase-averaged. DUSA's pedal: 0 -> 106 -> 212 -> 255 on press
and 255 -> 138 -> 0 on release (raw +40 per tick past 184, halving on
release, pedal = (raw - 56) x 255 / 96 clamped at raw 152). CCE: +32 per
tick clamped at 184, pedal / 128, so its pedal rose slower and dropped to 71
then 0. Patch 16: +27 per 30 Hz tick, DUSA's overshoot, release keeps 5/8
per tick, DUSA's pedal scaling.

| btap | DUSA | CCE before | CCE patch 16 |
|---|---|---|---|
| pedal at f8/f10/f12 | 71/141/212 | 32/95/159 | 36/107/179 |
| pedal at f20/f22/f24 (release) | 255/177/92 | 163/36/0 | 214/112/26 |
| speed lost at f30 | 11.3 km/h | 7.0 | 10.0 |

Full braking (bhold) was already equal (-55 km/h at 1 s in all three).

Still different: under full braking CCE's rear locks 2–4 frames earlier
(grip at f20: CCE 30710, DUSA 65536), and after a short tap DUSA's rear
locks briefly while CCE's doesn't. The rear grip limit drops faster in CCE
(the parked grip-limit filter conversion makes it track DUSA's:
86.4/87.7, 76.8/76.6 at f18/f20), but with it the lock never happens in
CCE at all, so the lock trigger itself still differs. Parked filter moved
to .org 06032A80 (06032A40 is now the steering hold).

## Replay scripts and patch 15

slide_replay_L3 places each steering release at the latest frame that
still reproduces the recording. DUSA reproduces the recording exactly with
every steering release up to 2 frames earlier (slide_replay_L3r2), but not
3; presses can't move 2 later. So the true releases lie within 2 frames
before the scripted ones, and with patch 15 a CCE replay of L3 holds the
steering ~1–2 frames longer than the player did. For CCE replays after
patch 15, steering releases should move 1 frame earlier (the expected
value).

## Patch 17: throttle input (patches/throttle.patch)

Under braking with the throttle released, CCE's engine drive collapsed from
frame 16 (DUSA: frame 28), so the rear's longitudinal demand rose and it
locked 2–4 frames early. Cause: the throttle raw value's release (slow -1
per tick above 176, then -raw/16 per tick) and press (+10/tick and a jump to
full at 160 in DUSA; +6/tick, no jump in CCE) are per-tick steps CCE kept
at 30 Hz. Patch 17 replaces the throttle function (cave routine; the call
literal 06036DEC is shared by all controller paths): +7 per tick with
DUSA's jump, the slow phase steps on two ticks of three, the fast phase
removes raw/24.

| bhold | DUSA | p16 | p17 |
|---|---|---|---|
| throttle at f18/f24/f30 | 243/239/217 | 197/145/0 | 239/209/173 |
| drive at f18/f24 (M) | 54.4/53.1 | 39.7/23.0 | 53.1/43.4 |
| grip at f18 | 65536 | 60103 | 65536 |

btap: CCE's rear now locks briefly after the tap as DUSA's does (grip at
f24 28450 vs 40016; before: no lock). Remaining offsets come from the
start state (CCE's throttle was at 251, DUSA's at 255).

Cave layout (dead function 06032918-06032AAF): rotation 06032918, wheel
filter 060329D8, steering hold 060329FC, throttle 06032A30-06032AAB.
tools/mkpatch.py writes each patches/<name>.patch from its .s source.

## Input hold for all car inputs; grip-limit filter adopted

DUSA's brake pedal starts releasing ~2 frames later than CCE's even with
patch 16: the same any-frame-since-last-tick input sampling as steering.
patches/steer_hold.s now hooks the first input function (throttle, via the
shared literal 06036DEC) and passes the OR'ed pad word on to throttle,
brake and steering (all three only read it). Steering is unchanged
(12-frame tap: 14 frames, ramp sum -506).

With patches 16-17, converting the grip-limit filter (patches/grip_filter.s,
1/4 per tick -> 0.175, in CCE's old throttle function at 06036FDE, now
unused) makes the rear limit follow DUSA's under braking (88.4, 78.0, 68.8
vs 86.5, 76.8, 68.0) and the rear lock on DUSA's frame:

| | DUSA | p17 | p17 + hold + grip filter |
|---|---|---|---|
| bhold grip f20/f22/f24 | 65536/50230/19618 | 40720/11744/11141 | 65536/42710/14750 |
| btap pedal f20/f22/f24 | 255/177/92 | 214/112/26 | 255/214/112 |
| btap speed lost at f30 | 11.3 | 9.0 | 11.0 |

Not matched: DUSA's brief rear lock right after a 12-frame tap (grip
52776 -> 40016); CCE's rear doesn't lock there now.

## Patch 20: wall contact (patches/wall.patch)

flick and lift run into the right-hand wall at ~0.9 s. Wall mode lasts 10
DUSA ticks and 15 CCE ticks (both 500 ms, already converted). Three
per-tick or per-car values were not:

- The impact speed factor for Hornet's category was x0.82 in CCE and x0.87
  in DUSA (cars 0-5). Restored to 0xDEB8. It applies once per impact, so
  no tick conversion is needed. The literal is shared by every CCE car in
  that category.
- The speed table (identical in both games) is indexed by the wall
  counter. Because CCE's counter is longer, its x0.7/x0.8/x0.9 steps
  landed 167 ms later than DUSA's at 50/100/150 ms. Now x0.8 lands at
  100 ms. x0.7 and x0.9 fall between CCE ticks, so each is split into two
  sqrt factors on the ticks either side.
- The heading turns toward the wall by angle/15 per tick, so CCE turned
  1.5x faster. The divisor is now 22.

The table is aligned on the impact: speed and heading are relative to the
frame before the wall counter is set. CCE uses phases 2 and 3.

| flick | DUSA | p19 | p20 |
|---|---|---|---|
| speed +4/+8/+10/+14 f | -25/-76/-100/-109 | -35/-34/-34/-34 | -25/-75/-100/-109 |
| heading at +30 f | -19.1 | -28.2/-30.2 | -19.3/-20.8 |

| lift | DUSA | p19 | p20 |
|---|---|---|---|
| speed +4/+8/+10/+14 f | -25/-77/-102/-112 | -35/-36/-37/-37 | -25/-77/-100/-111 |
| heading at +30 f | -23.7 | -41.1 | -27.2/-27.4 |

After the wall, the heading carried 6.4° in DUSA and -3.6° in CCE before
the patch; it is now 5.0°. lift still turns 3.6° more. Its rotation rate
matches (59 vs 62°/s), so the extra comes from the impact geometry.

tools/hotpatch.py now has a fourth trigger at 0604D388. A trigger at
0604D382, in the same 32-bit word as 0604D380, silenced the 0604D380
trigger.

## Turn 3 slope: same terrain, different pitch code

The slope difference at the turn 3 exit comes from code, not course data.

Test: CCE's car was teleported along DUSA's recorded path. A poke playback
at the CCE ground-contact routine (060386D8) wrote DUSA's x, z and heading
each tick. The routine then sampled the ground at exactly DUSA's points.

| DUSA frame | ground y DUSA / CCE | pitch DUSA / CCE | roll DUSA / CCE |
|---|---|---|---|
| 194 | 1.24 / 1.25 | -1055 / -1156 | -1893 / -3010 |
| 212 | 1.73 / 1.72 | -1497 / -2536 | -3598 / -3972 |
| 230 | 2.16 / 1.80 | -2011 / -4198 | -3233 / -3398 |
| 248 | 1.66 / 1.35 | -1696 / -4112 | -2784 / -2516 |
| 266 | 0.80 / 0.80 | -813 / -2401 | -3047 / -2439 |
| 284 | 0.11 / 0.19 | -40 / -569 | -1216 / -1317 |

The ground height agrees within the probe footprints, so the terrain is the
same. The pitch, which feeds the slope force, is up to 2.4x DUSA's.

How each game derives pitch (+0x1C DUSA, +0x0C CCE):

- DUSA (06005ECC): probes at the wheels, (+-0.55, +-1.4) in car space,
  plus a probe 12 units ahead. Pitch takes one of two forms:
  - atan((front avg - rear avg) / 2.8), wheels only.
  - atan((ahead probe - rear avg) / 13.4). DUSA uses this form throughout
    turn 3 (frames 150-320 of the replay) and the wheel form on flat road.
  Roll is atan(side difference / 1.1). Height is the mean of the 4 wheels.
- CCE (060386D8): probes at the body corners, radius 2.02 at +-63 deg
  front and 1.98 at +-114 deg rear. These are (+-0.92, +1.8) and
  (+-0.82, -1.8): DUSA's collision corners (06044670...), not its wheels.
  Pitch is atan((front avg - rear avg) / 7.2) with 0xC000 added.
  Height is the mean of the 4 corners.

There is no per-tick filter in either, so the fix is a code transplant,
not a 30 Hz conversion. Still to pin down: DUSA's branch condition
(060060EE-06006102: compares two stacked values, flag 0607EAD8 and car
+0x1EC >= 0xDC) and what its "ahead" value is. It read 0.1 for many ticks
while the rear wheels were at 2.48.

## Patch 21: ground contact DUSA's way (patches/ground_pitch.patch)

Two details of DUSA's routine, read from 06005ECC and checked in the
emulator:

- **The ahead point** is the ground height 12 units straight ahead along the
  heading: (0, 0, 12) rotated by the heading, then looked up on the track.
  At turn 3 the sliding car points at the infield, so the point lands on
  flat ground at 0.1, below the banked track.
- **The switch.** DUSA compares the ahead height with the car's ride height
  (the wheel mean):
  - If they differ, pitch uses the ahead form.
  - If they are equal, or the ahead point found no ground and so kept the
    ride height, pitch uses the wheel form. Both forms give the same pitch
    on flat road.
  - Exception: on course 1, from car +0x1EC >= 220, it always uses the
    wheel form. 0607EAD8 is the course index, and +0x1EC grows about once
    per 12 frames, like a progress counter.

The patch changes CCE's routine as follows:

- **Wheel probes:** moved to DUSA's wheels. Radius 1.504, at 0x0F40 either
  side of ahead and behind.
- **Ride height:** the mean of those 4 probes.
- **Baselines:** pitch 2.8 and roll 1.1.
- **Ahead point:** the pitch call goes through a cave routine (0603C304)
  that looks up the ahead point. The lookup goes through 06036B60, which
  picks the course's collision-grid half by z; the car's grid (+0x12C)
  could be the wrong half 12 units away.
- **Not transplanted:** the course-1 exception. CCE's course index and
  progress counter at that place aren't mapped yet.

Teleport test, CCE moved along DUSA's path:

| DUSA frame | y DUSA / before / patch | pitch DUSA / before / patch |
|---|---|---|
| 194 | 1.24 / 1.25 / 1.48 | -1055 / -1156 / -1176 |
| 212 | 1.73 / 1.72 / 2.14 | -1497 / -2536 / -1814 |
| 230 | 2.16 / 1.80 / 2.31 | -2011 / -4198 / -2148 |
| 248 | 1.66 / 1.35 / 1.74 | -1696 / -4112 / -1775 |
| 266 | 0.80 / 0.80 / 0.81 | -813 / -2401 / -894 |
| 284 | 0.11 / 0.19 / 0.11 | -40 / -569 / -40 |

At frame 230 the ahead point read 0.1 in both games, and the probes sat
exactly at DUSA's wheel positions (1.40 / 0.55). The remaining gap is in
the ground itself: CCE's height at the same points on the bank is up to
0.2 higher. DUSA's wheels read 1.435, 1.785, 2.543 and 2.893; CCE's read
1.512, 1.888, 2.753 and 3.092. This is the collision mesh, and it is the
only course-data difference seen so far.

Closed loop, from cce_p6_flying2. With patch 15's input hold, the old
script (slide_replay_cce2) spins and hits the wall at 2.9 s. The new
script (slide_replay_cce3) moves every steering release 1 frame earlier.
With it the slide recovers and the heading tracks DUSA's:

| t (s) | DUSA heading | CCE heading |
|---|---|---|
| 2.0 | -134.1 | -133.7 |
| 2.5 | -125.0 | -124.8 |

From 1.5 s, though, CCE's line runs 3-6 units wider (x -309.5 vs -304.1
at 2.0 s). That is higher up the bank, where the slope is steeper, so the
pitch along CCE's own path stays large: -3866 vs -1696 at 2.0 s. CCE also
carries 4-6 km/h more. CCE is already 2 units wide at 1.0 s and 4 km/h
faster at the brake point (313 vs 309), so the line difference starts
before the slope matters.

tools/hotpatch.py has a fifth trigger at 0604D390.

## Patch 22: default chase camera and lens (patches/camera.patch)

Both games build the view as offset + R(world - pivot) and project with
screen = k x X / Z.

| | DUSA (view 2) | CCE (view 2, before) |
|---|---|---|
| lens k | 160 | 224 (1.4x narrower) |
| pivot | car + 1.0 along camera yaw | car |
| offset | (0, 0, 5.5) | (0, -1.6, 7.0) |
| pitch | car pitch x 0.879 - 18.3 deg, smoothed 0.219 / 20 Hz tick | car pitch / 2 - 6.5 deg |
| roll | car roll x cos(cam yaw - heading), smoothed 1/2 per tick | car roll |
| yaw | travel + (heading - travel)/4 + lead, 1/2 per tick | same, 1/2 per 30 Hz tick |

Where the numbers come from:

- Lens: DUSA divides by Z with 0xA0 in its projection (06029E6E); CCE uses
  gbr+140 = 0xE0, set for the race in 06034CEC. The car's on-screen width
  confirms it. CCE's projection centre (VDP1 local 176,112) matched DUSA's
  in a level-pitch test (horizon within 2 px).
- Pivot, offset and pitch: 0600BB94 and 060053AC; distance 06063E24.
- Yaw: 0602CF96 (DUSA) and 06035EE8 (CCE) compute the same target.

The patch sets lens 160 for the race (the two-player split value is
kept), DUSA's view-2 offset and pitch, the pivot shift, DUSA's pitch and
roll rules with smoothing converted to 30 Hz (pitch keeps 0.848 of the gap
per tick, roll and yaw 0.630), in the cave at 0603C3B4 and a rewritten
camera-yaw function.

Result (turn 3 replay video, build/video/turn3_camera.mp4): the car's
size, the road and the slide framing now match DUSA closely.

Lens shift: DUSA's projection centre sits 127 lines below the top of its
3D frame; its first VDP1 command spans y -127.. On the TV that is line 143,
where CCE's (VDP1 local 176,112 plus an 8-line border) is line 120. The
patch moves CCE's 3D local origin to y 135; the HUD uses its own (0, 0)
locals and does not move. After the shift, the lane lines on the level
straight agree within 3%:

| row | DUSA lane width | CCE lane width |
|---|---|---|
| 120 | 156 | 161 |
| 128 | 198 | 206 |
| 136 | 239 | 245 |

CCE's car is drawn about 12% wider than DUSA's at the same spot (118 vs
105 px). Since the road matches, this is the car model, not the camera.

Still open:
- Views 0, 1 and 3, replay cameras and the background scroll are
  unchanged and now use the wider lens.
- A fresh race start has not been checked yet: that the race init copies
  the new view-2 table into the camera.

tools/hotpatch.py: triggers added at 0604D39C and 0604D3A8. Cave state
words (SKIP) are written once after a state loads (`once` line; handled by
tools/record_replay.py) instead of never.

## Car model size (research, not patched)

Model-to-world scale was read from each game's matrix while it draws the
player's car:

- DUSA: slave-CPU transform 06032158, matrix 0608A590.
- CCE: 060463E4, matrix rows at gbr+0x200/0x210/0x220.

The units:

- DUSA's matrix has unit columns and 16.16 vertices, so model units are
  world units.
- CCE's has columns of 64.0 and 16-bit vertices, so model units are 1/1024
  of a world unit.

Both matrices carry the same car-origin translation, (0, -0.3137, 4.5506).
So with patch 22 the two cameras sit identically relative to the car.

| Hornet (world units) | DUSA (060F9E24, 143 vertices) | CCE (PLCAR01 +0x2444, 138 vertices) |
|---|---|---|
| width | 1.766 | 1.885 (+6.7%) |
| length | 4.922 | 5.035 (+2.3%) |
| body sill / roof | 0.172 / 1.32 | 0.129 / 1.28 |

Each game's player car was identified by its draw:

- DUSA: zeroing the model's x coordinates in RAM left only the wheels and
  shadow.
- CCE: the projection loop's vertex reads.

DUSA's one vertex at y = 0.0 is a single centre point. CCE's body sits
0.04 lower and its roof 0.04 lower, so the model doesn't explain the car
looking higher on screen.

## Camera: over-culling from the new camera (patch 22 follow-up)

Pieces of the Sonic mountain wall (replay frames ~98-113) and of the
mountain above the right-hand wall (~206-221) vanished with the new camera
and showed sky. Still frames at replay frame 211 isolate the cause:

| Setup | Mountain above the wall |
|---|---|
| new camera | partly missing |
| old camera, with or without the 160 lens | complete |
| new camera at distance 7.0 | mostly back |

CCE culls in two stages:

1. **Track blocks near the camera.** It takes a window of blocks starting
   at the track area containing a camera point (camera +0x20, used only for
   this; 0602A6EC). With the new camera one area number moves on (0xCD to
   0xCE) and one block drops out. Feeding the old point back restores it,
   but the frame is pixel-identical: that block is behind the camera.
   Left as is.
2. **Per-block frustum test** (0602A9F0 -> 06047670). It projects the
   block's four corners at the car's height and drops the block when all
   of them fall outside +-176 x +-112 of the projection centre (render
   context +0x18). With DUSA's lens shift the screen reaches 135 lines
   above the centre, so blocks whose corners sit in the top 23 lines were
   dropped. This was the visible pop-in. The half-height is now 135 (both
   render contexts), and the re-recorded replay shows no holes at either
   spot.

## Camera: race-start handover

A fresh race showed the wrong chase framing until a view switch. The cause
is CCE's scripted cameras (the rolling-start intro, the reset at
0603072A): they write CCE's old view-2 offset (0, -1.6, 7.0) directly into
the camera, from literals and from the intro's keyframe tables. The view
table, now DUSA's (0, 0, 5.5), is only copied in during a view switch.

Outside view switches, the chase routine now eases the offset to the
current view's table entry, 1/8 per tick. After the intro the camera
settles on DUSA's framing within about 0.4 s, before the "3" of the
countdown, and stays there. Checked by booting the disc fresh into an
arcade race.

## Manual-shift drift at turn 3: DUSA trials

The user drove Time Lap laps on manual in DUSA (build/dusa_manual_laps.bin,
whole car struct per frame; inputs in build/dusa_manual_laps_inputs_m1.txt
from build/states/dusa_manual_laps_start.mcs). Replaying those inputs from
the state reproduces the recording exactly once every event is moved one
frame earlier than the trace logged it.

Three turn-3 passes are cut into trials: build/states/dusa_manual_t3_trialN.mcs
plus build/dusa_manual_t3_trialN.txt (built by build/cut_trials.py), each
starting about 3.5 s before the corner. Each one replays exactly for 600
frames.

Gear values (+0xDC DUSA, +0x17A CCE) are 0–3 for gears 1–4. The user's
pad layouts: DUSA R accelerate, Z 1st, B 3rd, Y 4th; CCE B accelerate,
X/Y/Z/C gears 1–4. The technique is the arcade H-shifter drift: from 4th
at 325 km/h, straight to 1st, then 3rd, then 4th, with steering taps and
no brake. Frames are relative to the car crossing x = -150 (60 Hz frames).

| | DUSA t1 | t2 | t3 | CCE t1 | t2 | t3 | t4 |
|---|---|---|---|---|---|---|---|
| 1st gear pressed | 26 | 31 | 31 | 23 | 23 | 18 | 25 |
| 3rd gear pressed | 68 | 70 | 72 | 67 | 74 | 69 | 87 |
| 4th gear pressed | 139 | 142 | 144 | 187 | 189 | 195 | 184 |
| minimum speed (km/h) | 274 | 279 | 275 | 282 | 280 | 273 | 265 |
| peak slide angle | 35.8° | 34.5° | 35.6° | 39.0° | 40.6° | 37.2° | 34.7° |
| heading change, 0–260 | 151.2° | 149.8° | 149.7° | 154.2° | 150.0° | 149.8° | 150.7° |

Both games reach the corner in the same state (324–325 km/h, within 2
units laterally). The user's own CCE drifts match DUSA's closely, except
that the user stays in 3rd about 0.8 s longer in CCE.

CCE trials: build/states/cce_manual_t3_trialN.mcs plus
build/cce_manual_t3_trialN.txt (build/cut_cce_trials.py, from
build/cce_manual_laps.bin). Unlike DUSA, CCE's trace replays exactly
without the one-frame shift. All four reproduce exactly for 600 frames.

### DUSA inputs driven into CCE

build/dusa2cce_t3_trialN.txt: each DUSA trial's buttons mapped by function
and shifted so the x = -150 crossing lines up, played from the CCE trial
state with the closest entry line (t1 and t2 from CCE state 4, t3 from 3).
Open loop, so small differences grow.

- Slide build-up matches: DUSA t3 / CCE slide angle 11.4°/11.2° at frame
  60, 29.9°/30.0° at 80, 34.0°/32.8° at 100.
- CCE loses less speed in 1st gear: 285 vs 299 km/h at frame 74, then a
  steady 7–10 km/h more through the corner.
- CCE's slide unwinds more slowly on the exit (frame 160: 13.3° vs 18.7°;
  200: 3.1° vs 8.7°), matching the user holding 3rd longer in CCE.
- t1 and t2 run wide and hit the outer wall in CCE (speed drops to ~200
  and ~240); t3 completes the corner, within 3° of DUSA's heading through
  the slide.

Lead for the speed gap: in 1st gear (rpm at the 8500 cap) DUSA's +0x84
reads 255 for about 18 frames (56–74 in t3) with no brake pressed, while
the speed drops fast; CCE's matching field (+0x90) shows only one-frame
blips at the shifts. This looks like over-rev engine braking in DUSA's
gearbox (row 11, not yet converted).

## Patch 23: gearbox timing (patches/gearbox.patch)

The manual gearbox is the same code in both games (DUSA 0602F270, CCE
0604D94C) with retuned numbers:

- Shift timer (DUSA +0xD8, CCE +0xB8): +N on an upshift, -N on a
  downshift, one step per tick towards 0. DUSA N = 5, CCE N = 16.
- While the timer is negative, rpm is driven from an overshoot value
  (DUSA +0xC4 = new rpm + 1250, -250 per tick; CCE +0xA4, +4000), so the
  rev-limit check can't fire. Once the timer is 0, rpm at the 8500 limit
  sets the brake pedal to 255 every tick: the engine braking that scrubs
  speed after the drop into 1st. (A positive timer also stops 0602CBC4 /
  06035A42 arming a timer, +0x152, that nothing reads; wheelspin itself is
  not gated by it.)
- The engine-rpm follow (+0xE4 / +0xD4, tach and sound; torque uses the
  clamped rpm) uses per-gear step limits per tick, not rescaled in CCE.

So in CCE the rev-limit brake started 34 frames after the downshift instead
of DUSA's 18, and the 3rd-gear shift came first, which explains the
1st-gear speed gap. Converted: N = 8 (the brake starts N + 1 ticks after
the shift: DUSA 6 x 3 = 18 frames, CCE 9 x 2 = 18), overshoot +1250
falling 156 per tick, follow steps x 2/3. Auto uses the same timer
(16 -> 8).

DUSA inputs in CCE, before -> after (frames from x = -150):

| | DUSA | CCE before | CCE after |
|---|---|---|---|
| t1 rev-limit brake | 48–72 | 60–72 | 48–72 |
| t1 speed at frame 72 | 278 | 293 | 277 |
| t1 path, max distance from DUSA | – | hits the wall | 5.0 units |
| t2 speed at frame 72 | 286 | 302 | 285 |
| t2 path, max distance from DUSA | – | hits the wall | 6.5 units |
| t3 speed at frame 72 | 285 | 302 | 285 |
| t3 path | – | completes, 14 units off | 10 units off at 240, then touches the wall |

Speeds now match within 1–2 km/h through the corner in all three. t3's
slide unwinds a little faster than DUSA's after frame 100 (frame 160:
10.2° vs 13.3°), so it comes out 4–7° less rotated and touches the outer
wall at the exit; open loop, small differences grow.

## Turn-3 exit: input phase, not unwind

After patch 23, t3's slide looked like it unwound early. Replaying each
trial with every input moved one frame earlier or later (build/phase.py;
scripts dusa2cce_t3_trialN{m,p}.txt) shows the outcome depends on input
phase as much as on anything else. Slide-angle error vs DUSA over frames
60–200, and the largest distance from DUSA's path:

| | -1 frame | as cut | +1 frame |
|---|---|---|---|
| t1 | 3.4° rms, 17.5 (wall) | 1.1°, 5.4 | 4.3°, 23.6 (wall) |
| t2 | 2.0°, 6.0 | 1.8°, 7.8 | 2.1°, 8.8 |
| t3 | 1.5°, 4.1 | 3.2°, 11.8 (wall) | 1.8°, 8.1 |

Each trial has a phase that tracks DUSA within 1–2° and 4–6 units. Mean
slide error over all nine runs is -1.1° (CCE slightly less sideways). A
one-frame shift moves a steering tap across CCE's 2-frame tick, which
changes how many ticks see it, and turn 3 is chaotic enough to amplify
that. So the exit has no systematic unwind difference to fix; comparisons
here should average over input phases.

Open: DUSA punishes a low-speed peel-out after a bad corner more than CCE
(see Peel-outs below).

## User's CCE laps after patch 23

build/cce_gb_laps.bin (from build/states/cce_gb_laps_start.mcs, trace
build/cce_gb_laps_trace_full.txt; summary by build/laps_cmp.py): ten turn-3
passes on the fully patched disc. Gear presses in frames from x = -150:

| pass | 1st | 3rd | 4th | min km/h | peak slide | km/h at 260 |
|---|---|---|---|---|---|---|
| 1 | 20 | 60 | 148 | 274 | 31.4° | 284 |
| 2 | 39 | 72 | 183 | 283 | 38.4° | 289 |
| 3 | 30 | 61 | 115 | 282 | 35.0° | 294 |
| 4 (entered at 310, wall) | 35 | 60 | 129 | 234 | 26.5° | 242 |
| 5 | 33 | 71 | 155 | 281 | 35.5° | 290 |
| 6 | 24 | 66 | 172 | 272 | 40.9° | 281 |
| 7 | 33 | 75 | 135 | 277 | 41.6° | 288 |
| 8 | 33 | 67 | 121 | 283 | 35.6° | 294 |
| 9 | 30 | 72 | 123 | 276 | 40.7° | 288 |
| 10 | 30 | 67 | 138 | 281 | 36.7° | 292 |
| DUSA (3) | 26–31 | 68–72 | 139–144 | 274–279 | 34.5–35.8° | 284–289 |

Before patch 23 the user held 3rd until frame 184–195 in CCE; now 115–183,
and 121–138 over the last four passes, at or just ahead of DUSA. Speeds
match DUSA's range. Peak slide is 31–42° (clean passes average 37°) against
DUSA's 35°, from three DUSA samples only.

## Peel-outs (wheelspin onsets)

Session: build/dusa_peel_trace.txt, a DUSA boot-to-pause input trace. Replayed
from a fresh boot with every event one frame earlier, it reproduces the
paused state exactly, so build/dusa_peel_m1.bin is the whole session's car
struct. A wheelspin onset is +0x110 (DUSA) / +0x100 (CCE) going positive.

Onset rule (DUSA 0602CCEC, CCE 06035B30): spin is injected when
threshold / (drive x (1 - rpm/8500) / (grip x rear limit)) drops below
1.0 (stored at DUSA +0x264, CCE +0x144) and the grip-event timer (DUSA
+0x16C, CCE +0x184) isn't running. There is no shift-timer check on this
path (the shift-timer check at 0602CBC4 only arms an unused timer, +0x152).

DUSA onsets in the session, frames from the turn-3 x = -150 crossing:

| | when | km/h, gear, rpm | spin length |
|---|---|---|---|
| rolling-start handover | (before the corner) | 302, 4th, 6871 | 99 frames |
| drop to 1st at turn 3 | 36 | 325, 1st, 7566 | 36 |
| early upshift to 4th after the botched corner | 201 | 193, 4th, 4513 | 267 |
| 4th at low speed, steering | 474 | 101, 4th, 2948 | 60 |

Rolling start: DUSA's car struct physics fields are all 0 during the
rolling start; at the handover the grip limits start from 0 and filter up,
so with the throttle held the first ticks' ratio is huge and the rear spins
(the tyre smoke at the start). CCE's car appears at the handover with the
limits already at steady values (rear 0x8000000) and the pedals are ignored
for about 90 frames, so it never spins. A difference in the start
sequence, not in the physics.

The DUSA inputs from the corner on, mapped to CCE (build/dusa2cce_peel*.txt,
from CCE turn-3 states 4 and 1 with patch 23 hot-poked):

- Drop to 1st: identical onset (frame 36) and length (36 frames).
- Early upshift: CCE also peels out, but at frames 222–250 instead of 201
  (lengths 210–370 vs 267); one input phase spins at 124 in 2nd instead.
  At the upshift CCE's ratio is 1.05 (DUSA 0.95): grip x rear limit is ~9%
  higher in CCE at that moment (27940 x 2382 vs 26213 x 2332), so it misses
  the threshold until the slide loads the rear further.
- By frame 474 the CCE paths are 30+ units away from DUSA's, so the
  low-speed onset can't be compared from this replay.

### State forcing at the early-upshift peel-out

DUSA's peel-out session state was forced into CCE every tick from 0.8 s
before the upshift (build/peel_forced.csv from build/dusa_peel_pad2.bin, the
session recording with two leading frames so DUSA's ticks fall on frames
== 2 mod 3 as teacher.py expects; offset 3529, first tick 331, from CCE
turn-3 state 4 with the DUSA inputs playing; patch 23 poked at 0604D388).

- Given DUSA's state, CCE's spin onset fires on the upshift too, one tick
  earlier than DUSA (rel 202 vs 204), with the same spin size (31894 vs
  31388) and ratio (60807 vs 62465). The onset formula, thresholds,
  grip-limit targets and clamps (DUSA 0602C690 / CCE 060354A0, same code
  with the 2.25 load-transfer and 4/9 slope conversions) agree.
- So the late onset in the open-loop replays comes from the state CCE
  arrives in, not from the onset code. Per-tick sources of divergence in
  this window: a steering tap that CCE's wheel angle picks up a tick late
  (input sampling, as at turn 3), and a 4-tick stretch at rel 190–198
  (1st gear on the limiter, steering -90, 196 km/h) where CCE's slide rate
  (+0x104 x 1.5) is 220–320 per tick against DUSA's -90 to 60.
- Forced per-tick RMS over the window: slide rate 176, heading step 52,
  slip 93, yaw 151, travel 130, lateral force 21M, grip 3212.

## Patch 24: rear rotation clamp at 30 Hz (patches/rotation_clamp.s)

Register logs of the core step at the slide-rate update (DUSA 0602D618,
CCE 06036138; CCE with DUSA's state forced, peel-out window) split the
slide rate into its two terms: rate = r10 - r11.

- r10 (front/steering term): CCE x 1.5 matches DUSA (RMS error 47).
- r11 = -(3 x rear rotation term, clamped so it never exceeds the slip
  angle). Unclamped ticks match (-486 vs -486, -976 vs -975). Clamped
  ticks are 1.5x DUSA's (-1042 vs -738, -1371 vs -931): the rotation term
  is per tick, but the clamp is the slip angle, unscaled, so at 30 Hz CCE
  could straighten 1.5x as fast as DUSA whenever the clamp applied.

Fix: clamp to 2/3 of the slip angle (rounded away from zero, so a slip of
one unit still straightens; rounding to zero left a permanent tiny slip
that kept the car off the straightening path).

Forced per-tick RMS vs DUSA (state forced every tick):

| | peel-out window, before | after | turn-3 trial 1 (rel 0–450), before | after |
|---|---|---|---|---|
| slide rate | 176.0 | 90.9 | 89.2 | 56.1 |
| slip | 92.5 | 39.0 | 46.3 | 28.3 |
| travel | 129.7 | 100.0 | 75.8 | 67.8 |
| heading step | 52.2 | 53.5 | 47.9 | 46.3 |
| lateral force (M) | 21.3 | 16.3 | 16.1 | 14.1 |

Open loop, DUSA's peel-out inputs in CCE (4 runs): the early-upshift
peel-out now starts at frames 199–202 (DUSA 201), 193–195 km/h (193), rpm
4503–4548 (4513), steering -94/-95 (-96), lasting 264–417 frames (267).
Before: 222–250, and two runs spun the other way.

Turn-3 DUSA trials open loop: t2 and t3 stay close (slide error 1.9–2.8°
rms, paths within 7.5–17.9 units, against 1.5–3.2° and 4.1–11.8 before).
t1 now runs wide into the wall in two of its three input phases. Cause: its
opening steering tap. CCE sees the 5-frame tap for 4 ticks (the input hold,
patch 15) where DUSA saw 2, so the heading rises 944 (patch 23 only) or
1169 (with patch 24) against DUSA's 737. 1169 is just past the 6-degree
(1092) self-straightening window, so the heading never comes back. The
tap response sits on that edge; it's input sampling, not this clamp.

Note on the replay method: after load_state, CCE's tick phase relative to
the input playback varies by one frame from run to run, so the "input
phase" variants sample tick phases at random rather than in order.

## Donuts and patch 25: slip angle limits (patches/slip_limit.patch)

Session: build/dusa_donut_trace.txt (DUSA boot trace; replayed from boot
with events one frame earlier it reproduces the end state exactly,
build/dusa_donut.bin). The user's donuts: full lock, full throttle, 1st
gear, 30-68 km/h, 170-270 deg/s, slide angle 62-69 degrees, rear spinning
(grip 0.17).

Test states: both games stopped on the track after turn 3 after braking
from the rolling-start handover (build/states/dusa_stopped_manual.mcs,
cce_stopped_manual.mcs; scripts build/dusa_stop_script.txt,
cce_stop_script.txt). Donut script: 1st gear, full throttle and full left
lock for 50 s (build/donutL_*.txt).

State forcing on DUSA's steady donut: DUSA's slip sits on -0x3400 every
tick; CCE's goes on to -13600..-13760 and its heading step comes out 1.17x
DUSA's. The slip clamp at the end of the core step (CCE 060362A4, DUSA
0602D76A) is ±0x3600 in CCE against DUSA's ±0x3400, and the spin-out
flags (+0x30 bits 0x40000000 with 0x10000000/0x20000000, above 65 km/h)
fire at ±0x3400 against DUSA's ±0x3280. Both are angles: restored to
DUSA's values. Forced heading step then 0.98x DUSA's, slip equal.

Open-loop 50 s donut from standstill:

| | DUSA | CCE before | CCE patch 25 |
|---|---|---|---|
| 3 s | 51 km/h, 271 deg/s, 66 deg | 50, 279, 70 | 50, 263, 66 |
| 9 s | 43, 273, 64 | 41, 291, 68 | 41, 273, 63 |
| 21 s | 34, 257, 62 | 32, 262, 66 | 32, 251, 62 |
| 41 s | 34, 255, 62 | 32, 263, 66 | 33, 250, 62 |

A donut from a clean start was already close; the slide angle and spin
rate now match. Released from DUSA's forced donut state, CCE keeps the
donut and its speed decays like DUSA's.

## Camera: lens after a pit stop

After a pit stop the car looked too big and view switches didn't fix it:
the lens (render context +0x8C) went back to CCE's 0xE0. A log of lens
writes from a pit-entry state (build/states/cce_pit_entry.mcs, unpause and
the car takes the pit lane) shows the write at 06038168, in the car's state
handler: it sets the race lens again (0x80 in two-player split, else 0xE0)
when the pit lane takes the car over; 0603827C does the same in another
state. Both literals (06038252, 06038378) now hold 0xA0 like the race start
(patches/camera.s). Replayed from the pit-entry state, the lens stays 0xA0
through the whole pit stop and exit.

## Patch 26: the other cars (patches/car_rescale.patch, tools/car_rescale.py)

The Hornet's per-car values are DUSA's; DUSA has no counterparts for CCE's
other 13 cars. Each of their values now keeps its CCE ratio to the
Hornet's: new = CCE value x (Hornet DUSA-converted / Hornet CCE).

- Rotation gains (0604D1CC): x 1.430, e.g. car 10 0x700 -> 0xA02.
- Rear stiffness (0604D2A4): x 8/7, e.g. car 4 550 -> 628.6.
- Wheelspin thresholds (0604D310): all cars shared CCE's row, so all now
  have DUSA's.
- Grip-limit filter: cars on CCE's other slide path (+0x1CB != 2) used 1/16
  per tick against the Hornet path's 1/4; now 0.1747 / 4 = 0.0437
  (patches/grip_filter.s).

Not measured yet; only the Hornet has been compared with DUSA. To check:
the largest gains (cars 8 and 10) make the rotation term's numerator about
1.9x the Hornet's, so watch for overflow in CCE's atan2 (06047E0C) at low
speed with large grip.

## Turns 1-2 banks: the car rocks against the camera (2026-10-24)

The user saw the car jitter through Three Seven's banked turns 1 and 2, as
if it rotated to fit the road while the camera didn't follow. Both runs are
the user's own, flat out at 250-310 km/h, each between two pauses:
build/snd/take_cce_t12.txt (frames 5896-6497) and take_dusa_t12.txt
(1349-2062). Per-frame traces are in build/camera.

- **Timing is not it.** Car and camera update every 2 frames in CCE95 and
  every 3 in DUSA, without a miss, and the 3D image changes on the same
  beat in a frame-by-frame video. Each game holds one image a frame long at
  turn 1.
- **Car roll against the camera.** On the banks, car roll minus camera roll
  is 1.26 deg rms (max 4.9) in CCE95 and 0.76 (max 1.8) in DUSA. CCE95's
  car roll reverses direction 39 times through the two corners, DUSA's 13.
- **The pattern.** On a bank entry CCE95's roll repeats a 3-tick cycle:
  about -2 deg, then +0.44 and +0.44 back (~10 Hz). DUSA's roll only
  steps one way. The camera eases toward the car's roll, so in CCE95 the
  car rocks against the view. CCE95 also banks deeper at the deepest part
  of each corner: -20 and -21.5 deg against DUSA's -17.5.
- **The roll is unfiltered.** CCE writes it once a tick at 06038A6C:
  0x4000 - atan2(wheel side difference, 1.1), the ground contact of patch
  21, straight from the ground heights under the wheels.

Each game's ground was run on the other's exact path, with a poke playback
of x, z and heading at the ground contact. CCE: 060386D8. DUSA: 0600E606,
the player's call into 06005ECC; it fires twice a tick, so each row is
written twice.

- **DUSA's ground on CCE95's line:** clean steps, no rocking (DUSA's own
  20 Hz staircase), and -17.4 deg at the deepest bank. CCE95 on the same
  line rocks and reaches -21.4 (build/camera/t12_teleport_dusa.png).
- **CCE's ground on DUSA's line:** close to DUSA's roll for most of the
  way, but -21.3 deg against -17.4 for ~0.6 s at turn 1's deepest bank,
  and 0.1-0.3 units higher (build/camera/t12_teleport.png).

So it is the ground CCE reads on the banks, not the driving or the camera.

### The lookups are the same; the meshes are not

Both games find the ground the same way:

- A 64 x 64 grid of 32-unit cells, each with a list of polygons.
- The first polygon in the list that contains the point wins.
- The height comes from that polygon's plane. Nothing is interpolated or
  filtered.

| | DUSA | CCE |
|---|---|---|
| Lookup | cell 06006838, polygon and plane 06027EDE | 06036AA8 -> 06036A70 (cell 060368D4, polygon 06036990, plane 06036914) |
| Data | COURSE0.BIN: 504 polygons, grid at +0x6660, lists at +0xA660 (RAM 060A6000 / 060C2000 / 060BF000) | CS0_COL.BIN, loaded as is at 00220000: two grids (z >= 0 and z < 0, identical for Three Seven), 1325 polygons at 00228000, lists from 00238D24 |
| Polygon, 0x34 bytes | flags, plane y = a x + b z + c, four edge lines (slope, offset, flag bits for "+ z" and "negate") | flags (type << 16, bit 0 triangle), four (x, z) corners in 12.20, normal (x, y, z) in 8.24 and D: y = 4D/Ny - (Nx x + Nz z)/Ny |

The difference is the data. CCE re-meshed the track (build/camera/t12_mesh.png):

- **DUSA's banks:** 16-unit sections, each split into two triangles.
  Neighbours meet within 0.002 units. The roll the wheels read holds within
  a triangle and steps at its edges: DUSA's staircase.
- **CCE's banks:** 8-unit quads in two strips across the bank. Each quad's
  plane is a fit to a twisted patch, so neighbours meet at one corner and
  are 0.11-0.13 apart at the other. For example, at the seam between
  polygons 1141 and 1130, (67.17, -179.12), both read 1.030. At
  (59.11, -176.76) they read 0.867 and 0.746.
- **The rocking.** CCE95's line through turn 1 runs along the seam between
  the two strips. The left wheels read one plane and the right wheels the
  other, and the gap between them changes along each 8-unit quad. At 280
  km/h a quad passes in 3 ticks, which is the 3-tick sawtooth.

A Python copy of each game's lookup (run on RAM dumps) gives the game's own
roll along CCE95's path within 0.1 deg.

The surface types line up one to one. Each CCE polygon's centre falls on a
DUSA polygon of the matching kind:

| CCE type | DUSA flags | Count |
|---|---|---|
| 1, road | 01 | 848 |
| 1, road | 41 | 3 |
| 4, apron | 02 | 132 |
| 3, grass | 04 | 104 |
| 0, wall strip | 80 | 228 |

Some types have no clean match:

- **CCE type 0 (wall strips).** These are vertical (Ny = 0), 10 units wide,
  along the outside edges. Their "height" is a ramp from the edge
  (06036948). DUSA's 80 polygons in the same places are sloped ground.
- **CCE type 2.** One patch on the main straight (x -45.75 to -23.25,
  z 134-155, flat) is ordinary road in DUSA. Its use is unknown.

In 90 frames of racing, every read of CS0_COL.BIN came from the lookup
(060368D4-06036A9A, a read profile of 00220000-0023B604). So the file can
be rebuilt freely in the same format.

### DUSA's ground under Three Seven (tools/col_convert.py)

`make disc` rebuilds CS0_COL.BIN from DUSA's COURSE0.BIN. Each cell's list
holds, in order (the first polygon that holds the point wins):

1. CCE's 228 wall strips and its 6 type-2 polygons, unchanged.
2. DUSA's road, apron and grass, as types 1, 4 and 3: 341 polygons.
3. DUSA's 163 polygons outside the track edges, as road. These only show
   through where nothing above lies: slivers between DUSA's road edge and
   CCE's walls (CCE had road there, 114 square units in all) and the ground
   beyond the walls.

Each DUSA polygon's corners come from where its edge lines meet. Corners
shared between polygons are snapped to one value, so neighbours share their
edges exactly. The planes become CCE's normal and D. The file is 75 KB of
the 112 KB slot, padded.

Checks:

- **Offline.** A copy of CCE's lookup on the new file, against DUSA's
  lookup on COURSE0.BIN, on a 0.5-unit grid over the whole course: the
  same surface type everywhere, and heights within 0.006 units. The only
  differences are on polygon edges, where the two lookups pick different
  neighbours. No point that had ground in CCE's file lost it.
- **In the game.** The new disc's race RAM at 00220000 holds the file. The
  user's turn 1-2 take (build/snd/take_cce_t12.txt), replayed from take
  frame 5980 with the new file, was compared with DUSA's own run through
  the same corners. Input phase 0 replays the old file exactly:

| Turns 1-2 (x > 0, z < -100) | CCE's ground | DUSA's ground in CCE95 | DUSA |
|---|---|---|---|
| Car-camera roll rms (deg) | 1.06 | 0.83 | 0.71 |
| Car-camera roll max (deg) | 3.10 | 2.08 | 1.70 |
| Roll reversals | 27 | 13 | 11 |
| Deepest roll (deg) | -19.9 | -17.1 | -17.4 |

- **Matches DUSA's surface.** On the new file, the game's roll along its
  own path matches the roll of DUSA's ground, worked out offline at the
  same wheel positions: within 0.12 deg for 95% of ticks. The larger
  differences are where a wheel reaches a kept CCE wall strip.
- **Turn 2 (x ~ 300).** The car-camera roll is still 1.47 rms against
  DUSA's 0.77. That is the line, not the ground: the CCE95 take turns in
  at x ~ 298, low and late, and rolls in at 2-4 deg a tick. DUSA's run
  sweeps in wide at x 305-310 and rolls in 1.5-2 deg a tick.
- **The whole take** (14766 frames) ran on the new disc from a new state,
  cce95_col_5000 (car struct equal to cce95_tyres2_5000's). The first lap
  follows the old path within 0.05 units, the car 0.07-0.15 lower on the
  banks, with the same three wall scrapes at turn 1. After that the
  closed-loop replay drifts off the user's line, as expected on a
  different ground.

Not converted yet: Dinosaur Canyon (CS1_COL.BIN, CS12_COL.BIN) and Seaside
Street Galaxy (CS2_COL.BIN). Seaside's two grids differ: they split at
z = 38 (0604E1DC). DUSA handles the same crossing with a cell list keyed
by progress (06061270, car +0x1EC <= 70).

### Turn 3 on DUSA's ground

This repeats two earlier turn-3 tests, once on CCE's ground and once on the
new file. For the new file, the converted CS0_COL.BIN was poked into the
state's RAM; the code in the states is the current build's. Plots:
build/camera/t3_new_ground.png.

**Ground only.** CCE95's ground contact was fed DUSA's turn-3 path each
tick (x, z and heading poked at 060386D8, from cce_turn3_alignedb), as in
the patch 21 test. Over k 100-500, the 200 ticks on the bank:

| | CCE's ground | DUSA's ground |
|---|---|---|
| Height - DUSA's, mean / max | +0.080 / 0.454 | -0.002 / 0.059 |
| Pitch error rms / max (deg) | 0.58 / 2.17 | 0.09 / 0.48 |
| Roll error rms / max (deg) | 1.41 / 5.89 | 0.33 / 2.02 |

That closes patch 21's leftover gap. CCE's bank read higher, and its pitch
ran up to 2 deg steeper mid-corner. With DUSA's ground, height and pitch
match DUSA's and roll follows DUSA's steps. The roll residue is when each
game's tick lands, not the ground.

**DUSA's buttons in CCE95** (cce_turn3_alignedb, script_t3_dusa2cce.txt
moved by each phase; the same test as docs/tyre_sound.md, "Turn 3 with the
same inputs"). Error against DUSA over k 0-560; slide angle over k 60-400:

| Ground, phase | Path max / rms (units) | Heading rms | Slide rms | Mean km/h - DUSA | Wall hit at k |
|---|---|---|---|---|---|
| CCE's, -2 | 143.0 / 48.6 | 10.5 | 9.91 | -52.6 | 376 |
| CCE's, -1 | 42.2 / 15.8 | 5.4 | 3.46 | -14.3 | 376 |
| CCE's, 0 | 125.5 / 43.4 | 7.0 | 5.82 | -44.7 | 380 |
| CCE's, +1 | 3.2 / 1.7 | 1.4 | 1.25 | +1.0 | none |
| CCE's, +2 | 51.6 / 19.0 | 5.7 | 2.64 | -13.7 | 394 |
| DUSA's, -2 | 168.6 / 54.5 | 15.2 | 13.64 | -62.5 | 380 |
| DUSA's, -1 | 37.4 / 12.1 | 3.8 | 1.65 | -12.5 | 438 |
| DUSA's, 0 | 125.5 / 43.5 | 7.0 | 5.74 | -44.7 | 380 |
| DUSA's, +1 | 4.1 / 1.8 | 1.2 | 1.18 | +0.8 | none |
| DUSA's, +2 | 32.4 / 11.4 | 4.6 | 2.03 | -0.9 | none |

- **The phase that tracks still tracks.** At +1 the run stays within about
  4 units of DUSA's path through the whole corner. Slide angle, heading
  and speed are as close as before, so the handling fit made on CCE's
  ground holds.
- **Near misses get closer.** Phases -1 and +2 now stay nearer DUSA's path
  through the exit. +2 no longer hits the wall and keeps DUSA's speed; -1
  hits it 60 frames later.
- **Early splits don't change.** Phases -2 and 0 split off before the exit
  on either ground. That is the input-phase effect at the slide's catch.
- **Peak slide is 62-64 deg in every run,** against DUSA's 62.4.

### Dinosaur Canyon and Seaside Street Galaxy

tools/col_convert.py now rebuilds all four of CCE's files for DUSA's
courses: CS0_COL.BIN, CS1_COL.BIN and CS12_COL.BIN (Dinosaur Canyon; CCE
loads CS12 when 0605492A is 1), and CS2_COL.BIN. In each cell's list:

1. CCE's wall strips, as CCE lists them in that grid.
2. DUSA's own list for the cell, in DUSA's order (so DUSA's first match
   wins, as in DUSA), mapped to CCE's types.
3. Outside the crossing cells, any DUSA polygon over the cell that DUSA's
   list leaves out.

Each DUSA polygon's corners are where its edge lines meet. Corners are not
snapped together: snapping merged distinct corners, which ranged from 1e-6
to 0.01 units apart, and opened slivers. Unsnapped, each polygon covers what
DUSA's own test covers.

What the surface type does in CCE: only the lookup (06036B0C) and the
ground contact (060388C4-0603894C, 06038834) read a probe's type. Both only
tell 0 (wall strip) and 0x80 (no ground found, which borrows a neighbouring
wheel's height) from the rest. CCE's types 1-4 change nothing (read
profile, 1500 frames). So DUSA's surface flags (01, 02, 04, 09, 0C, 10, 20,
41, 80) only need to be non-zero.

**Seaside crosses itself.** The road passes over itself at x -200..-130,
z 240..270, with the upper road at 43.3 and the lower at 33.

- **DUSA:** twelve cells have a second list, used while car +0x1EC <= 70
  (06027F20; cells 06061270, lists 06061240). That list holds the upper
  road.
- **CCE:** two grids (+0 and +0x4000), different in 24 cells. Each car
  uses the one in +0x12C, switched when its segment (+0x1A4) reaches the
  course's pair in 0604F9BC: segment 80 for the first grid (upper), 8 for
  the second (lower).
- **Converted:** the first grid gets DUSA's upper list, followed by the
  normal list, which fills where the upper road isn't. The second grid
  gets DUSA's normal list.

**Bug found in patch 21: the ahead point.** The ahead point went through
06036B60, which picks the grid by z (z >= 38 on Seaside: the upper road).
On the lower road under the bridge, the point 12 units ahead read the upper
road, 10 units up, and pitch jumped to +37 deg for about 1.5 s. Pitch
feeds the slope force, so that was a hard brake. This happened with CCE's
own file as well. The cave now looks the point up in the car's grid
(+0x12C), as the wheels do. Teleport along each road (x, z, heading and the
grid poked at 060386D8):

| | before | after |
|---|---|---|
| Lower road under the bridge, second grid | ride height 33.04, pitch 0 then +37.4 for 21 ticks | 33.04, pitch 0 |
| Upper road over the bridge, first grid | – | 43.30, pitch 0 all the way |

Checks:

- **Offline:** a copy of CCE's lookup on each new file was run against
  DUSA's lookup (with the upper lists for the first grid), on a 0.5-1.5
  unit grid over each course. Heights where both find ground agree within
  0.0001 units. Points that had ground in CCE's file and have none now:
  1 on Three Seven, 8 on Dinosaur Canyon (a real gap in DUSA's mesh near
  (305, -494)), and 22 on Seaside (x 860.7, z -274..-268, where CCE's road
  reaches past DUSA's polygons). DUSA finds no ground at any of them
  either.
- **In the game:** Time Attack states on the new disc for each course
  (build/cce_start_auto_courseN.txt; on the course menu a DOWN press at
  frame 3375 doesn't count, so course N takes N + 1 presses), saved as
  build/states/cce95_col_csN_start.mcs. Gas held for 900 frames: the car's
  height matches the new ground under it (median 0, worst 0.07 units, the
  four-wheel mean against the centre).

## Road direction from the ground (patches/road_direction.s)

The user saw the car wobble on Seaside's straights, most on the first
bridge, as if the drive-straight pull were rubber-banding. With the gas held
and no steering, the heading moved 15 times over 460 frames of straight,
between 9660 and 10205. It was following the road-direction field (+0x48).
That is the target of the straightening pull (06035C98, patch 12), which
pulls the heading 40 a tick toward it once the heading has stayed within
6 deg for 3 ticks.

- **CCE:** each of the four corner contacts (06036BB8) copies +0x194, a
  direction from CCE's course line. On Seaside's first straight it changes
  every 4-8 ticks, among 9660-9898 (up to 1 deg). On Three Seven's back
  straight it reads 11-20 deg off the road, so the pull never engages
  there. Stock CCE's pull was 16 a tick, weak enough to blur this; DUSA's
  40 follows it.
- **DUSA:** +0x25C is the road direction stored in each ground polygon
  (+0x30, high word), read from the polygon under the front corner (0.92
  right, 1.8 ahead; 06027CA4, called for the 4 corners with r5 = 0..3, only
  r5 = 0 sets it). It is constant over each section, exact on a straight
  (Three Seven's back straight: 0xAAAB, 240 deg), and unchanged where no
  polygon is found. Checked on the user's DUSA turn 1-2 drive: the
  polygon under that corner matches +0x25C on all 200 ticks.
- **Patched:**
  - tools/col_convert.py writes DUSA's direction into each polygon's flags
    low word: bit 1 set, bits 2-15 the direction. CCE's lookup reads only
    bit 0. Kept wall strips get the direction of DUSA's polygon at their
    centre.
  - At the first corner contact of each tick, a cave keeps CCE's value,
    then looks up the polygon under the front corner in the car's grid
    (060368D4) and takes its direction when it has one. The other three
    corners no longer copy.
  - Courses without DUSA's directions (the CCE-only ones) keep CCE's value.

Checks:

- **Seaside, gas only:** +0x48 holds one value (9828) all along the first
  straight, and the heading doesn't move once it is on it.
- **DUSA's turn 1-2 path fed to CCE95's ground contact:** +0x48 equals
  DUSA's +0x25C (to the 2 dropped bits) on 181 of 193 ticks. The other 12
  are at section edges, mostly one tick late: the teleport pokes heading
  +0x3C, and the cave reads +0x0E, which still holds the last tick's.
- **Race start:** the car is placed facing +0x48, so it now starts on
  DUSA's direction. That is 7868 on Seaside's grid, against CCE's 8151.
- **Old replays:** the drive-straight pull now engages where CCE's never
  did, such as Three Seven's back straight, so takes recorded before this
  patch no longer replay exactly.
- **The user's own drive** on Seaside after the patch: the wobble is gone,
  bridge included (2026-10-24).

## Ground for CCE's own courses (tools/col_generate.py)

National Park Speedway (CS3_COL.BIN) and Desert City (CS4_COL.BIN) were
never in DUSA. Their ground is now made from CCE's the way DUSA's was made.
`make disc` runs tools/col_generate.py from tools/col_convert.py.

**How DUSA's ground relates to CCE's.** On the shared courses, 81-84% of
DUSA's corners are CCE corners, at the same heights (median 0, p90 +-0.01,
Three Seven and Seaside). CCE refined DUSA's ground:

- cross-sections every 8 units on the banks, against DUSA's 16;
- extra rows across the banks, raised to a curve (the deeper bank);
- one plane per quad, which leaves the steps.

DUSA's bank is a straight ramp between its edges, in two triangles.

**The recipe**, on CCE's quad grid:

1. **Corner heights:** the median of the planes that meet at the corner.
2. **Edge roles:** which edge pair of each quad crosses the track is
   carried quad to quad through shared edges, choosing the labelling with
   the longest strips. Big flat quads (infields) are left out.
3. **Sections:** every other cross-section line is kept.
4. **Merging:** neighbouring cells of the same surface type merge across,
   so a bank is one cell from edge to edge.
5. **Splitting:** each cell is two triangles through its corners, split on
   the diagonal whose corners lie lower. That is DUSA's own rule: 27 of the
   29 Dinosaur Canyon cells that match a DUSA pair, and the cell at the start
   of Three Seven's turn 1.
6. **Slivers:** sliver triangles in the side's plane fill out to the corners
   a cell drops, where those lie outside its chord.
7. **Road direction:** each cell's along-track chord, pointed the way the
   race goes. That way is flooded over the ground from the start grid's
   heading (taken from each course's Time Attack start state).

**Tried on Three Seven**, CCE's file in, compared with DUSA's own along
the user's turn 1-2 line (build/camera/cce95_t12_car.trace.bin):

| | CCE's ground | made by the recipe | DUSA's ground |
|---|---|---|---|
| Turn 1 roll vs DUSA, rms (deg) | 2.19 | 0.63 | 0 |
| Turn 1 roll reversals | 27 | 13 | 13 |
| Turn 1 deepest roll (deg) | -20.0 | -16.2 | -17.3 |
| Turn 2 roll vs DUSA, rms (deg) | 2.03 | 1.05 | 0 |
| Turn 2 deepest roll (deg) | -21.4 | -16.3 | -18.3 |
| Road direction vs DUSA's | – | median 2.2 deg | – |

Three Seven itself keeps DUSA's real ground (col_convert.py); the recipe
only runs on CS3 and CS4.

**CCE's own courses** are cleaner grids than CCE's versions of DUSA's.
Shared edges that disagree on their role: 14 on National Park and 12 on
Desert City, against 354 on Three Seven. Quads merged: 1968 of 2651 on
National Park, 1482 of 2221 on Desert City. Desert City crosses itself,
like Seaside (its grids differ in 20 cells); each new polygon is listed,
per grid, in the cells its CCE quads were listed in there.

| | National Park, CCE / new | Desert City, CCE / new |
|---|---|---|
| Height step at shared corners, p99 | 0.176 / 0.048 | 0.184 / 0.075 |
| Corners with a step over 0.1 | many / 3 | many / 12 |
| Roll reversal size along the main strip, p99 (deg) | 0.41 / 0.25 | 0.77 / 0.24 |
| Points with ground in CCE's file, none in the new | – / 0 | – / 0 (both grids) |
| File size (bytes) | 226692 of 243988 | 223274 of 226000 |

Heights move where the straight ramps cut across CCE's curves. That is
mostly under 0.1 units (p1 -0.14, p99 +0.09), and up to 0.4 lower over a
crest on National Park.

In the game, from new Time Attack states on each course with the gas
held: the car sits on the new ground (median 0, worst 0.05 units). The
road direction under the front corner follows CCE's course line (median
4 deg on National Park, 0 on Desert City's start straight, which runs
along z), and none of them reversed.

The user drove several laps of both on the new disc and saw nothing out of
place (2026-10-24). The user has only driven these courses with CCE's
driving model, so the drive confirms nothing breaks, not what they should
feel like.

### The recipe against DUSA's real ground on all three of its courses

To check the recipe beyond the user's line, it was run on CCE's versions of
all three DUSA courses and compared with DUSA's own ground. The comparison
covers the whole road (recipe_check2.py in the session scratchpad): every
2 units on DUSA's road, facing DUSA's road direction there. Left out are
DUSA's outside ground, Seaside's crossing cells, and points where a wheel
finds a wall strip or nothing. At each point it takes the roll and pitch
the wheels read, the ride height, and how much the roll changes 2.5 units
ahead (the rocking).

| | Three Seven | Dinosaur Canyon | Seaside |
|---|---|---|---|
| Points (2-unit grid) | 17966 | 37084 | 73582 |
| Roll vs DUSA rms, CCE / recipe (deg) | 0.96 / 0.88 | 1.78 / 1.87 | 1.93 / 1.68 |
| The same on DUSA's banks | 2.21 / 1.99 | 3.26 / 3.06 | 3.43 / 3.33 |
| Pitch vs DUSA rms, CCE / recipe | 0.54 / 0.63 | 0.96 / 0.89 | 0.81 / 0.82 |
| Height vs DUSA mean, CCE / recipe | +0.021 / +0.020 | -0.217 / -0.204 | -0.152 / -0.144 |
| Roll change per 2.5 units, DUSA / CCE / recipe | 0.100 / 0.143 / 0.110 | 0.135 / 0.174 / 0.128 | 0.084 / 0.108 / 0.082 |
| Its 99th percentile, DUSA / CCE / recipe | 1.91 / 2.17 / 1.59 | 1.72 / 2.26 / 1.61 | 1.65 / 2.04 / 1.43 |

- **Rocking.** The recipe's rocking matches DUSA's within 0.01 deg a step
  on all three courses. CCE's is 25-30% more.
- **Tilt.** On the banks the recipe is closer to DUSA than CCE is, on all
  three courses. Over the whole road it is closer on Three Seven and
  Seaside, and a little further on Dinosaur Canyon.
- **Height.** The recipe starts from CCE's corners, so CCE's own height
  differences carry through. Dinosaur Canyon's corners sit 0.2 units under
  DUSA's.
- **The misfit limit.** The first version of this check found a fault.
  On Seaside some cells merged a road and a steep bank of the same surface
  type into one flat ramp, missing the corners they dropped by up to 5
  units, with 65 deg tilts at their edges. A merged cell that misses a
  dropped corner by more than 0.75 units is now left unmerged.

| Limit (units) | none | 0.5 | 0.75 | 1.0 | 2.0 |
|---|---|---|---|---|---|
| Roll vs DUSA rms: Three Seven / Dinosaur / Seaside | 1.05 / 1.95 / 2.37 | 0.87 / 1.69 / 1.67 | 0.88 / 1.87 / 1.68 | 0.91 / 1.95 / 1.70 | 1.05 / 1.95 / 1.83 |
| User's turn 2 line: roll rms, deepest | 1.05, -16.3 | 1.85, -21.2 | 1.05, -16.3 | 1.05, -16.3 | 1.05, -16.3 |

At 0.5 the limit also drops Three Seven's turn 2 bank, which DUSA builds as
a straight ramp too. National Park's and Desert City's cells all miss by
less than 0.75, so their files are unchanged.
