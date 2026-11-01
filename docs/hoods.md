# The in-car view's hoods

CCE's in-car view shows a picture of the car's hood over the bottom of the
3D view, and with one player the dashboard under it. Each car has its own,
painted in its CCE livery, so a car on DUSA's body showed CCE's paint from
the cockpit: the Hornet on DUSA's body CCE's red Hornet hood, each '95 car
its CCE livery's. Ours show the car as it is outside: DUSA's body in the
car's '95 livery, in the paint of the gearbox it races with.

## CCE's pictures

One file per car and player count, loaded with the race (06028DD6):

| car (from 0) | one player | two players |
|---|---|---|
| 0 Hornet | HORNET.BIN | HORNET2P.BIN |
| 1 Gallop | GALLOP.BIN | GALLOP2P.BIN |
| 2 Max | MAX.BIN | MAX2P.BIN |
| 3 Phoenix | PHENIX.BIN | PHENIX2P.BIN |
| 4 Oriole | ORIOLE.BIN | ORIOLE2P.BIN |
| 5 Magic | MAGIC.BIN | MAGIC2P.BIN |
| 6 Wolf | WOLF.BIN | WOLF2P.BIN |
| 7 Balance | BALANCE.BIN | BALANC2P.BIN |
| 8 secret car | OLD_DAYT.BIN | OLD_DAY2.BIN |

A file is a header (a count, then each part's size and destination), the
chars (8 x 8, 256 colours) for VRAM 0x42000, a map of one-word names (the
char x 2) 44 cells wide for work RAM 0x2F2CC0, and 256 colours for colour
RAM 0x600. The map holds four pictures: the hood whole, then crumpled on
both sides, on the left and on the right. 0602E7EC picks one from the
car's damage bits (+0x128 & 0xC0: 0xC0 both, 0x40 and 0x80 the sides,
swapped on mirrored courses).

- One player (06033B62 by car, 06007D94 loads the file and copies each part
  to its destination): pictures of 14 rows (112 lines), the hood above the
  cowl and the dashboard below it.
- Two players (06033BD6 by player and car, 06033CBE): the same pictures'
  top 7 rows, the hood alone, in at most 127 colours. The load puts each
  player's chars in their own half of VRAM (0xF600 bytes each), adds 128 to
  player 2's pixels, and copies the colours to each player's half of colour
  RAM, with a copy at half brightness.

CCE's pictures are renders of each car's hood. The dashboard is the same
art in all eight; the secret car has a dashboard of its own, more detailed.

The pictures show in view 1 (Y from the default chase view, view 2). With
one player the screen shows the picture's top 72 lines, from screen line
167: the hood and the cowl, the gauges below the screen's edge. With two
players each half shows about the top 20 lines, the nose's edge.

## Ours

tools/hoods.py renders DUSA's body in a car's '95 paint
(tools/liveries.py) with the camera CCE's pictures were drawn with. That
camera was fitted to them with CCE's own model in its own paint, flat
colours, by the hood's outline and its markings (the Hornet's stripe, the
Gallop's horseshoe, the Wolf's lettering): the eye 1.284 above the ground
and 0.318 ahead of the car's middle, 10.5 degrees down, a lens of 233, the
horizon 15 lines above the picture. The light was fitted the same way on
the Gallop, Oriole, Phoenix and Hornet pictures: from the front left and
low, with a highlight and the paint darker at grazing angles.

The body's front seen from above, with its paint on, is a height field;
each line of sight from the eye is followed to where it meets it. The
field is smoothed by 0.04 units, so DUSA's flat panels read curved as
CCE's renders of its rounder model do; more smoothing loses DUSA's shape
(at 0.08 the nose rounds off and its lettering goes). Crumpled hoods add
zigzag folds across the front with a few spikes where they meet, on the
left, the right or both, deepest at the nose (the same folds for every
car).

Above the cowl the picture is ours, below it CCE's dashboard from the
car's own file. The cowl's line is where CCE's eight cars' pictures stop
differing (their hoods) and stay alike (the cowl). The dashboard keeps its
pixels and colours; the hood gets the rest of the 255. Two players' files
take the render's top 56 lines in 127 colours of their own.

patches/hoods.s puts one routine at both of CCE's entries: a car on
DUSA's body with a hood of ours (OURS, a digit a car) loads
HOOD<digit><A|M><1|2>P.BIN by its gearbox and the player count; any other
car loads CCE's file, as before.

The DAYTONA directory had room for two more files, so tools/mkdisc.py now
moves a full directory to the end of the files with a sector more (its
record in the root, its '.' record and the path tables follow it).

## The pilot (2026-11-01)

The Phoenix '95 only (OURS and tools/hoods.py's CARS), both gearboxes.
Checked in Mednafen from a fresh boot: 1P automatic and manual show the
Firebird's and the Ember's hood in view 1; poking the damage bits (car
+0x128 = 0xC0, 0x40, 0x80) shows the three crumpled pictures; the Phoenix
with CCE's car chosen (left in car select) shows CCE's PHENIX.BIN; a 2P
race with player 1 automatic and player 2 manual shows each player's hood
in its own colours. The disc's every file record lies inside the data
track and holds the built file's bytes.
