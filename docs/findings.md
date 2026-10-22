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
