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
| Car model | DUSA's low-detail Gallop | below |
| Livery (patches/livery.s) | per player | below |
| Window reflection (patches/reflection.s) | none | player 1's PLCAR01 only |
| Engine sound | DUSA's, per player | below |
| Tyre sounds | DUSA's slip, brake and peel-out, per player | below |

## Sound

CCE's 2P race files (DAYT2P, DAY3_2P, DAY4_2P, and the M versions, which
differ only in the pan words: centre for mono) played CCE's engine, four
layers a player: P1 on slots 24-27, P2 on 28-31, from the same table blocks,
mailboxes 6F00 and 6F20, panned by the words at 7F780/7F782. The race loop
calls the car-tick sound routine once per player (06028B76, r4 = player),
which sends to that player's mailbox (06010AB0[r4]).

Now tools/engine_convert.py builds the 2P files like the 1P ones (DUSA's six
engine layers, slip, brake, one peel-out record) with
patches/sound_2p_bank0.s as the code, tagged 'DUS2'. When the driver's
engine module finds that tag it hands its tick to that code and skips
CCE's two engines (patches/tyre_sound_drv.s), and it reserves slots 16-31
instead of 20-31:

| slots | |
|---|---|
| 16-17 | peel-out, shared: each one starts on the other slot and rings on over the last |
| 18, 19 | P1 slip, brake |
| 20, 21 | P2 slip, brake |
| 22-26 | P1 engine |
| 27-31 | P2 engine |

Each sound is panned to its player's side with the pan words. DUSA's engine
has at most five layers in range at once; the slot shared by the top-end
layer (3, from step 19) and one of the idle pair (4, to step 17) switches
blocks at step 18, where both tables are silent (engine_convert checks
it), so all six layers play as in 1P. The car tick writes each player's
tyre values after its engine values (P1 6F10, P2 6F30).

The sequencer keeps slots 0-15. Over 60 s of a 2P race with constant wall
hits it used at most 12 at once (vanilla CCE: 11, its tyre loops
included), and never 16 or above.

The reservation didn't hold below slot 24: the driver's voice monitor
(17EA) walks slots 0-23 and clears a slot's +0x3A word, the allocator's
mark, once the voice there reads idle. That freed 1P's peel-out slots
20-23 to the sequencer whenever 0-19 were all busy. The monitor now skips
reserved slots (byte +0 bit 7, set only by the reservation).

Slots 16-17 also carry the CD audio's mix: their EFSDL/EFPAN (the low byte
of +0x16) set the music's level and pan. The layer set-up (19AA) wrote the
record's whole send word, so the first two peel-outs cut the music (the
user heard it). The sequencer writes the high byte alone; the set-up and
the 2P pan now do too. On slots 18-31 that byte does nothing.

Checked from boot: both players' engines follow their own rpm on their
own side, P2's brake plays on slot 21 while P1 drives on, slip and
peel-outs come from both cars, the music's level on slots 16-17 holds
through the peel-outs, and the 1P files are byte for byte what they were.
The user: "sounds really good", then "working great, consider the 2P sound
done" (2026-10-25).

## The Gallop in 2P

2P loads PLCAR21 for the Hornet. tools/car_convert.py now writes it from
DUSA's body, model 0, the 1P car, in all six model slots (so 2P shows no
damage: the damaged body doesn't fit as well). To fit the file: only the
textures the body uses, 16-colour tables 0-21 (the livery sets at 8-13 and
16-21 as in PLCAR01), the floor panel's 64x60 texture at 16x15, and the
texture table grown from 38 entries to 49 (the loader's relocation,
060482F8, runs over as many entries as the count says): 2956 of 3972 MDL
bytes, 20344 of 20380 TEX bytes. The livery patch runs in 2P too, for car
1, from each player's transmission byte; checked from boot with the
transmissions forced at the loader both ways round.

Cost: 132 faces a car against CCE's 47-48. Over 20 s of a 2P race from
the green flag, P1's car moved every 2 frames (30 Hz) on this disc and on
vanilla CCE alike.

First try, rejected: DUSA's model 11 (92 vertices, 49 faces), the lowest
detail of DUSA's generic car mesh. Its texture ids follow the same sheet
layout as the body's (DUSA's slot table, 060684EC, gives every bank ids
1-10 and 16-57), but on the Gallop's sheet it came out as a big rear
window over a black tail; the user: "super cursed".

## Found along the way

- The livery copy recoloured every 1P car, not just the Gallop (fixed,
  docs/car_model.md).
- Driving into the turn-1 wall unsteered from the rolling start, CCE95's
  P2 gets a crash (spin timer +0xB4 = 116, from 06039ED8) where vanilla
  CCE's doesn't: the cars' lines differ after the green flag. Not
  2P-specific.

## DUSA material for 2P

- POLYGON.BIN's other car-sized models: 6 (101 vertices, 79 faces) and 11
  (above), lower-detail versions of a generic car mesh; 5 (99 vertices, 68
  faces) uses textures 58-63, outside the car sheet.
