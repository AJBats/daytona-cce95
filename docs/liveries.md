# '95 liveries on DUSA's body

Every CCE car gets a new livery in the style of DUSA's 1994 cars, gently
inspired by its CCE paint, on DUSA's body (the Hornet's proportions). Each
has an automatic and a manual version, as DUSA's Gallop does, and left or
right in car select switches to CCE's own car. The style reference is
DUSA's 39 rival liveries (tools/drone_sheet.py, build/cars/drones.png;
docs/car_model.md, "DUSA's drones").

All seven are done, in borrowed art (below), each the user's pick of
three colourings (2026-10-29; `PICKS`):

| car | automatic | manual |
|---|---|---|
| Gallop #27 | Derby: navy sides, white top, CCE's horseshoe in black with its red bars, white 27 | Rosette: red sides, white top, the horseshoe and lettering in navy |
| Max #2 | Spearmint: teal, white top, red MAX | Citrus: yellow, teal top |
| Phoenix #8 | Firebird: black, the fireball, red PHOENIX, yellow 8, red lower body | Ember: red sides, black top, a gold fireball and 8 |
| Oriole #16 | Nightjar: black, yellow top, red 16 | Robin: orange, yellow top, black 16 |
| Magic #33 | Emerald: green, white top, CCE's star, red 33 | Conjurer: black, green top, white 33 |
| Wolf #41 | Timber: red, white top, white 41 | Midnight: black, red top |
| Balance #99 | Scales: white, orange lower body, red 99 | Inkwell: black, white top, orange 99 |

The Wolf keeps CCE's 41, the number DUSA's Hornet carries: changing it
would mean changing CCE's own car too, which is kept as CCE shipped it.

## Paint (tools/liveries.py)

A paint is the DUSA body's textures as 4bpp pixels plus 29 16-colour
tables, the same layout for every car on DUSA's body, so they all share
car 9's MDL:

| tables | |
|---|---|
| 0, 1, 15 | DUSA's (under-body details, the window strip) |
| 2-7 | DUSA's tables 2-7, at their own numbers: panels, pillars, lights, decals |
| 8 | hood (textures 25, 26, 27, side by side: 72 x 72) |
| 9 | roof number (28, 48 x 48) |
| 10 | trunk (29, 80 x 40) |
| 11, 12 | door number, top (37, 38) and bottom (39) rows: 48 x 40 |
| 13 | rear-quarter lettering (46, 47, 48 left, 42, 41, 40 right, 43, 49 below) |
| 14 | tail (30 spoiler face, 31 plate) |
| 16-28 | the manual livery's 2-14 |

Tables 2-14 hold the automatic livery; patches/livery.s copies 16-28 over
them for a manual car. The two liveries share their pixels: each art
group's pixels are numbered by the pairs of colours they have in the two
liveries, at most 16 pairs a table, so both versions of a car draw the
same shapes in different colours. The door is two groups because DUSA's
own door (three textures on three tables) has 18 colour pairs.

The Gallop's paint is DUSA's own. A '95 paint recolours DUSA's manual
tables 2-7 by role (reds to the body colour, yellows to the panel colour,
table 3's greys to the lower body's, each keeping its brightness step; the
tail lights keep theirs and the side window's net takes the scheme's) and
draws the art textures afresh from the car's CCE paint (below).

Texture orientation on DUSA's body: the hood reads from in front of the
car (canvas top at the windshield), the roof number from the car's left
side, the door number upright on both sides, the rear-quarter lettering
front to back on each side.

`liveries.py <dusa dir> <cce dir> <png>` renders every paint in both
versions.

### Borrowed art (2026-10-28)

The first liveries were drawn in code (polygon emblems, numbers built
from rectangles after DUSA's 41, Windows fonts without smoothing), and
together looked like a set made by one program. The user asked for a middle ground between CCE's own art
and DUSA's 1994 style, so a car's art is now borrowed (`Borrowed`,
`borrowed_art`):

- **Logo:** CCE's own, from its car drawn from above in its textures'
  colours (`cce_logo`, a rectangle in world units), as each pixel's share
  of dark and of red (`soft_inks`). It is traced to outlines smoothed along
  their length, its small holes (the horseshoe's nails) made ellipses, and
  made symmetric about its own middle (CCE's Gallop logo is 0.04 units off
  the car's), then laid onto DUSA's hood through the hood's faces
  (`texel_world`, `world_cover`), so it keeps its shape across the three
  strips, which cover the hood at different widths.
  Kinds (`logo_kind`): the Gallop's dark and red inks; the Phoenix's
  fireball as one shape (all it draws lit on the black hood), filled with
  our own glow in steps from its bright core; Balance's triangle by nearest
  colour (`logo_inks` against `logo_ground`). Magic's three stars are
  regular five-pointed stars drawn whole (`MAGIC_STARS`, `logo_kind=
  'vector'`), each fitted to the part of it CCE's hood shows: CCE's
  wordmark covers their tops, so a trace cut them off (2026-10-30).
  Max, Oriole and Wolf have no hood logo.
- **Wordmark:** CCE's, drawn up smooth (`drawn_up`) across DUSA's hood and
  to the trunk, the rear quarters and the tail plate: from the textures
  that spell it (the Gallop's trunk; the Phoenix's two rows of them), or
  cut from CCE's hood seen from above, where it is biggest (Max, Oriole,
  Wolf, Balance), by its red, colour, dark or light. Magic's is broken in
  every CCE texture, so it is set in Bookman Old Style Bold; the Phoenix's
  and Wolf's rear-quarter lettering is set in Impact and Arial Black, the
  wordmarks being too tall to read 8 pixels high.
- **Number:** Franklin Gothic Heavy Italic (`NUMBER_FONT`), the nearest of
  32 fonts tried to CCE's own heavy italic numbers; on the roof on a glow as
  DUSA's rivals have theirs, and on the doors.

All of it is drawn on a grid 8 times finer than the texture (`FINE`) and
each texel takes the share its area covers, blended into the colours under
it. A group with more than 16 colour pairs then comes back to 16
(`fit_colours`): the pairs covering 1% of its pixels or more stay as they
are and the rest of the table is the k-means of the edge colours.

Copying CCE's pixels as hard masks had made the logo and the numbers
chunky: DUSA's hood has about half the texels across that CCE's has (41 a
unit in the middle strip against 83). Bigger art textures would fit in the
car file (19 KB free) but were turned down: on the Saturn these textures
are small on screen, and smoothing at DUSA's own sizes is enough.

Candidates: three colourings a car (`BORROWED_CANDIDATES`; sheets by
tools/livery_candidates.py), from which the user picked an automatic and
a manual (`PICKS`).

## Files (tools/car_convert.py)

| file | |
|---|---|
| PLCAR09.MDL / .TEX | DUSA's body, the Gallop's paint (1P) |
| PLCAR29.MDL / .TEX | the same, low detail (2P); floor panel at 1/4, grille at 1/2 |
| PLCAR3n.TEX | car n's '95 paint (1P), n from 1: Gallop PLCAR32 to Balance PLCAR38 |
| PLCAR5n.TEX | car n's '95 paint (2P): PLCAR52 to PLCAR58 |

Every paint gives the same MDL (the converter checks), so a '95 car has
only a TEX of its own, padded to the size of the Gallop's. The '95 files
are new on the disc: tools/mkdisc.py adds a file not on the disc at the
end of the data, with a record after the last one in its directory's last
sector (DAYTONA's had room for about 18). Records keep their order, so
the GFS file numbers of the files already there don't change. CCE's GFS
directory table (work + 0x98: type 1 = names, 256 entries at 002FE800)
holds 256; DAYTONA has 205 now.

## Racing one (patches/car_choice.s, patches/livery.s)

- **is_dusa** (060334FC) reads a byte a car (`bodies`, in car_choice.s's
  cave at 0603CC54): 0 CCE's car only, 1 DUSA's body or CCE's as chosen
  (the Hornet and the '95 cars), 3 DUSA's body always (the secret car).
  car_convert.py checks the table against liveries.NINETY_FIVE.
- **car_number** gives 9 for a car on DUSA's body, so the load takes
  PLCAR09.MDL (29 in 2P) and patches/livery.s copies the manual tables.
- **tex_load** (0602C9C0) runs in the TEX load's place (literal at
  0604039C, was 0604828C): for a car on DUSA's body other than the Hornet
  and the secret car, it writes the car's digits over the TEX name
  ("PLCAR3n", "PLCAR5n" in two-player), then loads.
- **The choice** is one byte a player (002FC3A9 + player), flipped by left
  or right on any car with a choice (tools/car_pictures.py's car-select
  code), so it carries from car to car.

Checked in the debugger from a fresh boot (2026-10-28): Arcade on Three
Seven with the Phoenix in automatic (Firebird) and manual (Ember), left on
the Phoenix then automatic (CCE's black Phoenix), the Hornet in manual
(the Gallop's yellow and red); 2P with player 1's Phoenix in manual and
player 2's in automatic. The Gallop's 1P files render pixel for pixel as
before; in 2P only the halved grille differs.

The '95 Gallop, from a fresh boot (2026-10-29): Arcade on Three Seven, its
picture in Derby and, on MT, Rosette; the race in automatic (Derby) and
manual (Rosette); left on it gives CCE's picture and races CCE's Gallop.

All seven, from a fresh boot (2026-10-29): Arcade on Three Seven, each of
the other six's pictures in automatic and in manual, and each raced in
manual; the Oriole raced in automatic (Nightjar); left on the Wolf gives
CCE's picture and races CCE's Wolf; up from the Hornet wraps to the
Balance as before. PICS95.BIN is 134,696 bytes for the seven.

## Car-select pictures (tools/car_pictures.py, patches/car_pictures.s)

Each '95 car has a picture rendered as the Gallop's is (both liveries,
one set of chars plus a manual remap). They don't fit in the car-select
screen files (the secret car's slot holds the Gallop's, and the files
already reach work RAM low 0x2D9730-0x2F40AC), so they go in a file of
their own, PICS95.BIN, loaded with the screen into work RAM high
060B0000-060ECFFF, which is zero and unused in the menus (the race uses
it). About 19.4 KB a car.

- **Load:** the menu starts the screen file's load through the kernel's
  queued loader (06005C10, SLCT 0602A42A) while course select shows; the
  rewritten dispatch queues PICS95.BIN after ARC, TA, TWO_P and LINK
  (not REC or OPT). Car select's program start, when it comes back from a
  race (Exit in 2P), loads its screen with the loader that waits
  (060058B4, 06028200); the rewritten dispatch loads PICS95.BIN after it,
  for all five screens. Both dispatches were made shorter to make room;
  the file name is in old case 8's dead literals (0602FA84).
- **File:** a tag ('PICS'), a record address for each car from 0 (0 for
  none), the end tag's address, the records, the end tag. A record is the
  chars' size in words and the addresses of its map, remap and chars.
- **Draw:** every car's picture case (0-8) goes to the code; it finds the
  car's record (the Gallop's for the Hornet and the secret car, the
  file's for a '95 car while both tags are there) or goes on to the car's
  own case, as CCE had it, for CCE's picture.

Checked from a fresh boot (2026-10-28): Arcade, the Phoenix's picture in
Firebird and, with the gearbox cursor on MT, Ember; left on the Phoenix
gives CCE's picture and then CCE's Hornet too; every other car's own
picture (Gallop, Max, Oriole, Magic, Wolf, Balance); 2P car select with
player 1's Phoenix and player 2's Gallop; Exit from a 2P race back to
course select, through the waiting load, and the Phoenix's picture
again. Course select takes a moment longer to answer while the file
loads behind it.

## Open

- Two-player with the new cars is untested beyond the Phoenix's (the 2P
  files build the same way).
