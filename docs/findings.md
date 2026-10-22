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

So CCE's handling is DUSA's code base modified, with the biggest changes in
the top-level update and a few large functions.

Call chains at the speed writer:

- DUSA: 0x0600DE70 → 0x0600E4F2 → 0x0602ECF2 → 0x0602D814
- CCE:  0x06028000 → 0x06037E28 → … → 0x0604D380 (car update root) → 0x060366EC
