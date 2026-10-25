# Two-player split screen: what CCE95 changes, what it doesn't yet

DUSA has no split screen, so 2P parity means each player gets what 1P has.
Game mode byte 002FC233 = 2 in 2P. Both players' cars tick at 30 Hz, the
same as 1P.

## Cars and input

- Car structs: P1 0605224C, P2 06052424 (stride 0x1D8). Car +0x12 is the
  player index, +0x160 the key config (P1 0605273C, P2 06052764).
- Pad reader 06044344 (r4 = player): in mode 2 it reads pad n from the
  peripheral table 060072C4 + 12n and writes 060540F4 + 12n (P2 06054100).
  In car states 0-1 the pad words are cleared while the crash timer +0xB4
  is 32 or more (06037EFE).
- Car loader 06040280 (r4 = player): car number = byte 060540B6 + 6 x
  player, plus 1; in mode 2 cars 1-9 load PLCAR21-29, the low-detail
  files. Transmission byte 060540B8 + 6 x player.
- Tooling: the debugger takes P2_ button names (P2_START, P2_LEFT) for the
  second pad (SaturnAutoRE mednafen 5ecc6cb). build/cce_start_2p_course0.txt
  starts a 2P race on Three Seven from boot (2PLAYER BATTLE, delay 0 s);
  build/states/cce95_2p_t7.mcs is the rolling start, cce95_2p_t7_go.mcs
  just after the green flag.

## Patch by patch

| | 2P now | |
|---|---|---|
| Handling (throttle, brake, steering filters, grip filter, rotation, ground pitch, road direction, car rescale) | per car | same as 1P |
| Steering hold (patches/steer_hold.s) | per player | was one slot, so neither player got the hold; now two |
| Throttle slow-release phase | one counter for both cars | each car still steps on two ticks of three: two calls a tick walk every car through all three phases |
| Chase camera (patches/camera.s) | CCE's | the chase and yaw routines branch to CCE's rules in mode 2; lens 0x80 kept |
| Car model | CCE's Hornet | 2P loads PLCAR21, which keeps CCE's Hornet |
| Livery (patches/livery.s) | CCE's | skipped in mode 2; the routine already reads the transmission per player |
| Window reflection (patches/reflection.s) | none | player 1's PLCAR01 only |
| Engine sound | CCE's 2P engine, interpolated | 2P files (DAYT2P, DAY3_2P, DAY4_2P and their M versions) keep CCE's engine: four layers a player, P1 on slots 24-27, P2 on 28-31, mailboxes 6F00 and 6F20 |
| Tyre sounds | none | CCE's slide loop and screech code is now the tyre cave, and DUSA's tyre code lives only in the 1P files' tone bank 0 |
| Sequencer slots 20-23 | reserved, unused | the driver patch reserves them in every mode |

## Found along the way

- The livery copy recoloured every 1P car, not just the Gallop (fixed,
  docs/car_model.md).
- Driving into the turn-1 wall unsteered from the rolling start, CCE95's
  P2 gets a crash (spin timer +0xB4 = 116, from 06039ED8) where vanilla
  CCE's doesn't: the cars' lines differ after the green flag. Not
  2P-specific.

## DUSA material for 2P

- POLYGON.BIN has two lower-detail Gallops with the player car's body
  textures: model 6 (101 vertices, 79 faces) and model 11 (92 vertices,
  49 faces, the window texture included). CCE's 2P Hornet has 55-57
  vertices and 47-48 polygons; PLCAR21.MDL is 3972 bytes and PLCAR21.TEX
  20380.
- DUSA's engine has six layers, up to five sounding at once (v 5-63: main,
  octave, low/mid and the idle pair). The top-end layer (v 72-127) and the
  idle pair (v 1-63) never sound together.
