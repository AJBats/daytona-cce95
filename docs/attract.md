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
four frames, level for four, then the 3D. CCE's attract runs a demo on
each of its five courses in turn (0601335C holds the demo's number, 1-5,
and the course byte 06054920 is one less), then starts again on Three
Seven; DEMOTTL.BIN is loaded again for each, so the scene code starts
fresh. DUSA's scenes run on DUSA's three courses (see "Dinosaur Canyon
and Seaside Galaxy" below); on CCE's own two, National Park and Desert
City, CCE's demo plays with CCE's camera, opening and ending on the song
by the same clock. (A scene's camera must only run on its own course:
Three Seven's crane on Dinosaur Canyon is off the course, and the road
drawing, 0602A2FC from 06029A78, read through a bad pointer and stopped
on a CPU address error.) The C is built with SH-2 GCC 14.2 in
tools/sh-gcc (gitignored; copied from another project).

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

### Cars (tools/attract_record.py, src/attract.c)

DUSA places a scene's cars from its table (segment, speed, lane) and then
drives them as drones (0600E71A: AI, physics, contacts between them). In
scene 1 the faster cars run into the slower ones in turn 1 (yaw kicks of up
to 37 degrees a tick), and a car far from the camera runs a cheaper mode
(flat, its angles held) until it comes back into range. So the cars are
recorded, not modelled: tools/attract_record.py boots DUSA in the
debugger with no input (the demo is the same every run) and samples its
car array every frame. Each car's draw state comes with it: DUSA's draw
loop (0600B914) skips a car whose flags (+0) carry none of the detail
levels 0x00E00000, about 120 units out; nothing else in the attract moves
the drawn car (+0x1B4 and the crash offsets stay 0).

DUSA's scenes follow one another tick after tick (scene 2's first tick
is the one after scene 1's last; the camera moves to the next scene's
first keyframe on the same tick), 183, 383 and 354 ticks; scene 3 ends
where the demo cuts to the title. Scenes 2 and 3 place the same cars the
same way, but don't run the same (up to 6 units apart from the first
tick), so each is recorded.

The tracks (tools/build_attract.py) ride in DEMOTTL.BIN, one piece per
course: Three Seven 102 KB (three scenes, 19, 20 and 20 cars), Dinosaur
Canyon 53 KB, Seaside Galaxy 54 KB. The race start reads the file whole
to 0x220000 and copies its blocks out (06007D94), then reads the course's
ground file over the buffer, also from 0x220000. Work RAM snapshots
through all five demos: from the ground file's end to 0x2DC000
(CMVDATA.BIN) nothing is loaded or written (0x280000 holds the leftover
logo program, the disc's root file 0, which is loaded again before each
demo). So the pieces go top down from 0x2DC000, Seaside Galaxy's first
(its ground file is the longest, to 0x2AA576), at 0x2A8CC8, 0x2C1C6C and
0x2CEB84; each is past its own course's ground file, and a piece under
another course's ground file is simply loaded over after the copy. The
file (245 KB) outgrows its slot, so tools/mkdisc.py moves it to the end
of the data track; the read makes every cut come about 27 frames later
than with CCE's file, on the song's beat as before.

src/attract.c plays them back: from the cut, each 30 Hz frame puts every
car where it is at that moment by the wall clock (between DUSA's two
ticks around it, as the camera is), sets CCE's detail level (+0x98: 4, 3
or 2 by distance from the camera, as 0603FABE does, or 0 where DUSA
doesn't draw the car), and keeps CCE's AI cars past DUSA's off CCE's list
(count 060529AC, next +0x84), so nothing moves, draws or meets them. At
each scene's first tick every car is placed afresh and the list's count
set; the links always run on to the next car, since the slave CPU walks
the list (0603E60C) while the master sets it (cutting the list with a 0
link crashed Seaside Galaxy's fourth scene, which has more cars than the
third: a walk with the new count ran off the end). CCE's AI cars keep
their own models.

CCE's AI update runs after the attract's tick, on both CPUs (0603E340 on
the master, 0603E394 on the slave, a routine per detail level through the
tables at 0603E388 and 0603E3DC), and it moved each placed car on by CCE's
own state: a step along CCE's path, and the pitch and roll of the road
where CCE had the car (0603EAAA writes them from its segment table). The
per-tick check below reads the cars before that, so it didn't show; on
screen a car near the camera sat rolled and shifted (the "sits
differently" further down). patches/attract.s now sends every level through
ai_gate: while src/attract.c places the cars (ai_hold, 0603CD34, set from
the first attract tick on DUSA's courses, and only in the attract) it
lets CCE's routine run, for what the drawing needs, and puts the car's
position and angles back as placed. Read at the end of a frame, every
AI car now holds exactly what src/attract.c placed.

The slave CPU draws its share of the cars (the job 0603E60C, started from
0603E488) through its own cache. Its AI update purges the cache car by car,
but the last car's lines stay cached, and src/attract.c then places that
car again in the next tick, on the master: the slave drew it once more from
its stale lines, where it was a tick before, beside the master's fresh
copy (found by the user on Dinosaur Canyon, 2026-10-26: car 8, the last in
the list, ahead of the Hornet "jumping every few frames"; in VDP1's command
list those frames hold the car twice, once in the master's commands and once
in the slave's). patches/attract.s now starts the slave's draw job through
slave_draw, which purges the slave's cache first, as its AI update does.
Over the same 50 frames the car's outline no longer changes between ticks.

The detail level is set after the tick's camera: CCE's attract routine,
which runs first in the tick, leaves its own camera in the struct, and the
level came from that camera's distance.

A drone coming back from DUSA's cheap mode jumps to where it should be,
up to 100 units in one tick (Dinosaur Canyon and Seaside Galaxy have
several, one car at a time); DUSA shows the jump on its next 20 Hz frame,
so src/attract.c holds a car whose tick-to-tick move is over 12 units
(4 units is 300 km/h) instead of sliding it across the in-between frames.

Checked per tick at the view build (06029CA0, after the cars are placed
and before they're drawn), from a fresh boot through the whole demo:

| scene | CCE ticks | cars vs DUSA | camera eye | camera angles |
|---|---|---|---|---|
| 1 | 275 | 0.0001 units, 0.005 deg | 0.014 units | 0.35 deg |
| 2 | 574 | 0.0001 units, 0.005 deg | 0.006 units | 0.34 deg |
| 3 | 531 | 0.0001 units, 0.005 deg | 0.011 units | 0.68 deg |

Every car is drawn exactly where DUSA draws it (the opening's tilt
apart, which is deliberate). The demo still cuts to the title 2764
frames after the cut, as before.

The clock is the VBlank count (2026-10-25, the user's first real Saturn
run): CCE's race loop holds 30 Hz only while a tick's work fits in two
frames. Mednafen never drops one here (one 3-frame tick in the whole demo,
at the title), but on a Saturn the busy shots do, and a clock counting
ticks (+2 frames each) let the scenes and the title run late against the
song. At the cut src/attract.c points the VBlank-IN vector at
patches/attract.s's demo_vbl, which counts frames and goes on to the
handler it replaced; the camera and cars read the count. CCE starts the
title by its own tick count (1407), so once the count says the demo is
over (2762 frames, where the 30 Hz demo got there) its tick is brought
up to the title. title_start chains its handler in front as before;
title_leave, in the race's teardown, gives back what demo_vbl replaced.
Checked: in Mednafen the clock reads the same frames as before (the
per-tick table above holds); with 40 frames added to the count mid-demo,
as a run of dropped frames would, the title comes 40 frames sooner; the
vector is demo_vbl through the demo, title_vbl through the title and
CCE's own (06005568) after the title or after Start in the demo.

Side by side at the same moments the shots match: the crane over the
pack, the swoop alongside car 2, the shot behind the Gallop, the
grandstand cranes of scenes 2 and 3, the Gallop through the turn. Still
different: CCE's ranking table and Press Start, where DUSA has its AM2,
SEGA and copyright marks and from scene 2 its own scrolling Ranking;
CCE's car models (the AI cars are CCE's); CCE's trackside scenery. A car
close to the camera also sat differently on screen: CCE's AI update had
moved it after the placement (see Cars above; fixed 2026-10-26).

### Dinosaur Canyon and Seaside Galaxy (2026-10-26)

DUSA's demo picks its scene list by course (0605F5EC + 4 x course; a
second set at 0605F62C, chosen by a flag never set from boot) and plays
920 ticks, but 60 fewer on Seaside Galaxy (06008984: 0x398, minus 60 for
course 2), so its title comes 3 s earlier in the song. From boot with no
input DUSA plays Three Seven, Dinosaur Canyon, Seaside Galaxy, each
opening on the song (its Play command for track 3 just before each cut),
and round again.

| course | scenes (ticks) | cars | DUSA demo frames (state 2 -> 3, 4 -> 5) |
|---|---|---|---|
| Three Seven | 183, 383, 354 | 20, 21, 21 | 1244-4009 |
| Dinosaur Canyon | 920 | 10 | 5326-8091 |
| Seaside Galaxy | 123, 103, 103, 531 | 18, 12, 8, 10 | 9472-12057 |

tools/attract_record.py records all three in one boot. A demo's first
scene starts on the first car tick after DUSA's attract state goes to 3
(state 2 places the cars once before); a later scene where at least 8
cars jump and every active car does (single cars jump mid-scene too, back
from the cheap mode). Three Seven's recording is the same as before, bit
for bit.

src/attract.c keeps one keyframe table and a scene list and cars piece
per course (dusa_attract.h). CCE has 19 AI cars in its Dinosaur Canyon
demo and 29 on Seaside Galaxy, more than DUSA's 9 and 17. The demo ends
by the wall clock on every course: 2762 frames after the cut, 2582 on
Seaside Galaxy; on CCE's own courses too, so a Saturn that drops frames
there still brings the title in on the song.

The title holds 600 frames as DUSA's, but 780 on Seaside Galaxy
(patches/title.s: title_tick sets the limit, and title_vbl's cut to
black, from the course), so the song, which starts 3 s earlier against
the title there, still ends under it. (DUSA's own credits cut the song's
last second there.) CCE's own title timeout moved to tick 2400, past the
title's end at any tick rate.

Checked:
- Every demo opens on the song: from boot, the cut comes 5-6 frames after
  the drive reaches PLAY on all five courses (cuts at 2173, 6799, 11531,
  15771, 20388), as the first did.
- The title comes 2765 frames after the cut on Dinosaur Canyon, 2587 on
  Seaside Galaxy (the cut to black after 604 and 784 frames), and at
  2738-2768 on National Park and Desert City.
- Per tick at the view build: every car within 0.0001 units and 0.005
  degrees of DUSA's on Three Seven and Seaside Galaxy (0.13 units on
  Dinosaur Canyon, at a 12-unit jump); visibility as DUSA's.
- The camera against DUSA's own every frame on Dinosaur Canyon: eye
  within 0.06 units, angles within 0.2 degrees.
- From a fresh boot with no input through all five demos twice (46000
  frames, 13 minutes): no exception, on either CPU.
- A 1P race through the menus (the menu script shifted 27 frames for the
  longer load) with and without the AI gate: every AI car and the player
  car at the same place in all 36 samples over 900 frames, bit for bit.
- Side by side at the same demo times the shots match. Still different:
  CCE's scenery (on Seaside Galaxy DUSA's bridge has a stone tower CCE's
  hasn't; on Dinosaur Canyon CCE's rock walls sit nearer the road), CCE's
  ranking overlay, and the close pass beside car 0 on Seaside Galaxy
  (about 51 s into the demo, 1.5 s long), where CCE doesn't show the
  player car's body 1.5 units from the camera. Its polygons are in
  VDP1's command list (unmarked, in front, last in the list, as the
  nearest thing), but VDP1's framebuffer holds only the road and the
  hill: the camera is 0.6 units above the road there, so the road
  polygons next to it are huge (CCE clamps them at x -512..512) and
  VDP1 most likely runs out of time at 30 Hz before it reaches the car.
  DUSA has a 20 Hz frame for the same shot. Not fixed.

Done: the opening, the title, and DUSA's camera and cars on its three
courses; CCE's own two courses keep CCE's demo on the same clock.
