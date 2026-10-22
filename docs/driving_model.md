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
| 5 | Auto-straighten | — / 0604D780 | CCE adds a state that forces throttle/brake to 0x38 and returns the wheel angle to centre by 0x71C/tick | rewritten (CCE only) |
| 6 | Steer scaling | 0602EFF0 / 0604D580 | 0.64 similarity, not decoded | ? |
| 7 | Engine torque × gearing | 0602F5B6 / 0604DB10 | same torque curve, gear ratios, rpm cap; rev limit 0x1CE8 → 0x1BE8 (CMVDATA) | ok / retuned (rev limit) |
| 8 | Pedal curves | same | DUSA table is linear i·0x101, CCE multiplies by 0x101 | ok (identical) |
| 9 | Brake force split | same | b²·180 front, b²·120 rear in both, *not* rescaled for 30 Hz | ? (needs a matched braking test) |
| 10 | Rolling resistance | same | ×0.90 → ×0.60 when +0xD6 > 0 | retuned |
| 11 | Gearbox (auto / manual) | 0602F17C, 0602F270 / 0604D83C, 0604D94C | ±5 → ±16, 1250 → 4000; auto logic 2.5× larger | rewritten |
| 12 | Tyre load & grip limits | 0602C690 / 060354A0 | load transfer ×2.25 (correct); clamp ranges ≈ same; 1/4-per-tick filter not rescaled | ok, small bad conversion |
| 13 | Wheelspin | 0602CCEC / 06035B30 | spin decay 0x5C2 → 0x51E per tick (CCE fades 1.33× faster in real time; 30 Hz value 0x3D6); grip floor 0.17 → 0.10; spin-onset gating changed, threshold table moved into per-car data | bad conversion + retuned + rewritten |
| 14 | Grip recovery & event timers | 0602C8E2 / 06035750 | grip recovery ×1.10 → ×1.03 per tick (30 Hz value ×1.066; CCE recovers far slower); 10 and 16 tick timers not rescaled (2/3 duration); 20 → 30 ticks correct | bad conversion |
| 15 | Traction circle (drive vs lateral) | 0602C8E2 | present in both | ok? |
| 16 | Slide rate | 0602D43C / 06035F48 | clamp ±768 → ±256 | **fixed (patch 2)** |
| 17 | Slip angle limit | same | ±0x3280 / 0x3400 → ±0x3400 / 0x3600 | retuned |
| 18 | High-speed grip loss | same | ≥ 240 km/h with grip < 0x6800: grip cut over 10 ticks (0.5 s). CCE: grip < 0x300 (almost never), 48 ticks (1.6 s) | retuned (effectively disabled) |
| 19 | Slide-rate reversal | same | CCE rate briefly flips sign mid-spin; DUSA doesn't | ? (inserted clamp code) |
| 20 | Extra slide damping | — / 06035F48 | byte +0x1CB selects a path that quarters each rate change | rewritten (off in Time Attack) |
| 21 | Tyre forces / yaw | 0602CA84 / 06035904 | constants ×2.25 (correct); 0.96 similar | ok |
| 22 | Integration (velocity → position) | 0602CDF6 / 06035C98 | 0x2C → 0x40 (×1.5 ok); 0x154 → 0x44 and 0x444 → 0x38E unexplained | ? |
| 23 | Speed / rpm | 0602D814 / 060366EC | identical, rpm scale ×1.5 | ok |
| 24 | Surface types | 0602C7FC / 06035624 | surface IDs differ (tracks differ) | ? |
| 25 | Wall / car collisions | outside this pipeline | not explored | ? |
| 26 | Heading smoothing | — / 06035EE8 | CCE adds a smoothing step on +0x134 from position deltas and wheel angle; probably visual | ? |
