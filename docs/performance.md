# VDP1 performance

## The frame budget

CCE holds 30 frames a second whatever VDP1 has left to draw (the user's
call, 2026-11-07: dropping frames to finish them felt far worse,
patches/probe/vdp1_wait.s). A frame VDP1 hasn't finished goes out cut short:
the polygons at the end of its list, the player's car first, are missing.

The kernel's protocol (DAYTONA/0, docs/findings.md): the main loop runs the
race program, marks the list ready (06011F89) and waits. At the next
VBlank-IN that finds it ready with a vertical blank gone by (06005568), a
VBlank task copies the list over VDP1's command table (06047B90, a DMA to
25C00000 and 25C06000) and the VBlank-OUT after that changes frames
(06005652 -> 060071AE, FBCR = 3); VDP1 starts on the new list there
(PTMR 2). So VDP1 has from one VBlank-OUT to the VBlank-IN two fields on,
486.5 of 525 lines: 92.7% of a 30 fps frame. If it's still drawing at the
copy, it carries on with the new list's commands from where it is and the
change stops it.

The first probe (patches/probe/vdp1_late.s) reads EDSR's BEF at the change.
It misses most cut frames: after the copy VDP1 often reaches the new list's
end before the change and reports the list done.

## Measuring: tools/vdp1_lap.py

The Tomb Raider project calibrated its Mednafen fork's VDP1 and SH-2
timing against a real Saturn (TombRaiderSaturn tools/mednafen_timing.py:
within 3% of a frame on its scenes), and its `vdp1_cost_log` command
writes a frame's VDP1 commands with each one's cycles, lines, pixels and
texels. The user: that tuning is a little pessimistic against a real
Saturn, so it compares builds; the Saturn has the last word.
tools/vdp1_lap.py runs it (tools/mednafen/mednafen_tr.exe, a copy)
beside the debugger and drives the chase camera round a lap: the player car
is put, each tick, where a drone was at that tick of the same race
(build/vdp1cost/path_<course>.csv, recorded once, so builds compare on one
path), with travel and heading as the drone's yaw. A cost log every 10
frames, 190 of them. A frame VDP1 didn't finish has no log of its own: the
log runs on into the next plots (the logs with two or three thousand
commands, and the numbers missing from the f*.csv files).

## The race start on Three Seven (2026-11-07)

Twelve frames over the six seconds after GO, plain CCE against ours
(cars all around, 82.2% against 84.5% of a frame on average, 86.2%
against 87.9% at worst). Ours draws 2.9 screens of pixels to CCE's
2.3-2.5: DUSA's chase camera sits lower and pitches down further, so the
road and grass near the camera fill more of the screen (faces over 4096
pixels: 23-27% of a frame against 14-15%), and our car is bigger in the
picture (about 11% against 8%).

## Laps (2026-11-07)

Each run's races start on the same frame (tools/vdp1_lap.py's menu inputs),
so runs of one course compare frame for frame. Mean over the frames both
runs of a pair finished; then the logs over 92.7% or unfinished, of 190.

| course | plain CCE | ours, CCE's camera | ours |
|---|---|---|---|
| Three Seven | 76.5%, 4 | 80.1%, 7 | 82.0%, 34 |
| Dinosaur Canyon | | | 75.7%, 0 |
| Seaside Galaxy | | | 84.2%, 34 |
| National Park | 84.2%, 16 | 83.7%, 12 | 105.2%, 126 |
| Desert City | | | 77.0%, 5 |

(Plain CCE and CCE's camera: means over all their logs.) With CCE's chase
framing (a test disc, framing_cce in 1P races: patches/camera.s) our build
costs VDP1 about what plain CCE does. DUSA's framing is most of the extra:
its camera is low and pitched down 18.3 degrees (CCE's 6.5), with a wider
lens (160 to CCE's 224), so the road and verge just ahead project huge and
far past the screen's sides. VDP1 spends its time on a polygon's pixels
off the screen as on those on it: in a heavy National Park frame one near
quad ran from x -512 to 89 and drew 57,000 pixels, another 74,000.

## Turned quads (tools/turn_quads.py, tools/turn_choice.py)

VDP1 draws a textured quad as lines from edge A-D to edge B-C, as many as
the longer of the two is long on screen, each with a fixed cost (about 26
cycles calibrated) besides its pixels and texels. Turned a quarter (drawn
from B, its texture turned under it) the same picture takes as many lines
as A-B or D-C is long. But most course quads are trapezoids in
perspective, and turned, their lines all start from the narrow edge and
pile up there: more pixels than the lines saved. An estimate from the
edges alone (Tomb Raider's tools/vdp1_cost.py, which holds pixels the same)
chose textures that made Dinosaur Canyon worse, 75.7% to 85.3% with 50
frames over. Turning every texture that can turn cost 6-12% of a frame.
So tools/turn_choice.py measures: a run with nothing turned against one
with everything turned, and keeps the textures whose quads drew faster:

| course | textures kept | mean before -> after | over or unfinished |
|---|---|---|---|
| Three Seven | 78 of 214 | 82.0% -> 80.0% | 34 -> 38 |
| Dinosaur Canyon | 48 of 222 | 75.7% -> 73.1% | 0 -> 0 |
| Seaside Galaxy | 69 of 284 | 84.2% -> 82.8% | 34 -> 31 |
| National Park | 34 of 148 | 105.2% -> 94.6% | 126 -> 97 |
| Desert City | 43 of 229 | 77.0% -> 76.4% | 5 -> 4 |

No VDP1 VRAM and no CPU time: the textures turn in place in the course
files. Checked in the debugger: the courses draw as before.

## Stepwise frames and the next steps (2026-11-07)

tools/stepwise.py on two frames VDP1 didn't finish (National Park log 10,
102% of a frame; Three Seven log 28, 99%): four or five near course quads
cost 9-12 ms, stepping 115-183k pixels for 38-40k on the screen; two
thirds of all the pixels stepped in the National Park frame are off it.
Faces under 64 pixels cost 11-16% of a frame (about 400 cycles each
however small: the command and its lines; the smallest are slivers of
16-24 lines for a dozen pixels).

VDP1 skips a line wholly outside the clip window cheaply but steps every
pixel of one that crosses it, so a near quad's cost is in its long lines
across the screen's edge. tools/vdp1_rewrite.py rewrites a captured list
and draws it again (the same VDP1 code):

- bands of texture rows alone (cutting along A-D): no gain, the waste is
  to the sides (+0.2 to +1.1% of a frame);
- the heavy quads cut both ways, from copies of their textures in column
  strips 8 or 16 wide, the pieces wholly off the screen left out: National
  Park 102.4% -> 85.3% (two quads, 4 KB of strips), Three Seven 99.2% ->
  95.0% (two, 3 KB);
- each quad turned whichever way is cheaper: -7.9 and -1.6 there; over
  81,586 quads of 300 lap frames, -5.1% of a frame on average. The rule
  "turn when 26 x lines + pixels, both estimated from the corners, is 5%
  less turned" gets 70% of that.

Free room: about 19 KB of VDP1 VRAM on every course (the tail of our car's
texture area), 33 KB on National Park; work RAM that stays zero through a
race: 06015140 (16 KB), 060D8C98 (81 KB), 00200020 (133 KB) among others.
The master SH-2 works 65-74% of a frame on Three Seven (it must hand the
list over by about 92.7%).

The course quads' commands are built by 06045E44 (draw mode, colour
table, texture and size from the course's texture record, relocated at
load, through [r14+40] + the polygon's word) and their corners written by
0604698C's paths (060469F4 for a quad in view) into the list at 0601B000,
linked into depth buckets by 06045E06.

## Race-time quads (src/vdp1x.c, 2026-11-07)

The heavy near quads cut in the race itself, as the offline rewrite above
did them. src/vdp1x.c runs once a frame, at the race frame's last call
(patches/vdp1x.s, through the literal at 06028EA0), when the list is whole:
every command built and linked into the depth order. It is a block of
SCREEN.BIN (tools/vdp1x.py), which CCE's block loader copies to work RAM
06015140 at every race start; the attract never loads it, and the stub
checks for its magic word.

The list: VDP1's command table at 0601B000, in two areas, slots (8 bytes)
0 on and 0xC00 on (06021000), each with its count of slots used and its
limit at 06057888 and 06057C88 (the VBlank task 06047B90 copies each area
to VRAM by its count, so pieces added at an area's end go too). Course
quads are in both. Most jump to their link (control 0x1000); near-clipped
pieces CCE chains by place (control 0, on to the next command), and those
are the biggest quads of all.

A quad is cut when its texture has strips (copies of its columns, 8 or 16
wide, made from VRAM at the race's first frame into the course's free VRAM
after a check of each texture's sum), it is estimated over 50,000 cycles
(26 a line plus its pixels, from the corners) and it isn't wholly on the
screen: pieces by strip and band of 32 rows, corners bilinear across the
quad and shared between neighbours, mirrored quads' pieces keeping their
flips, the pieces wholly off the screen left out. The first piece takes
the quad's place and jumps to the rest at its area's end; the last jumps to
where the quad went. tools/vdp1x_eval.py builds src/vdp1x_core.c (the
decisions) for the PC and runs it over lap logs, costing every quad as
drawn and as cut, and chooses each course's textures by frame time saved
over 85% of a frame, a byte of VRAM at a time (tools/vdp1x_choices.json).

Laps against the static turned quads' (final runs), frame for frame:

| course | mean | over 92.7% or unfinished |
|---|---|---|
| Three Seven | 80.5% -> 76.7% | 34 -> 6 |
| Dinosaur Canyon | 73.1% -> 72.3% | 0 -> 0 |
| Seaside Galaxy | 82.4% -> 77.4% | 30 -> 10 |
| National Park | 97.9% -> 79.1% | 88 -> 2 |
| Desert City | 76.4% -> 68.0% | 4 -> 0 |

The pass costs the master SH-2 time every frame (from the race program's
call, 06028000, to the list marked ready, 0600529A, 400 frames from the
race start; no frame late in either):

| course | before | after (worst) |
|---|---|---|
| Three Seven | 67.8% (77.8%) | 72.2% (82.6%) |
| Seaside Galaxy | 68.0% (83.5%) | 74.2% (84.7%) |
| National Park | 70.3% (80.5%) | 73.6% (82.9%) |

What it took to get there, measured the same way:

- Through every quad's submit (a hook on the course loop's call of
  06045B74): 12% of a frame more on Three Seven, 23 frames of 200 late.
  The call and the cache misses on each quad, not the work.
- Each quad also drawn turned whichever way is cheaper (copies of textures
  turned a quarter): as dear as the cuts in CPU time, for 2-3% of VDP1 on
  average and hardly a frame fewer over. The course files' quads stay
  turned where that pays on the whole (tools/turn_quads.py); nothing turns
  at race time.
- The SH-2 shifts a value by a variable, or a signed value right by more
  than one bit, only through library calls (___ashrsi3, ___ashiftrt_r4_n):
  the cut's sums are unsigned, of coordinates biased by 2048.
- SCREEN.BIN outgrew its sectors; moved to the data track's end, the race
  start took 15-30 frames longer in Mednafen. tools/mkdisc.py now keeps it
  in place and moves its neighbour RESULT.BIN (read only at a race's end)
  to the end instead.

## Late frames, and a trim that didn't work (2026-11-08)

Exact late frames: patches/vdp1x.s registers a stub in place of the race's
list copy (06047B90, a VBlank task the kernel runs in its VBlank-IN handler
when it takes a list, VDP1's deadline). It notes whether VDP1 was still
drawing the list the copy replaces (0603E438: 1 when late) and counts those
frames (0603E43C). Over the lap tool's lap (1900 frames), with the trim
below held off by a poke (the same disc and states):

| course | before (static turned quads) | cut |
|---|---|---|
| Three Seven | 192 | 18 |
| Seaside Galaxy | 141 | 38 |
| National Park | 450 | 3 |

A scripted spin on National Park's grass (770 frames, B accelerates, C
brakes): 51 late frames before, 16 with the cut.

Plain CCE (build/disc_vprobe, the probe's count at 0600A904; tools/vdp1_lap.py's
menu inputs land on 2PLAYER BATTLE there, UP UP C reaches Arcade) has no
late frame on any of these laps or in the pack from the start in Mednafen,
yet on the Saturn (build/flicker_hw/probe_cce1.mkv) it flashes six times in
about 70 seconds of Dinosaur Canyon, in traffic and spinning on the grass,
once without the car. The lap tool can't tell how close to CCE we are; the
Saturn can.

The trim, tried and taken out: after a late frame, leave the course
scenery's smallest faces (diagonal under 6 to 20 pixels) out of the next
lists, easing off with VDP1 headroom. It took Seaside to 9 late frames a
lap, Three Seven to 1, the spin to 5, but CCE's distant road and terrain
are many small faces: at 12-20 pixels the far road broke into gaps over
the background (judging by one diagonal also dropped long slivers near the
camera), and switching on and off with the load it would flicker. Visual
comparison: build/trim_compare/index.html.

Also left out: the polygon CCE draws first over the screen's bottom 42
rows in colour 0 (clearing them, 2% of a frame); the course covers those
rows in the chase and in-car views.

Master CPU, 400 frames from the race start, with the trim (before -> after,
mean and worst): Three Seven 67.8/77.8 -> 72.8/83.4, Seaside 68.0/83.4 ->
73.5/83.6, National Park 70.3/80.5 -> 72.3/82.0, Desert City 69.0/81.7 ->
72.9/87.7; no frame late. Without it the pass does less.

Measuring pitfalls met on the way:

- A save state keeps the game's file table from its own boot (low work RAM
  around 0x2FF98C: FAD, size, name). Loaded with another disc build, files
  are read with their old sizes: SCREEN.BIN's tail never arrived and the
  block's last few hundred bytes were stale buffer contents. Make a fresh
  course-select state for every build.
- SH-2 shifts by a variable or arithmetic shifts of more than one bit call
  library routines; a helper GCC didn't inline at -Os cost as much as the
  scan. The block is built at -O2.
- The dynamic texture turning offline (heaviest fifth of lap frames): a
  copy-free variant for square noise textures would save under 2% of a
  frame; not done.

## Dropped frames on the Saturn, and the pass's deadline (2026-11-08)

On the Saturn, the cut-only build gave Three Seven's pack dropped frames
(a picture held a third field: about 50 a minute in bursts in the user's
recording, build/hw_vx/play_nodetect1.mkv, counted as repeated frames of
the 30 fps capture), in traffic, at the start/finish line and with the TIME
EXTENSION and BEST LAP messages up. Plain CCE (Dinosaur Canyon) and the cut
build on National Park the night before showed none but the capture's own
slips, one every 11.7 seconds.

In Mednafen, driving into Three Seven's pack from the start (B held, 450
frames from 06028000 to the list marked ready at 0600529A): plain CCE 75.1%
of a frame on average, 87.0% at worst; ours without the pass 74.4/87.7;
with it 78.6/92.6. The pass costs 4.2% of a frame there (4.9% in the
heaviest tenth), mostly the scan over every command (each one a cache miss
on the list). A real Saturn's master runs slower than Mednafen's, so those
four points tipped the heaviest frames past two fields.

A frame's timeline (Three Seven's pack, in frames from the kernel taking
the last list): the race begins its work at 0.075 and zeroes the master's
free-running timer then (0600730A from 06028170: FRC at phi/128, about
7,480 ticks a frame); the pass runs around 0.74-0.80; the race still works
about 0.09 more before it marks the list ready (0.87-0.95); the kernel's
next chance is at 1.003. The pass now reads the timer every 64 commands and
stops past 5,800 ticks (src/vdp1x.c, VX_LATEST), so on the Saturn it cuts
fewer quads in the heaviest frames instead of delaying them. In Mednafen
the laps lose nothing (National Park 3 late frames, Seaside 34, Three Seven
17) and the pack's worst frame is 90.2%, none late. A test build that stops
it at 5,100 (VDP1X_CFLAGS=-DVX_LATEST=5100 make disc, into another folder)
cut the pass to 2-2.7% and drew correctly, with more late VDP1 frames.

Two traps on the way: patches/vdp1x.s's cave isn't dead all through, the
dead function's literals at 0603E448-0603E453 are loaded by live AI code
(a longer stub there froze the attract); and the timer read in the list
copy stub, before the race zeroes it, is useless as a frame start.

## Car effects out after a late frame (2026-11-08)

Replaced by drawing them last ("Car effects drawn last", below).

The visibility audit (240 captured frames rendered command by command with
the Mednafen fork's VDP1 code) put the car effects at a few points of a
frame in the heavy moments: CAREFC.TEX's tire smoke, a 32x32 speckle
sprite drawn large behind the car (up to 6.6% of a frame in a Dinosaur
Canyon drift), and its three 48x48 frames of sparks. The file's other
pictures (the cars' wheels among them) stay. The race loads CAREFC.TEX
after the course's TEX and its objects', each from the 32 bytes the one
before ends in; tools/vdp1x.py works out each course's places and sums,
and the block checks them before using them.

After a frame VDP1 didn't finish in time (patches/vdp1x.s's late flag), the
pass leaves the smoke and sparks out of the next 30 frames: they come and
go anyway, and the frames that follow lose them instead of the list's end
(the nearest things, the player's car). The same disc and states, with the
flag held at 0 by a poke for the control:

| run | late frames, effects kept | effects out after a late frame |
|---|---|---|
| National Park grass spin (770 frames) | 16 | 4 |
| Three Seven pack (1010 fields) | 13 | 8 |
| Dinosaur Canyon pack (1010 fields) | 24 | 15 |

In the spin the smoke showed in 34 of the 51 logged frames it was in
before.

## Cutting as CCE builds the list (2026-11-08)

The pass over the whole list cost the master 4-5% of a frame in Three
Seven's pack, almost all of it reading every command back (a cache miss
each) to find the few worth cutting. Now the cut happens while CCE builds
the list, polygon by polygon, and only for the polygons that can need it.

CCE's polygon routines (06045BC4 for quads, 06045C00 for triangles, which
the near plane's pieces go through too; 06045A2C and 06045A7E for models
wholly in view, the cars and their effects) write a polygon's commands at
the list area's end (slot @(136,gbr), @(155,gbr) slots of them), then link
them into the list for the polygon's depth (06045E06, a first and a last
slot per depth in the table at r14+32) and move the count past them.
patches/vdp1x.s gives them one tail that first tests the polygon's
attribute: bits 14 and 15 are set on no polygon in CCE's models, and CCE
masks them off wherever it reads the attribute. tools/vdp1x.py sets bit 14
on the course polygons drawn with a texture that has strips (1,114 to 7,250
a course) and bit 15 on the car effects' smoke and sparks (33 polygons in
CAREFC.MDL). A marked polygon goes to the block (its emit entry at
06015140 + 28, while its magic word is there): a course polygon of one
command CCE found wholly on the screen (pre-clipping off, 060469F4) or
under 96 pixels across goes straight on, in a few instructions; the rest
go to src/vdp1x.c's vx_emit, which cuts the quads worth it into the
polygon's place, links the pieces itself and moves the count, or leaves
the polygon to the tail. A car effect while the effects are out is left
unlinked and uncounted: not drawn. Every unmarked polygon costs three
instructions.

The effects first went through the course's model draw (06045958) to
reach the tail; its near plane dropped the nearest smoke puffs (13 of 34
frames in the grass spin differed from CCE's, same state, same frame), so
the draw stays CCE's and only its link moved.

Three Seven's pack from the start (B held, 450 frames from 06028000 to the
list marked ready, mean / 90th percentile / worst, % of a frame):

| build | master work |
|---|---|
| the pass over the list (76ffdfd) | 79.9 / 88.1 / 90.4 |
| cutting as CCE builds the list (0b2a5d8) | 76.9 / 84.3 / 89.0 |
| the same, the estimate in the emit entry | 76.2 / 83.6 / 88.9 |
| either, block held off (magic poked away) | 74.4-74.9 / 81.9-82.4 / 87.7-88.2 |

So the cut costs about 1.5 points of a frame where the pass cost 5.5. A
profiling build (VDP1X_CFLAGS=-DVX_PROFILE) told where: at first 11.5
polygons a frame went into vx_emit and 1.4 were cut; the other ten, turned
away by the estimate (under 50,000 cycles), cost about 1,000 cycles each
(the C function's code and tables miss the caches between polygons), 1.1%
of a frame. The emit entry now works out vx_estimate's sum itself, in
assembly on the command it already has in hand; 1.9 polygons a frame reach
the C function, 0.84% of a frame. What's left, per frame: about 0.74% in
the 1.4 cuts (some 5,000 cycles each: the grid about 3,000, 2,200 of it
with warm caches, then writing and linking the pieces about 1,000), about
0.45% for the 75-135 marked polygons that only pass through the entry
(magic check, a cache miss on the command's draw mode), about 0.25% for the
three instructions on each of the 700-1,000 other polygons. Built for size
(-Os) it cost the same.

The same pictures: over the lap tool's lap of Three Seven the course's own
commands (its texture file and the strips) cost VDP1 65.3% of a frame on
average both ways, frame for frame within 0.01% on average. Late frames a
lap moved with the traffic (a new build shifts the race's timing): Three
Seven 13 -> 18, Seaside 26 -> 38, National Park 3 -> 3, Dinosaur Canyon and
Desert City 0 -> 0-1. In the grass spin with the late flag held at 1, no
smoke or spark command reached the list (126 in 21 frames otherwise).

## Turning chosen by the heavy frames (2026-11-08)

The user's Saturn race on Three Seven lost the car in a storm on the straight
past the rocky overpass, a drone big beside the camera. The lap tool's path
there (frames 1400-1900, every 2) costs VDP1 93-96% of a frame in its
heaviest frames with no drone close at all: the course 75%, strips 11%, cars
5%. Two things changed.

A drone beside the chase camera: patches/near_clip.s held its vertices
nearer than the near distance out at the screen's edges, as DUSA's attract
close-ups need, so its nearest panels drew stretched off the screen: on the
start straight 7 commands, 5.7% of a frame (81.7% -> 76.0% without them),
the picture beside it the same. Races now drop those polygons as CCE did;
the attract keeps the held vertices (e310bc6).

Turning: tools/turn_choice.py had kept the textures whose quads drew faster
turned summed over a whole lap, so it chose by the light frames, which are
most of them. A probe build (VDP1X_CFLAGS=-DVX_POLYID with VX_MARK_ALL=1:
every textured course polygon goes through the emit entry, which writes its
model record's address / 4 into its commands' gouraud word) tagged every
logged command with its polygon, and each quad was costed again turned. Over
the storm stretch's heaviest tenth (choices made on the lap's frames, judged
on the stretch's):

| quads turned | saves in the heaviest tenth | frames over 92.7% (of 249) |
|---|---|---|
| none more (as built) | 0 | 11 |
| each whichever way is cheaper that frame | 9.1% | 0 |
| fixed per polygon | 6.5% | 0 |
| fixed per texture | 3.8% | 1 |

Fixed per polygon needs a second copy of every texture whose polygons
disagree, 85 KB on Three Seven, where its free VRAM (19 KB) holds the
strips. Per texture costs nothing: the textures turn in place. So
turn_choice.py --heavy makes the choice again from one run of the current
disc, keeping or changing each texture's turn by the time it saves over 85%
of a frame (48, 10, 24, 23 and 19 textures changed). The cut's choices
(tools/vdp1x_choices.json) keep their textures, sizes refreshed for the
seven that turned; choosing them again from laps with the block held off
measured worse (Three Seven's lap 1 -> 9 frames over).

Laps, frame for frame against the disc before (heaviest tenth / frames over
92.7%): Three Seven 90.6% -> 87.9% / 4 -> 1, Seaside 96.4% -> 95.6% / 6 -> 7
(a stretch that runs into the next plot either way), National Park 2 -> 0
over, Dinosaur Canyon and Desert City none over either way; light frames
rise 0-1.8 points. The storm stretch: heaviest tenth 92.9% -> 89.1%, worst
96.3% -> 92.3%, 11 -> 0 over. DUSA's Three Seven attract: 44 -> 16 frames
over; the forest shot where the Saturn loses the camera car's body every
third frame, 22 -> 3. The pictures are the same; texels land a little
differently in the turned quads (single pixels in the road's grain).

## Car effects drawn last (2026-11-09)

The 30-frame hold left the smoke out long after the frame that ran late.
Now, in one-player races, the block links every smoke and spark polygon at
depth 0, whose list VDP1 draws last (after the cars, before the track map's
two markers), and never leaves one out. A frame VDP1 doesn't finish then
loses the nearest smoke, or the markers, where it lost the car's nearest
panels. CCE draws effects for the player's car only: 06040860, from the
player car's draw 06040634 (no other routine calls it). A breakpoint on the
emit entry's effect path over National Park's grass spin and its race start
found nothing else, the effects 0x19F00-0x43000 deep, the car's own
polygons 0x1DC00-0x70A00, so nothing else changes order.

The cost is the smoke lying over the car where it should pass behind: the
lower edge and the bumper in the spin's heavy frames (568-590), the rear
quarter when the car slides sideways (604-636). The user judged it unseen
in play. A replay's trackside cameras face the car, where the rear tires'
smoke belongs behind it, so replays (06054923) keep CCE's order, as do the
attract and two-player races; vx_frame sets the flag each frame (checked in
a race and in a replay forced through 06013360).

The spin (same state and frames, calibrated Mednafen): in depth order the
car loses its body at 568 (both runs, the main disc and the test disc) and
its bumper at 584 (the test disc's); drawn last it stays whole with the
smoke on. The block shrank from 5,312 to 4,828 bytes (the effects'
textures and sums, the hold, its counter and the late flag's read gone).
