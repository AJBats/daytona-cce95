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
| 7 | Engine torque × gearing | 0602F5B6 / 0604DB10 | same torque curve, gear ratios, rpm cap; rev limit 0x1CE8 → 0x1BE8 (CMVDATA) | ok / retuned (rev limit) |
| 8 | Pedal curves | same | DUSA table is linear i·0x101, CCE multiplies by 0x101 | ok (identical) |
| 9 | Brake force split | same | b²·180 front, b²·120 rear in both, *not* rescaled for 30 Hz | ? (needs a matched braking test) |
| 10 | Rolling resistance | same | ×0.90 → ×0.60 when +0xD6 > 0 | retuned |
| 11 | Gearbox (auto / manual) | 0602F17C, 0602F270 / 0604D83C, 0604D94C | shift timer ±5 → ±16, downshift overshoot 1250 → 4000, rpm-follow steps not rescaled, CCE idle floor 500; auto thresholds not compared | **shift timer, overshoot, rpm follow converted (patch 23)**; auto thresholds ? |
| 12 | Tyre load & grip limits | 0602C690 / 060354A0 | load transfer ×2.25 (correct); clamp ranges ≈ same; 1/4-per-tick filter not rescaled | ok, small bad conversion |
| 13 | Wheelspin (**patch 3**: floor 0.17, decay 0x3D7) | 0602CCEC / 06035B30 | spin decay 0x5C2 → 0x51E per tick (CCE fades 1.33× faster in real time; 30 Hz value 0x3D6); grip floor 0.17 → 0.10; spin-onset gating changed, threshold table moved into per-car data | bad conversion + retuned + rewritten |
| 14 | Grip recovery & event timers (**patch 4**: x1.0656, 15 and 24 ticks) | 0602C8E2 / 06035750 | grip recovery ×1.10 → ×1.03 per tick (30 Hz value ×1.066; CCE recovers far slower); 10 and 16 tick timers not rescaled (2/3 duration); 20 → 30 ticks correct | bad conversion |
| 15 | Traction circle (drive vs lateral) | 0602C8E2 | present in both | ok? |
| 16 | Slide rate | 0602D43C / 06035F48 | clamp ±768 → ±256 | **fixed (patch 2)** |
| 17 | Slip angle limit | same | ±0x3280 / 0x3400 → ±0x3400 / 0x3600 | retuned |
| 18 | High-speed grip loss | same | ≥ 240 km/h with grip < 0x6800: grip cut over 10 ticks (0.5 s). CCE: grip < 0x300 (almost never), 48 ticks (1.6 s) | retuned (effectively disabled) |
| 19 | Slide-rate reversal | same | CCE rate briefly flips sign mid-spin; DUSA doesn't | ? (inserted clamp code) |
| 20 | Extra slide damping | — / 06035F48 | per-car byte +0x1CB; when 0, each rate change is quartered (cars 2, 7, 8, 10, 12, 13). Hornet (car 0) has 2, so it uses the DUSA-like path | rewritten (per car) |
| 21 | Tyre forces / yaw | 0602CA84 / 06035904 | constants ×2.25 (correct); 0.96 similar | ok |
| 22 | Integration (velocity → position) | 0602CDF6 / 06035C98 | 0x2C → 0x40 (×1.5 ok); 0x154 → 0x44 and 0x444 → 0x38E unexplained | ? |
| 23 | Speed / rpm | 0602D814 / 060366EC | identical, rpm scale ×1.5 | ok |
| 24 | Surface types | 0602C7FC / 06035624 | surface IDs differ (tracks differ) | ? |
| 25 | Wall / car collisions | outside this pipeline | not explored | ? |
| 26 | Heading smoothing | — / 06035EE8 | CCE adds a smoothing step on +0x134 from position deltas and wheel angle; probably visual | ? |

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
- 0604D268[car] → `+0x148`
- 0604D1CC[car·2] → `+0x16C/+0x16E` gains (0x2E0–0x700)
- 0604D2A0[car·2] → `+0x14C/+0x150`
- 0604D310[car·4] → `+0x1B2..+0x1B8` wheelspin thresholds (same for all cars)

Player config bytes (060540B5 + player·6): [1] car, [2] steering speed
(`+0x1C9`), [3] transmission (`+0x174`), [5] controller ID (2 = pad → `+0x16A`=0,
0x13 = wheel → 1, else 2).

Patches 1–4 change code constants, so they apply to every car.

Patch 8 (rotation term, core step 06035F48 → routine at 06032918) adds
code: DUSA's atan rounding and minimum, converted to 30 Hz, for every car.
