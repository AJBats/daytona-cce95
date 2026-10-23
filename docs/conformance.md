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
(routine in the cave; pedals and gears untouched; a single slot, so in
2-player play the hold doesn't apply).

12-frame tap, steering frames / ramp sum:

| | phases | frames | ramp sum |
|---|---|---|---|
| DUSA | 3 | 12, 15, 15 (14) | -405, -579, -579 (-521) |
| CCE before | 2 | 12, 12 | -392 |
| CCE patch 15 | 2 | 14, 14 | -506 |

Hot-patching note: the routine keeps state in the cave (tag, previous
word), so those two words must not be re-poked every tick.

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
