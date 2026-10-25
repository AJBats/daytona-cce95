# Attract mode: DUSA vs CCE

The user's goal (2026-10-24): CCE95's attract like DUSA's, with DUSA's sound
and camera work. It should open at once on the Daytona theme and DUSA's
opening shot (CCE fades in), and end with DUSA's DAYTONA USA logo sliding
in with a crash shake. Start there fades into CCE's main menu (today CCE's
title crossfades in over its demo).

## Survey (2026-10-25, boot with no input, frame = 1/60 s)

Screenshots every second and around each transition, audio recorded, CD
Block commands traced (scratchpad attract/).

DUSA:

| frames | |
|---|---|
| 360-660 | Saturn logo, SEGA licence |
| 720-1244 | black (loading); CD track 3 starts ~1.9 s before the cut |
| 1248 | hard cut to the demo: a sky shot tilting down onto Three Seven's straight as the rolling-start pack comes at the camera |
| 1248-4008 | demo race, trackside and chase cameras, PRESS START BUTTON, AM2 logo top right, ranking table scrolling over it from 2280 |
| 4010, 4012 | one black frame, one green frame |
| 4014-4034 | white striped title background at once; a pale ghost of the logo in place; the black DAYTONA USA logo slides in from the left |
| 4034-4040 | arrival shake (doubled letters) |
| 4078- | PRESS START BUTTON blinks; the title holds to ~4600 |
| 4620-5280 | white credits: SEGA, AM2, SEGA SPORTS; CD track 2 (9 s jingle) from ~4520 |
| 5340- | the next demo, Dinosaur Canyon, with its own ranking; the cycle goes on |

DUSA's attract music is its CD track 3 (57 s; the recording matches it at
0.99 from 18.8 s to 75.8 s, so it carries on under the logo and title);
track 2 is a 9 s jingle at the credits. Neither is on CCE's disc (best
match against all 30 CCE audio tracks: 0.29).

CCE:

| frames | |
|---|---|
| 360-1980 | Saturn logo, SEGA licence, SEGA SPORTS, trademark notice; silent from ~540 |
| 2090-2100 | the race start plays CD track 18 (94 s) |
| 2100-2150 | fade in from black to a trackside shot of the pack mid-race; the song comes in at 2131, mid-fade |
| 2160-6720 | demo race on Three Seven: ranking table from the first frame, high and overhead cameras; track 18 under the race sounds |
| 6720-6900 | the DAYTONA USA CIRCUIT EDITION title crossfades in over the still-running demo |
| 6900- | title with Press Start Button; track 18 plays on (80 s in at 6800) and fades out by itself at its end |

Music level, fitting each recording to its CD track sample by sample in
2 s windows: DUSA's track 3 at gain 0.42 (the track explains 96% of the
recording's power), CCE's track 18 at 0.41 (90%; CCE's demo race is a
little louder). Both tracks open with 2 s of silence, so a play command
is heard 2 s later.

## The opening (patches/attract.s)

make disc appends DUSA's track 3 as track 32 and track 2 as track 33
(tools/mkdisc.py --append). The attract demo plays track 32 in place of
18. CCE's fade-in is held black until the CD drive is playing audio, then
the colour offsets go to their targets in one call (the fade engine's
state 2), so the demo appears on a hard cut. The hold only takes fades
in (offset below its target): fades out, as after Start, run as CCE's.

Measured from boot with no input (CCE95's frames moved by the appended
tracks, so they aren't vanilla's):

| | DUSA | CCE95 |
|---|---|---|
| song's play command | 1230-1240 | 2090-2100 |
| first beat (track 2.0 s) | 1245 | 2147 |
| hard cut | 1248 | 2146 |
| music gain | 0.42 | 0.40 |

## The title (patches/title.s, tools/title_convert.py)

DUSA's title, frames from its first slide frame (t = 0), from register
dumps every frame:

| t | |
|---|---|
| -4 to -2 | display off |
| -1 | display on, one green frame: the back colour, before the background layer has its map |
| 0-21 | NBG3 (the black logo) X scroll 336 - 16 t: it slides in from the left; DUSA writes two more map columns a frame so it doesn't wrap round |
| 23-30 | the shake: X -8, 8, -4, 4, -2, 2, -1, 1 |
| 31-61 | X -1 on odd frames, 0 on even ones |
| 64- | PRESS START BUTTON (NBG3 rows 23-24) 4 frames on, 4 off |
| 600 | display off, then the credits |

NBG2 is the white striped background with a pale ghost of the logo, which
shows beside the black one as a drop shadow. Both are 16-colour 8x8 cells.
In SCROLL.BIN, LZSS streams: at 0x400 the 556 chars (DUSA decompresses
them into VRAM at the title), at 0x7643 a font holding PRESS START BUTTON
as 22 x 2 cells, at 0x8F84 the logo map, at 0x9374 the background map.
The palettes are in APROG.BIN. Start: DUSA holds 15 frames, then cuts to
its game select.

CCE's attract keeps its own title loaded through the demo: DEMOTTL.BIN, a
list of blocks for VRAM, CRAM and work RAM the demo doesn't use. At tick
0x906 of the demo (77 s) it crossfades the CIRCUIT EDITION title in over
the demo in hi-res, then shows it still for 15 s.

CCE95 instead:
- tools/title_convert.py writes DEMOTTL.BIN from DUSA's files: the chars,
  the PRESS START cells and both maps, staged in VRAM at 0x40040, and the
  palettes into CRAM palettes 48, 49 and 53.
- The demo ends at tick 1407 (46 s). The first black frame is 2760 frames
  after the opening's cut, as in DUSA, and the song carries on under the
  title, ending 8 s in, as in DUSA.
- title_start (in place of CCE's title start, 0602F564) waits for VBlank,
  turns the display off, and copies chars and maps to DUSA's VRAM banks.
  It sets VDP2 as DUSA's title, except that NBG3's plane is 2 pages wide
  with the second blank, so the logo slides in without wrapping round. It
  stops the race drawing as CCE's still title does.
- The attract runs at 30 Hz, so the title's frames run from the VBlank-IN
  interrupt: title_vbl is chained ahead of CCE's handler while the title
  is up.
- title_tick (in place of CCE's blink, 0602F7C0) ends the title at t = 600
  as CCE's timeout.
- Start, or the timeout, goes through CCE's fade to black. In the race's
  teardown, title_leave gives the VBlank vector back and restores the
  registers CCE's own title never touched (PLSZ, PNCN2, NBG2's map,
  PRISA) to the race's values.

Checked frame by frame against DUSA, side by side:
- The four frames between the demo and the slide.
- The logo's position in every slide and shake frame (the same pixel).
- PRESS START's blink.
- The song's level under the title (it explains 93-98% of the recording,
  DUSA 87-95%).

Checked on the way out:
- Start fades to black in 36 frames, then CCE's main menu loads and fades
  in.
- After the timeout come CCE's logos and the next demo, Dinosaur Canyon,
  with the title again.
- From the menu, an arcade race looks and plays as before.
- Start in the demo still goes to CCE's title page.

Differences from DUSA:
- DUSA's green frame is black here.
- Start fades out (the user's choice) where DUSA holds and cuts.
- After the timeout come CCE's logos rather than DUSA's credits. The user
  is happy with that loop (2026-10-25): no credits.

## Camera work (src/attract.c, tools/build_attract.py)

DUSA's attract on Three Seven is three staged scenes, not one race. Each
scene places 20-21 cars (a track segment, speed and lane each; 0601FEC0)
and runs its own camera; at the cut to the next scene every car jumps.

| scene | DUSA frames | cars | where |
|---|---|---|---|
| 1 | 1249-1795 | 20 | a two-wide pack at full speed on the main straight, the Gallop last, to turns 1-2 |
| 2 | 1798-2944 | 21 | the back straight round to turns 1-2 |
| 3 | 2947-4008 | 21 | the same stretch, the same placement, other camera work |

The camera (060055BC) runs through 32-byte keyframes in 20 Hz ticks: a
camera position and a point it looks at, each fixed in the world or riding
with a car (car + Ry(yaw) Rx(pitch) Rz(roll) point, fitted to DUSA's own
camera to 0.01 units); linear between keyframes; a keyframe at time 0
starts a shot, -1 jumps. The look-at (06005294) has no smoothing: yaw =
-atan2(dx, dz), pitch = atan2(dy, d), d ~ 0.924 max + 0.383 min of |dx|,
|dz|. Scene 1: a crane down beside the straight looking at car 4 (8 to 4
units up over 1.6 s), a swoop alongside cars 2 and 1, then behind the
Gallop.

DUSA's opening tilt is a side effect of its pipeline: its sky and ground
(VDP2) follow the new camera at once, its 3D (VDP1) two ticks later. So
the first three frames show sky and ground alone with the horizon low,
the next four the same level, then the scene.

CCE95: the attract's tick (060285AC) runs src/attract.c from work RAM
(002E2780, loaded with DEMOTTL.BIN, where CCE kept its title's map). It
calls CCE's tick, then sets CCE's attract camera (the struct at
*06052094: pivot, pitch/yaw/roll, offset 0 so the eye is the pivot) from
DUSA's keyframes, built at build time from DUSA's APROG.BIN, with CCE's
atan2 (06047E0C). It keeps DUSA's keyframe logic in 20 Hz ticks and
interpolates for CCE's 30 Hz. DUSA's car n is CCE's player car for 0 and
the n-th AI car (060FD400 + 0x100 (n - 1)) otherwise: CCE's AI cars keep
position at +0 and pitch/yaw/roll at +0xC, as the player car does. The
opening: sprites off from the cut, the camera tilted up 45 degrees for
four frames, level for four, then the 3D. The C is built with SH-2 GCC
14.2 in tools/sh-gcc (gitignored; copied from another project).

Checked numerically, not by eye (2026-10-25), with a Python model of
DUSA's camera (the keyframes from APROG.BIN, the car transform, the
look-at), each game recorded every tick:
- The model against DUSA's own camera, from DUSA's keyframe pointer, time
  and cars of the same frame: within 0.013 units and 0.3 degrees over
  scene 1 (552 frames). With the cars of the frame before it is 3.5 units
  off, so DUSA's camera reads the cars after they move.
- CCE95 against the model, from the cars its camera read (sampled with a
  breakpoint at the tick's entry, 002E2780): within 0.003 units and 0.11
  degrees on all 270 ticks, apart from the opening's deliberate tilt.
  Samples at frame ends aren't enough: CCE's 30 Hz loop drifts against
  the 60 Hz frame, so a frame-end sample sometimes holds the cars of the
  next tick. Watchpoints show that the camera and the car draw read the
  same car state every tick.
- DUSA against CCE95 at the same scene tick: the eye of the opening crane
  (fixed in the world, ticks 0-33) is the same to 0.01 units. Everything
  that rides with a car or looks at one is off by exactly where CCE's
  cars are. DUSA's pack is two lanes, 8 units apart, from x 157 back to
  76, at 68-84 units/s, faster at the front. CCE's demo race has its cars
  spread over 435 units at 55 units/s: car 4 starts 66 units nearer the
  camera, so the crane whips round it 0.5 s early.

Time base: DUSA's camera steps at 20 Hz and holds each step for 3 frames.
CCE95 steps at 30 Hz. Every sixth frame (each 1/10 s) both show the same
instant; between those, CCE95 shows in-between positions.

Done so far: scene 1's camera, and the opening. Next: DUSA's cars for
scene 1 (placement and motion), checked per tick against DUSA's cars and
then the camera as above, then scenes 2 and 3.
