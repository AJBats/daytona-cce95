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
