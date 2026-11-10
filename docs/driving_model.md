# Driving model: dimensions and DUSA → CCE differences

Each row is one part of the per-tick car update. Function addresses are
DUSA / CCE; field offsets are DUSA (CCE in docs/findings.md field map).

Verdicts:
- **ok**: same logic, constants correctly converted 20 → 30 Hz
- **bad conversion**: same logic, constant converted wrongly for 30 Hz
- **retuned**: value changed beyond any rate conversion
- **rewritten**: logic changed
- **?**: not yet understood

A per-tick *increment* converts ×2/3, a per-tick *acceleration* ×4/9, a
per-tick *multiplier* m becomes m^(2/3), and a *tick count* ×3/2.

| # | Dimension | Where | Difference | Verdict |
|---|---|---|---|---|
| 1 | Steering ramp | 0602FDA4 / 060370A0 | 1/7 per tick → 1/16; target ±112 → ±134 | **fixed (patch 1)** |
| 2 | Throttle ramp | input step | +20/tick (400/s) → +12/tick (360/s) | bad conversion, small (should be ~13) |
| 3 | Brake ramp | input step | not measured | ? |
| 4 | Front wheel angle filter | 0602F0E8 / 0604D780 | DUSA: halve the gap each tick. CCE: same halving at 30 Hz when a flag is set, otherwise no filter | bad conversion / rewritten |
| 5 | Auto-straighten | ? / 0604D780 | CCE has a state that forces throttle/brake to 0x38 and returns the wheel angle to centre by 0x71C/tick. DUSA also self-straightens on straights (visible on Three Seven); its code not found yet | ? |
| 6 | Steer scaling | 0602EFF0 / 0604D580 | 0.64 similarity, not decoded | ? |
| 7 | Engine torque × gearing | 0602F5B6 / 0604DB10 | same torque curve, gear ratios, rpm cap; the automatic's upshift rpm 7400 → 7144 (CMVDATA +0x1630; earlier listed as a rev limit) | ok / **upshifts fixed (patch 32)**: 1→2 at 106 km/h, 2→3 at 173 km/h, as DUSA |
| 8 | Pedal curves | same | DUSA table is linear i·0x101, CCE multiplies by 0x101 | ok (identical) |
| 9 | Brake force split | same | b²·180 front, b²·120 rear in both, *not* rescaled for 30 Hz | ? (needs a matched braking test) |
| 10 | Slipstream drag | same; CCE detection 0604DD34 | drag ×0.90 → ×0.60 while the tow timer (+0xD6 DUSA, +0x180 CCE) runs. Both start it at 30 ticks when another car is within 30 units ahead; CCE's window is 5° either side of the heading (0604DE2C), DUSA's 10° (0602F4B4, row 30) | retuned → **fixed (patch 31)** |
| 11 | Gearbox (auto / manual) | 0602F17C, 0602F270 / 0604D83C, 0604D94C | shift timer ±5 → ±16, downshift overshoot 1250 → 4000, rpm-follow steps not rescaled, CCE idle floor 500; auto thresholds not compared | **shift timer, overshoot, rpm follow converted (patch 23)**; auto thresholds ? |
| 12 | Tyre load & grip limits | 0602C690 / 060354A0 | load transfer ×2.25 (correct); clamp ranges ≈ same; 1/4-per-tick filter not rescaled | ok, small bad conversion |
| 13 | Wheelspin (**patch 3**: floor 0.17, decay 0x3D7) | 0602CCEC / 06035B30 | spin decay 0x5C2 → 0x51E per tick (CCE fades 1.33× faster in real time; 30 Hz value 0x3D6); grip floor 0.17 → 0.10; spin-onset gating changed, threshold table moved into per-car data | bad conversion + retuned + rewritten |
| 14 | Grip recovery & event timers (**patch 4**: x1.0656, 15 and 24 ticks) | 0602C8E2 / 06035750 | grip recovery ×1.10 → ×1.03 per tick (30 Hz value ×1.066; CCE recovers far slower); 10 and 16 tick timers not rescaled (2/3 duration); 20 → 30 ticks correct | bad conversion |
| 15 | Traction circle (drive vs lateral) | 0602C8E2 | present in both | ok? |
| 16 | Slide rate | 0602D43C / 06035F48 | clamp ±768 → ±256 | **fixed (patch 2)** |
| 17 | Slip angle limit | 0602D76A / 060362A4 | spin-out flag at ±0x3280 → ±0x3400, clamp ±0x3400 → ±0x3600 (angles, no tick conversion) | **fixed (patch 25)** |
| 18 | High-speed grip loss | same | ≥ 240 km/h with grip < 0x6800: grip cut over 10 ticks (0.5 s). CCE: a lift-off check against the per-car `+0x148`, only nearly straight, 48 ticks (1.6 s), and a floor on the countdown that DUSA lacks (its last tick can give grip x 1.1 or 1.2) | **converted (patch 6); per-car threshold from `+0x148`; floor removed** |
| 19 | Slide-rate reversal | same | CCE rate briefly flips sign mid-spin; DUSA doesn't | ? (inserted clamp code) |
| 20 | Extra slide damping | — / 06035F48 | per-car byte +0x1CB; when 0, the rate moves 1/4 of the way to its target each tick (Max, Balance, the secret car, horse 2). Hornet has 2, DUSA's path | per car, **as 20 Hz code: 0.1745 a tick (car_traits)** |
| 21 | Tyre forces / yaw | 0602CA84 / 06035904 | constants ×2.25 (correct); 0.96 similar | ok |
| 22 | Integration (velocity → position) | 0602CDF6 / 06035C98 | 0x2C → 0x40 (×1.5 ok); 0x154 → 0x44 and 0x444 → 0x38E unexplained | ? |
| 23 | Speed / rpm | 0602D814 / 060366EC | identical, rpm scale ×1.5 | ok |
| 24 | Surface grip | 0602C7FC / 06035624 | per axle, the mean of one term per surface: DUSA grass 0xB4, apron 0xD2, its 10 and 20 kinds 0xF6/0xFA, other bits 0x96; CCE grass 0x80, apron 0xE0, and our ground had DUSA's kinds as road | **fixed (surfaces)** |
| 25 | Car contact | 06030FC0 / 0603A784, 0603AF00 (2P) | CCE's contact sets the player's impact timer (+0x190), which makes the tyre step halve the slip every tick for 8 ticks; DUSA's contact never sets its timer (+0x150) | **fixed (patch 27)** |
| 25b | Wall scrape slip decay | 0602CBEA / 06035A68 | DUSA: timer 4, slip × 3/4 per tick; CCE: timer 8, slip × 1/2 per tick | **converted (patch 27)** |
| 25c | Wall impact speed factor | 06030E92 / 06037966, 06037B46, 06037D06 | DUSA: one shared tail, cars 0-5 ×0.87, 6-7 ×0.98, 8+ ×0.75. CCE: the tail copied into three impact paths, groups by +0x1C5 at ×0.82 / ×0.98 / ×0.77 | **fixed (patch 20, all three paths)** |
| 25d | Off-road drag | 0602F71C / 0604DC40 | DUSA: four wheels, 1-2 on grass heavy/4, 3-4 heavy/2, none with a wheel on its 10 ground (Dinosaur Canyon's last hairpin). CCE: front corners only, none if either is on road, light table 1.5x DUSA's | **fixed (surfaces)** |
| 26 | Heading smoothing | — / 06035EE8 | CCE adds a smoothing step on +0x134 from position deltas and wheel angle; probably visual | ? |
| 27 | Standing start (grid pedals, start rule) | 06030380, 0600C302 / 06037592, 0603740E, 06039952 | same rule (bog at pedal ≥ 230, fast start at brake ≥ 140 with pedal 156–229), timers 18 → 27 correct; grid pedal ramps +4/−2 (brake +5/−5) → +8/−4 (+10/−5): 3× faster; analog triggers (CCE only) at once | retuned → **fixed (patch 28)**, triggers at DUSA's button rates |
| 28 | Inputs during a crash | 060302C6, 0602F0E8 / 06037EFE, 0604D7BE | both freeze the pedals while a spin-out (DUSA +0xB8 = 48, CCE +0xB0 = 72) or a flip (DUSA +0x1BC, CCE +0xB4) runs; CCE also zeroes the pad while the flip count is 32 or more, so no steering or gear changes | rewritten → **fixed (patch 29)** |
| 29 | Spin-out and wheel rates | 06008252, 0602F144, 0602F41C / 06039E16, 0604D804, 0604D708 | spin-out speed loss 227 per tick kept as 151 (×4/9 = 101); wheels back to centre 0x71C per tick unconverted (0x4BD); wheel spin caps 0xAAA / 0x2AAA unconverted (visual) | bad conversion → **fixed (patch 30)** |
| 30 | Slipstream window | 0602F4B4 / 0604DE2C | ±10° (0x71C) → ±5° (0x38E); distance and timer converted | retuned → **fixed (patch 31)** |
| 31 | km/h cap | 0602F3F2 / 0604D6BE | 344 → 334 | retuned → **fixed (patch 32)** |
| 32 | Rolling-start handover (Three Seven) | 0600E5A2 / 0604D46C (mode 2) | DUSA skips physics until handover, so grip limits start at 0 and the rear spins with smoke; CCE forces steady limits every tick | ? (audit 2026-11-09; cause partly read) |
| 33 | Flip length and animation | 06008418 / 06008460 / 06039ED8 | DUSA one 64-tick flip (96 at 30 Hz); CCE 86 or 116 ticks (by impact flag 0x1000 / 0x800), tables resampled with the end cut, ~75% of DUSA's height | ? (audit) |
| 34 | Flip side rules | 06008270, 06030846, 0600875C, 06030B1C / 06039E4E, 06037AC2, 06037BF8 | what a flip blocks (DUSA the first count − 40 ticks, CCE all of it); DUSA's scrub at count 10 (absent in CCE); wall-strip (0x80) impacts flip unconditionally in DUSA, by speed in CCE | ? (audit) |
| 35 | Grass climb grip event | 0602C946 / 060357B6 | pitch over 0x500 → 0x600 (if patch 21 gave DUSA's pitch scale) | ? (audit) |
| 36 | Bog rear-limit halving | 0602CA40 / 060358C0 | ×0.5 per tick, unconverted (30 Hz ×0.63); patch 28 launches already within 1 km/h | bad conversion, small |
| 37 | Arcade Racer wheel (type 1) | 0603004C, 0602D08A, 0602EE58 / 06037200, 0603631C, 0604D1CC | DUSA: the pad's path but for steer = byte - 128 at once, its own gain table and an analog core differing from the pad's in the high-speed grip loss and the front term's slope (4 for 3). CCE: the byte doubled through a table with a dead zone, CCE's analog core, the pad's gains, no front-wheel filter | **fixed (patch 33)** |

## Per-car handling data

Both games pick handling from 14-entry tables indexed by car.

DUSA car init (0602ED18), index `+0x7C`:
- 0602EE90[car·2] → `+0x7E`, `+0x7F` (bytes)
- 0602EDE8[car] → `+0xC8` torque-curve pointer
- 0602EE20 (pad) / 0602EE58 (analog, `+0x9E`) [car] → gains `+0xCC/+0xCE`
  (pad: 0x1180/0x1180 for entries 0–1, up to 0x1700/0x1D00 for others)

CCE car init (06035388), index `+0x168` (from player config 060540B5):
- 0604D220/22E/23C/24A[car] → `+0x1C5`..`+0x1C8`; `+0x1C8` gates wheelspin onset
- 0604D258[car] → `+0x1CB` (extra slide damping path; values 2/1/0)
- 0604D204[car·2] → `+0x1BE`
- 002E01B4 (auto) / 002E01EC (manual, `+0x174`) [car] → `+0x74` torque curve (in CMVDATA)
- 0604D268[car·4] → `+0x148`
- 0604D1CC[car·2] → `+0x16C/+0x16E` gains (0x2E0–0x700); the same table for pad and analog
- 0604D2A0[car·2] → `+0x14C/+0x150`
- 0604D310[car·4] → `+0x1B2..+0x1B8` wheelspin thresholds (same for all cars)

The index is the config's car byte: 0 Hornet, 1 Gallop, 2 Max, 3 Phoenix,
4 Oriole, 5 Magic, 6 Wolf, 7 Balance, 8 the secret car, 9 and 10 the
horses. What each per-car byte does (2026-11-07, read from RACE.BIN):

| Field | Read at | Effect | Hornet | Others |
|---|---|---|---|---|
| `+0x1C5` | 06037966, 06037B46, 06037D06 (wall impact) | speed factor: 0 ×0.82, 1 ×0.98, 2 ×0.77; patch 20 gives DUSA's ×0.87 / ×0.98 / ×0.75 in all three paths | 0 | 2: Phoenix, Oriole, Magic, secret; 1: horse 2 |
| `+0x1C6` | 0604DC40 (off-road drag) | 0 DUSA's four-wheel drag, 1 heavy table x2 (DUSA's cars 8-9), 2 none (DUSA's cars 4-5); CCE's own: 0 light table, front corners only | 0 | 2: Max, horses; 1: Phoenix, secret |
| `+0x1C7` | 06035AD0 (tyre step) | scrub factor 0x72 (DUSA 0x100 ×4/9) or 0x89, now 0x8E (DUSA's 0x140 for its cars 4-5, ×4/9) | 0 | 1: Max, Magic, secret, horses |
| `+0x1C8` | 06035B76 (wheelspin onset) | when set, no wheelspin onset below 4th gear | 0 | 1: Max, Oriole, Magic, Wolf, Balance, secret, horses |
| `+0x1CB` | 06035604 (grip-limit filter), 0603613C (slide rate) | 2: DUSA's path; 1: grip limits follow 1/16 a tick; 0: that and the slide rate moves 1/4 of the way to its target each tick. Both now as if written at 20 Hz: 0.0421 and 0.1745 a tick | 2 | 1: Gallop; 0: Max, Balance, secret, horse 2 |
| `+0x148` | 06035F72 (high-speed grip loss) | CCE: rear-limit check, dropped by patch 6; now scales DUSA's grip threshold: (`+0x148` >> 16) x 13 | 0x8000000 (0x6800) | Phoenix 0x9000000 (0x7500), Balance 0x1000000 (0x0D00), secret and horse 2 0x6000000 (0x4E00) |

`+0x1C5` to `+0x1C8` are DUSA's own mechanisms keyed by car number in DUSA
(`+0x1C8`'s gate is DUSA's 0602CD30 for its cars 2, 3 and 10 up), with CCE's
choice of cars. `+0x1CB` and `+0x148` are CCE's; they now run as if written
into DUSA's 20 Hz code (patches/car_traits.s, grip_filter.s,
high_speed_grip_loss.s).

Player config bytes (060540B5 + player·6): [1] car, [2] steering speed
(`+0x1C9`), [3] transmission (`+0x174`), [5] controller ID (2 = pad → `+0x16A`=0,
0x13 = wheel → 1, else 2).

Patches 1–4 change code constants, so they apply to every car. Per-car
values changed for the Hornet are carried to the other cars proportionally
(patch 26, patches/car_rescale.patch).

Patch 8 (rotation term, core step 06035F48 → routine at 06032918) adds
code: DUSA's atan rounding and minimum, converted to 30 Hz, for every car.
