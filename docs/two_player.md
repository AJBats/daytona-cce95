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
| Chase camera (patches/camera.s) | CCE's, by the user's choice | the chase and yaw routines branch to CCE's rules in mode 2; lens 0x80 kept. The user: the split screen changes how framing works and CCE's camera works fine there |
| Car model | DUSA's low-detail Gallop | below |
| Livery (patches/livery.s) | per player | below |
| Window reflection (patches/reflection.s) | per player | below |
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
instead of 1P's 19-31 (files without a tag, such as the menus', reserve
CCE's 24-31):

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

This section first described PLCAR21, the Hornet's 2P file. Since the
'95 cars, every car with DUSA's body chosen loads PLCAR29 in 2P (car 9's
2P file, laid out as PLCAR21), with its paint from PLCAR29.TEX or
PLCAR5n.TEX; CCE's own body still loads its untouched PLCAR2n.
Since 2026-11-14 it is DUSA's low-detail car (below); until then
tools/car_convert.py wrote it from
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

VDP1, measured 2026-11-14 (the calibrated Mednafen vdp1_lap.py uses, Three
Seven, both cars poke-driven along build/vdp1cost/path_t7.csv 8 ticks
apart, a cost log every 5th frame for 24 s, each way round): ours averages
83.8-84.0% of a frame, worst 96.5-99.0%, with 7 of about 290 logs over
VDP1's 92.7%; plain CCE 81.1-81.3%, worst 92.6-92.7%, none over. Plain CCE
sits right at the limit in the same spots, and our cars add the 2.7
points that push those frames over: each car costs 0.7-1.0 points more per
half, 2.1 points in all, and the course 0.6 (the turned quads, chosen on 1P
runs). VDP1 draws P1's half, then P2's, each with its own car last, so a
late frame cuts P2's own car: in 11 of the 14 late logs the time ran out
inside it, and P1's car never lost a command. That is the flicker on
player 2's screen (OPEN_ISSUES.md). With CCE's car costs swapped in, the
late logs drop to 2-3. Lighter 2P cars are the main lever.

First try, rejected: DUSA's model 11 (92 vertices, 49 faces), the lowest
detail of DUSA's generic car mesh. Its texture ids follow the same sheet
layout as the body's (DUSA's slot table, 060684EC, gives every bank ids
1-10 and 16-57), but on the Gallop's sheet it came out as a big rear
window over a black tail; the user: "super cursed".

## The 2P cars on DUSA's low-detail car (2026-11-14)

The user asked to try the lighter body for the flicker. Model 11 is the
mid-distance drone of DUSA's own races (DUSA draws it, with no wheels of
its own, for cars 12-35 units from the camera, at most 7 of them). Its
textures index DUSA's drone banks, which is why the first try came out
cursed: drawn with the player's sheet, the ids name other images. So
tools/rebake.py paints each livery onto it again from the livered body:

- Each texel of a model 11 face is a point on the face (VDP1 stretches a
  texture over the four corners: the bilinear mix of the corners). The
  body seen from outside along the face's normal there, the outermost of
  model 0's faces within 0.6 units, gives the colour in both liveries.
  Model 0 lays a transparent overlay (frame, bars) on each window; where
  two of its faces lie on each other the overlay, listed first at sort
  type 1, is on top, as the race draws it (the bars show on the rear
  window).
- Texture sizes come from each face's edges at one texel density for the
  whole car, the one that fills the TEX (38.3 texels a unit, 38,344
  texels, tucked and seated); the floor gets 16 x 16. 99 texels see no body
  face (a few edges) and copy their nearest neighbour.
- The faces fall into 12 groups by place and facing, each fitted to 16
  pairs of colours (liveries.fit_colours) in tables 2-13 and 16-27, so
  patches/livery.s's copy of 16-28 over 2-14 still picks the manual
  livery.
- The rear window keeps DUSA's window texture (table 15, texture entry 48,
  80 x 40, so reflect_2p keeps rotating it; checked for both players over
  60 frames), and the body's overlay goes on as a 50th face on the same
  corners, the overlay at sort type 1 listed first and the window at sort
  type 2, as model 0 has them. The overlay's colours take table 14/28,
  colour 0 transparent.
- The tail tucked in (the user, from the top views: follow the 1P car's
  outline). Model 11 runs straight back at full width (0.82 either side)
  to its tail; the body narrows from its rear wheels (0.83) to 0.65 at the
  tail lamps and 0.56 at the deck and spoiler. Each vertex of model 11's
  last two rings (z 2.38 and 2.46) and the deck's two front corners (z
  1.73, y 0.87) moves in to the body's half-width at its height and length
  (a line from the centre out along x to the body; the nearest body vertex
  in that cross-section where it meets none): 14 vertices, 0.12-0.26 each,
  y and z kept, no faces added. The nose was within 0.05 of the body's and
  stays.
- The wheels seated (the user, from the rear views). Model 11's wheel
  blocks reach down to y 0 and its nose and sills to 0.11-0.14, with square
  sides top to bottom; the body ends at 0.17 (0.24 at the rear wheels' back
  edge, 0.36 under the tail) and its sides narrow from 0.88 at y 0.5 to
  0.84 at 0.17. The Saturn draws a car over the road whatever its depth, so
  the extra showed as tall, boxy dark blocks under the tail. Every vertex
  below the body's lowest point in its cross-section rises to it (x and z
  kept: 32 vertices, up to 0.24), and each outer vertex below y 0.3 (the
  wheel and sill bottoms) moves in to the body's outline from behind at its
  height, scaled to model 11's width (0.82 / 0.88), to 0.78-0.79, so the
  lower sides slope as the body's. The side view keeps its shape above
  0.17. The two wheel faces in front of the front wheels lay wholly below
  the body's bottom and are now flat (a line at 0.17); they stay in the
  list.
- Groups and sizes depend only on the geometry, so every paint gives the
  same MDL, as car_convert.py checks. 1688 of 3972 MDL bytes (under
  reflect_2p's +0xBA0), 51 texture entries, 20,208 of 20,380 TEX bytes.

Pictures: tools/lowpoly_sheet.py draws each livery's 132-face car beside
its model 11 one (build/2p_lowpoly/sheet_a.png, sheet_b.png); in a race
from behind, build/2p_lowpoly/ingame_2p_seat_zoom.png (132 faces, tucked,
tucked and seated, plain CCE).

VDP1, the same way as above but from states made the same way on all
three discs (2P menu from boot, both Hornets, automatic, default views,
saved a second after the green flag; tools/vdp1_lap.py's calibrated
Mednafen), each way round, about 290 logs of 24 s:

| | 132-face body | model 11 | tail tucked | tucked, wheels seated | plain CCE |
|---|---|---|---|---|---|
| both cars, both halves (mean) | 8.0-8.2% | 5.8-6.0% | 6.1-6.2% | 5.9-6.1% | 5.9-6.1% |
| everything else (mean) | 77.3% | 77.4% | 77.4% | 77.4% | 76.8% |
| logs over 92.7%, P2 behind / P1 behind | 14 / 14 | 6 / 5 | 6 / 6 | 6 / 5 | 4 / 4 |
| ...of which P2's own car cut | 11 / 10 | 5 / 4 | 5 / 4 | 6 / 5 | 2 / 4 |

The cars now cost what CCE's own 2P cars do (the tuck's few tenths came
from the same texels at a higher density over smaller tail faces; seating
the wheels took them back off). The late logs left are at
one spot on Three Seven (logs 96-100, the same frames in every build),
where our course costs 4-5 points more than CCE's: the turned quads, chosen
on 1P runs, not the cars.

## Window reflection

In 1P the window comes each tick from an 80-row strip (a 40-row sky image
stored twice) kept in PLCAR09.MDL. PLCAR29 has no room for the strip, so
the 2P routine (reflect_2p, called from the two-player race loop's car
effects call for each player, like 1P's) runs the same scroll state and builds the window from the image
held once, plus its first byte again, at +0x8F0 in each player's
PLCAR29.MDL (tools/rebake.py): from the start to the image's end, then from
its beginning. The state sits at +0x8E0 (the loader puts the next file at
+0xF40, over the trailer): the file start is the undamaged model header
(06056578 + 32 x player) plus its offset back to the texture table, and
the window's VRAM address is texture entry 48's.

Uploads (2026-11-15): neither routine writes VRAM. Each fills slots in the
race block (06018710: source, window, bytes), and the race's list copy in
VBlank-IN DMAs them (win_upload), as DUSA DMAs its window in its VBlank-IN
handler (patches/reflection.s). The first version rotated each texture in
place in VRAM, byte by byte, while VDP1 was drawing: about 1,600 reads and
1,600 writes a player a frame, and a Saturn's VDP1 slows down for every
CPU access to it. That was the flicker on player 2's screen, which plain
CCE doesn't have (OPEN_ISSUES.md); Mednafen shows it only with
`-ss.dbg_hh vdp1rwdrawslowdown`. With an odd start, the image's extra byte
keeps both pieces' lengths and the second's VRAM address even.
Since 2026-11-08 the routine is in a block of SCREEN.BIN, at 06018700
since 2026-11-12
(src/race_block.s, tools/race_block.py), entered through a trampoline at
its old place (0603CAD4) that checks the block's magic word; its cave
holds the replay camera's selectors (docs/conformance.md, "Camera:
replays on CCE's camera").
Like 1P's, the window stops while the crash camera has the car.

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
