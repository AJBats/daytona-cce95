# Findings

## Load map

| Game | File | Load address | Notes |
|---|---|---|---|
| DUSA | APROG.BIN | 0x06003000–0x06063690 | single program, all game code |
| CCE  | DAYTONA/0 | 0x06005200 | kernel / common code |
| CCE  | DAYTONA/RACE.BIN | 0x06028000–0x06051608 | race overlay, contains car physics |

CCE per-car files (HORNET.BIN, OLD_DAYT.BIN, ...) are VDP2 graphics
(destinations 0x25E42000 / 0x25F00600), not handling code.

## Player car state

| | DUSA | CCE |
|---|---|---|
| struct base | 0x06078900 (passed in r14) | 0x0605224C (r14, also GBR) |
| speed (internal) | +0x0C | +0x24 |
| speed (km/h, int) | +0x08 (0x06078908) | +0x34 (0x06052280) |
| acceleration added to speed | +0xFC | +0xF0 |
| gear (s16) | +0xDC | +0x17A |
| engine rpm (clamped 0x2134) | +0xE0 | +0xD0 |
| rpm overflow | +0xE8 | +0xC0 |

## Tick rate

Car physics run at **20 Hz in DUSA** (speed written every 3 frames) and
**30 Hz in CCE** (every 2 frames). Internal speed per km/h is ~912 (DUSA) vs
~608 (CCE), a ratio of 1.5 = 30/20, so speed is distance-per-tick in the same
distance units.

## Shared lineage (derived, not identical)

The speed/RPM update is instruction-for-instruction identical in both games
(DUSA 0x0602D814, CCE 0x060366EC): same compiler output, different struct
offsets and constants. The RPM scale constant is 0x0221AC91 (DUSA) vs
0x0332ED21 (CCE), ratio 1.5008.

Whole player-car update subtree, from call traces of one physics tick
(DUSA root 0x0602ECF2, 28 funcs; CCE root 0x0604D380, 31 funcs), matched
with tools/funcmatch.py (immediates/offsets masked). Null baseline
(shuffled instruction order): median 0.24, max 0.52. Full table:
build/match_cartree.txt.

- 4 identical, ~12 at 0.77-0.96 (same algorithm; changed field widths,
  extra/removed conditions, retuned constants)
- top-level update (0.42), 0x0602FDA4 (0.42), 0x0602F17C (no match) and
  several small helpers are substantially rewritten or replaced

So CCE's handling is DUSA's code base modified. The tick pipeline below
shows where: input processing is rewritten, a few stages changed, most are
close edits.

Call chains at the speed writer:

- DUSA: 0x0600DE70 → 0x0600E4F2 → 0x0602ECF2 → 0x0602D814
- CCE:  0x06028000 → 0x06037E28 → … → 0x0604D380 (car update root) → 0x060366EC

## Per-tick car update pipeline

The earlier 0.42 score for the "root" compared DUSA's state dispatcher +
init code against CCE's tick body. Comparing the tick bodies directly, both
games call the same pipeline in the same order (build/pipeline_pairs.txt):

| # | DUSA | CCE | score | note |
|---|---|---|---|---|
| 1 | 0602FDA4 (314) | 06036CEC (45) | 0.16 | **input processing; CCE replaced with 3-way dispatch on +0x16A** |
| 2 | 0602EFF0 | 0604D580 | 0.64 | |
| – | copy +0x250→+0x252 | copy +0x170→+0x172 | | |
| 3 | 0602F3EC | 0604D6B8 | 0.78 | |
| 4 | 0602F7BC | 0604D758 | identical | |
| 5 | 0602F0E8 (27) | 0604D780 (58) | 0.56 | |
| 6 | 0602F270 / 0602F17C (100) | 0604D94C / 0604D83C (254) | 0.96 / 0.55 | branch on DUSA +0x9C / CCE +0x174; CCE else-arm 2.5× larger |
| 7 | 0602F474 | 0604DAD8 | 0.96 | |
| 8 | 0602F4B4 (7) | — | | dropped in CCE |
| 9 | 0602F5B6 | 0604DB10 | 0.94 | |
| 10 | 0602EFCC | 0604DD04 | 0.50 | |
| 11 | 0602C690 | 060354A0 | 0.87 | |
| 12 | 0602C8E2 | 06035750 | 0.93 | |
| 13 | 0602CA84 | 06035904 | 0.96 | |
| 14 | 0602D08A / 0602D43C | 0603631C / 06035F48 | 0.86 / 0.87 | branch on DUSA +0x9E / CCE +0x16A |
| 15 | 0602CDF6 | 06035C98 | 0.90 | |
| 16 | — | 06035EE8 (44) | | added in CCE |
| 17 | 0602D814 | 060366EC | identical | speed / rpm |
| 18 | 0602D8BC | 06036790 | 0.88 | |

DUSA 0602FDA4 reads the pad block at 0x06081888–0x06081896 and writes the
input fields +0x6C..+0xB8.

## Steering input (digital pad, LEFT held from rest)

| field | DUSA | CCE |
|---|---|---|
| ramped steer (→ ~-105, snaps to 0 on release) | +0xAC | +0x78 |
| scaled steer (saturates at -127) | +0xB0 | +0x7C |
| scaled steer, one tick later | +0xB4 | — |

Ramped steer vs time (same real time, both from 0):

| t (s) | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 |
|---|---|---|---|---|---|---|
| DUSA | -29 | -50 | -65 | -76 | -85 | -91 |
| CCE  | -15 | -35 | -51 | -64 | -75 | -84 |

Scaled steer reaches full lock at ~0.47 s (DUSA) vs ~0.60 s (CCE). CCE's
steering builds up measurably slower on the pad.

## Car tuning data

CCE loads its car tuning tables from `DAYTONA/CMVDATA.BIN` (0x5000 bytes) at
0x002DC000 in low work RAM. DUSA keeps the equivalent inside APROG.BIN
starting around 0x060454CC. Matching table block (DUSA 0x0604779C ↔ CCE
0x002DD620): gear ratios identical; rev limit 0x1CE8 → 0x1BE8; the table at
+0x50 changed format (0x0BD52BD3… → 0x00026666…).

## Car struct field map (DUSA → CCE)

From tools/fields.py over 20 aligned function pairs; full list with vote
counts in build/fields.txt. Fields confirmed independently in the emulator:
speed 0x0C→0x24, km/h 0x08→0x34, accel 0xFC→0xF0, gear 0xDC→0x17A, rpm
0xE0→0xD0, steer ramp 0xAC→0x78, steer scaled 0xB0→0x7C.

## Pipeline roles (from field writes)

| DUSA | CCE | writes (DUSA offsets) | role (tentative) |
|---|---|---|---|
| 0602FDA4 | 06036CEC | 0x6C..0xB8 | pad input → steer / throttle / brake |
| 0602EFF0 | 0604D580 | 0x94 0xB0 0xB4 | steer scaling |
| 0602F270 / 0602F17C | 0604D94C / 0604D83C | 0xD8–0xE4 | gear / rpm (auto vs manual?) |
| 0602F5B6 | 0604DB10 | 0xEC–0xF8 0x11C | engine force / accel |
| 0602CA84 | 06035904 | 0x58–0x64 0xFC 0x108–0x110 | grip / slide state |
| 0602D08A / 0602D43C | 0603631C / 06035F48 | 0x00 0x58 0x5C 0x10C 0x168 0x178 | **yaw / handling core** |
| 0602CDF6 | 06035C98 | 0x28 0x30 0x60 0x64 | velocity / position integration |
| 0602D814 | 060366EC | 0x0C 0xE0 0xE8 | speed / rpm |

## Retuned constants in the pipeline

Full list: build/constdiff_all.txt (tools/constdiff.py). Some are the
expected 20→30 Hz rescale (×1.5 such as #20→#30 ticks, 0x480000→0x6C0000;
×2.25 = 1.5² such as 0x28D0FA→0x5BD633). Others are not explained by tick
rate and look like retuning, e.g.:

- handling core 0602D43C→06035F48: 0x6800→0x300, #10→#48, 0xA0000→0x300000;
  plus inserted clamp logic
- 0602C8E2→06035750: 0x11999→0x107AE (1.10→1.03 in 16.16)
- 0602F5B6→0604DB10: 0x7333→0x4CCC (0.90→0.60 in 1.15)
- 0602CCEC→06035B30: 0x2B85→0x1999 (0.17→0.10), #10→#2
- 0602CA84→06035904: 0x140→0x89, 0x100→0x72
- gear/rpm 0602F17C→0604D83C: ±5→±16, 0x4E2→0xFA0

## Patch 1: steering ramp (patches/steering.patch)

DUSA 0602FDA4 (pad, 20 Hz): `steer += (±112 − steer) / 7` via the hardware
divider (helper 0602ECCC = CCE 06048160, r1 = r1 / r0).
CCE 060370A0 (30 Hz): `steer += (±134 − steer) / D`, D = 22 / 16 / 10 from
car byte +0x1C9 (value 1, D = 16, in a default Time Attack race).

30 Hz equivalent of DUSA: retain (6/7)^(2/3) = 0.902 per tick → D ≈ 10.25.
Patch sets all divisors to 10 and the targets back to ±112.

Measured, LEFT held from straight-line running (scaled steer +0x7C/+0xB0):

| t (s) | 0.1 | 0.2 | 0.3 | 0.4 | full lock |
|---|---|---|---|---|---|
| DUSA | -40 | -76 | -102 | -120 | 0.43 s |
| CCE stock | -5 | -43 | -73 | -97 | 0.55 s |
| CCE patched | -33 | -73 | -103 | -123 | 0.43 s |

## Wheelspin and spin-out (launch tests)

States: build/states/dusa_stopped.mcs, cce_steerpatch_stopped.mcs,
cce_p2_stopped.mcs (stopped on the Three Seven main straight). DUSA pad:
C = accelerate, B = brake. CCE pad: B = accelerate, C = brake.

- grip `+0x10C` (CCE +0x70) + wheelspin `+0x110` (CCE +0x100) ≈ 64062 (1.0).
  Written by DUSA 0602CCEC / CCE 06035B30.
- Straight launch: wheelspin curves nearly identical in both games.
- Full-lock launch: DUSA spins out (grip → 0.17, yaw rate → -14000, spin-out
  flag `+0x114` (CCE +0xBC) = 400<<16). Stock CCE never gets there: yaw
  rate stalls at ~-5300 and wheelspin fades.

Cause: in the core step the per-tick slide rate `+0x178` (CCE +0x104) is
`clamp(target, ±768)` in DUSA, ±256 in CCE, and slip `+0x5C` (CCE +0x68)
integrates it ×7/8 per tick. CCE's /3 rescale halves the real-time rate;
the 30 Hz equivalent is ±512.

## Patch 2: slide rate (patches/slide_rate.patch)

Clamp ±256 → ±512 at CCE 06036158 and 06036190. Full-lock launch now spins
out like DUSA (grip 0.10, yaw rate peak -14849, spin-out flag set), about
0.5 s later than DUSA.

Remaining differences seen in this test:
- CCE rate `+0x104` briefly flips sign (+256/+512) around 2.0 s; DUSA stays
  negative. Something in CCE's target computation differs.
- slip limit: DUSA ±0x3280/0x3400 vs CCE ±0x3400/0x3600.
- CCE byte `+0x1CB` selects an extra path that quarters the rate change
  (not used in Time Attack here; +0x1CB = 2).

## Patches 3–4: wheelspin and grip recovery

Full-lock launch (yaw, slip as before):

| t | DUSA grip / spin | CCE p2 grip / spin | CCE p4 grip / spin |
|---|---|---|---|
| 2.00 | 23966 / 25949 | 48408 / 12377 | 45685 / 14986 |
| 2.25 | 11141 / 27026 (spun) | 49232 / 3207 | 22617 / 29964 |
| 2.50 | 11141 / 26801 | 12800 / 33081 | 11576 / 31704 |
| 3.00 | 11141 / 26247 | 6553 / 33613 (spun) | 11141 / 31806 (spun) |

The grip floor now matches DUSA exactly (11141) and the spin-out arrives
~0.25 s later than DUSA instead of ~0.75 s.

Straight launch: every CCE build lags DUSA from 2.0 s (42 vs 50 km/h): DUSA
upshifts around 2.25 s, CCE later. With patch 4's slower spin decay the
longer first-gear phase keeps more wheelspin (3.5 s: 62 km/h vs DUSA 85).
The gearbox rewrite (0602F17C / 0604D83C) is the next thing to match.

## Position-matched tests (back straight after turn 1, Three Seven)

States: build/states/dusa_backstraight.mcs, cce_p4_backstraight.mcs (both
stopped, game paused: tap START to resume), and *_bs_7s.mcs = 7 s of full
throttle from there (~187 km/h, 3rd gear, level road).

- Drag race from standstill: within 1–3 km/h for 10 s (DUSA 231, CCE 230).
- Straight braking from 187 km/h: matches (DUSA 126, CCE 122 km/h after 1 s).
  The braking gap measured on the main straight came from the banking.
- Throttle + full lock at 187 km/h: DUSA's rear goes into wheelspin at
  0.47 s (grip 0.17); CCE never does.

Wheelspin gate (DUSA 0602CD72 / CCE 06035BA6): spin starts when
drive·(1 − rpm/cap) ÷ (grip·rear budget) exceeds the per-gear threshold.
Grip (`+0x10C`) is cut in the tyre-force step (0602CBBC) when lateral +
longitudinal demand exceeds the rear budget. CCE's demand was lower because
lateral force builds slowly.

## Patch 5: lateral force filter (patches/lateral_force_filter.patch)

DUSA 0602CDF6: `lat += (target − lat)/4` per 20 Hz tick (τ 0.17 s), one
target for front and rear. CCE 06035C98: `/16` per 30 Hz tick (τ 0.52 s),
and separate front/rear stiffness from per-car data (`+0x14C/+0x150`;
Hornet 0x320/0x2BC vs DUSA 0x320 for both). Patch replaces the shifts with
a 3/16 multiply (τ 0.16 s), reusing a dead literal at 06035E84.

Throttle + full lock, lateral force (front): 0.3 s DUSA 181M, CCE p4 89M,
p5 180M. Steady state ~200M vs DUSA 227M. The wheelspin gate ratio now
peaks at 0x4B48 vs threshold 0x5000 (DUSA reaches 0x543C), so CCE still
doesn't break into wheelspin in this test, even with DUSA's rear stiffness
and thresholds poked in. Remaining gap: ~9% lower steady lateral force and
about half DUSA's slip (`+0x5C`).

## Hot-patching save states

The debugger can't write memory directly, but `poke_breakpoint_set` with
trigger 0x0604D380 (CCE car update) writes code/data on the next tick. Load a
state, poke, advance 2 frames, `poke_breakpoint_clear`, save. Poke triggers
survive `load_state`, so always clear them.
