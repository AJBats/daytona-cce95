# Car select

## Pictures (SLCT.BIN, base 06028000)

The car under the cursor is drawn on VDP2 NBG3 by 0602F83E (player, map
column, row): 43/73 for players 1/2 in 2P modes (06042369 = 12 or 13), 46
in 1P; row 27. Player 1's chars go to VRAM 0x10000, player 2's to 0x18000;
the map is 13 x 27 cells.

It switches on the player's car (002FC230 + player, from 0) through the
word table at 0602F900 (braf base 0602F8E8), 11 cases: 0 Hornet, 1 Gallop,
2 Max, 3 Phoenix, 4 Oriole, 5 Magic, 6 Wolf, 7 Balance, 8 Daytona (the
secret car), 9 and 10 the horses. Each case copies the picture's chars to
VRAM (06028D46: chars, VRAM, size) and draws its map (060291B6, from
0602FACA on). Each picture's data is in the car-select screen file,
loaded at 0x250000 and laid out the same in ARC, TA, TWO_P, LINK and
XBANDISE.DAT: chars (256 colours, 64 bytes each, char 0 blank), then a
header (the chars' size, 4 bytes), then the map (char number x 2).

| Car | chars | header |
|---|---|---|
| Balance | 28CF40 | 291D80 |
| Gallop | 292042 | 296E44 |
| Hornet | 297106 | 29C088 |
| Wolf | 29C34A | 2A12CC |
| Max | 2A158E | 2A63D0 |
| Magic | 2A6692 | 2AB414 |
| Oriole | 2AB6D6 | 2B05D8 |
| Phoenix | 2B089A | 2B4F5C |
| Daytona | 2B521E | 2BA7A0 |
| horse 1 | 2BAA62 | 2BE0A4 |
| horse 2 | 2BE366 | 2C1928 |

All eleven pictures share one 256-colour palette (screen file +0x71BEA,
CRAM 0x600). Its entries 2-13 are a ramp from the screen's background to
black that every picture's halo is drawn in, and each screen sets them to
its own background (ARC red, TWO_P blue, TA yellow); 14 is black on all.

The gearbox cursor is 002FC3A7 + player (0 automatic, 1 manual). After
every move, and when it first shows, car select draws it with 0602FAE6
(player).

## DUSA's car (2026-10-27)

tools/car_pictures.py renders DUSA's car from its in-game model and
textures, top-down and nose up as CCE's pictures are, in the automatic
and the manual livery. CCE's cars span rows 15-203 of the 216 with the
halo offset 2 pixels down and right, so it fades out inside the picture;
DUSA's car is drawn the same length and in the same place, keeping its
own proportions (narrower than CCE's drawings). Both are quantized to
the shared palette as one index picture plus a 256-byte remap (automatic
index -> manual index).
The car never uses entries 2-13, so it looks the same on every screen,
while its halo uses the ramp and takes each screen's background. The
chars, the code and the remap, and the map replace the secret car's
picture (Sega's drawing of DUSA's #41) in every car-select screen file:
chars from 2B521E (293, room for 311), code and remap from 2BA000, map
at 2BA7A4, where its map was. CCE's own Hornet picture is left in place.

Shading (2026-10-30): CCE's pictures are smooth renders, its own cars'
from a finer model; Sega's drawing of DUSA's #41 (the secret car's) is the
nearest to ours, DUSA's low-poly body with its textures. Like it, ours are
lit from the picture's top left (the car's front left) and above, with a
highlight: each face's normal is interpolated across it from its corners,
which share the normals of the faces meeting there within 65 degrees, so
the low-poly body shades as if curved; surfaces seen edge-on darken a
little. The windscreen is light grey at its front edge, dark at the roof,
the back and side windows dark, as on Sega's and CCE's pictures, in place
of the in-game reflection texture.

patches/car_pictures.s sends case 0 to case 8 and case 8 to the code
(2BA000), which copies the chars to the player's VRAM, through the remap
while the player's gearbox cursor is on manual, then draws the map as
the cases do. 0602FAE6 jumps to the code's second entry (2BA004), which
copies the chars again when the player's car is DUSA's and goes on with
the cursor's draw. Checked from a fresh boot: Arcade with the Hornet and the secret car
switching between automatic and manual as the cursor moves and keeping the
choice when going back to the car list, the Gallop's own picture, 2P (each
player's picture on its side, the halos blue), Time Attack (halo yellow)
and the race after it in the manual livery. Player 2's gearbox moves were
checked by the user on the keyboard pad (2026-10-28).

## DUSA's car or CCE's on the Hornet (2026-10-27)

Left or right on the Hornet flips that player's choice, 002FC3A9 +
player (0 DUSA's car, the default; 1 CCE's own). The boot clears both
bytes (0 at the main menu) and no code refers to them. The choice isn't saved in
the backup.

- **Disc:** tools/car_convert.py builds DUSA's car as the secret car's
  files only (PLCAR09, PLCAR29); the Hornet's PLCAR01/PLCAR21 are CCE's
  again.
- **Race:** patches/car_choice.s has the car load (06040280) name the file
  from car 9 for the Hornet when DUSA's car is chosen, so the load and
  patches/livery.s (now car 9 only) see car 9. Its is_dusa (060334FC: car
  8, or car 0 in the attract or with DUSA's chosen) also gates
  patches/reflection.s. The attract always has DUSA's car. The Hornet's
  handling is the same either way: only the model and its paint change.
- **Car select:** each player's car list input (0602EE2C, 0602F1D2,
  where it tests up) jumps to the code (2BA008, 2BA00C): left or right on
  the Hornet flips the choice, plays the cursor's sound and draws the
  picture again; anything else goes on to the up test. The picture code
  goes to case 0's own body (0602F952) for CCE's Hornet, and the gearbox
  hook leaves its chars alone.

Checked from a fresh boot: Arcade, left on the Hornet shows CCE's
picture, the gearbox cursor leaves it, and the race has CCE's red #19
Hornet; right again shows DUSA's and the race has DUSA's car in red/blue;
left/right on the secret car does nothing. The attract, with the choice
forced to CCE's, still loads DUSA's car. 2P car select: player 1 flips
to CCE's Hornet while player 2's picture stays DUSA's. The first 2P
build sent player 2 into the gearbox by itself: the hook had overwritten
r4, the handler's pointer to player 2's pad, which it reads for A
further on; the code now restores it. The user checked player 2's own
left/right and gearbox and a 2P race with one player in each model on
the keyboard pad (2026-10-28).

The picker isn't shown anywhere on the screen; how to hint at it is open.

Since 2026-10-28 left and right also flip the choice on a car with a '95
livery (all seven of CCE's cars; docs/liveries.md). The choice is one byte a
player, so it carries from car to car. A '95 car's picture comes from
PICS95.BIN, loaded with the screen into work RAM high (docs/liveries.md,
"Car-select pictures"); every car's picture case now goes through the
code, which sends a car not on DUSA's body to its own case.

## Colours of their own (2026-10-30)

CCE's pictures and ours are the same format: 256-colour chars over one
shared palette of 15-bit colours (CRAM 0x600, bank 3). CCE's eight
pictures use 255 of its 256 colours between them, and the palette was
made for them: ours, put in the nearest of its colours, came out dithered
(the Phoenix's fireball, a checkerboard of CCE's oranges).

So each of our pictures (the Gallop's and the '95 cars', in PICS95.BIN)
has colours of its own: entries 15-255 of the palette, an automatic and a
manual colour for each, k-means over the pairs of colours of the car's
pixels, so one index picture serves both gearboxes. With one player the
picture code writes the picture's colours into CRAM with its chars (the
gearbox's), and CCE's back (from the screen file, still loaded at
0x250000) before CCE's own picture; entries 0-14 (the halo's ramp, black)
are never touched. With two players both pictures show at once over the
one palette, so ours keep CCE's colours: the chars go through a remap to
the nearest of them. The Gallop's picture in the screen file stays in
CCE's colours, for when PICS95.BIN isn't loaded.

The palette can't simply grow. Car select fills all 1024 colours of colour
RAM mode 0 (banks 0-3, the backgrounds' and the pictures'). Mode 1 holds
2048, but car select runs in high resolution (TVMD 0x80C3) with colour
calculation on its scroll screens (CCCTL 0x000F), and in high resolution
mode 1 can't blend palette-format screens (ST-058 table 12.1), which is
likely why Sega kept mode 0.

Checked from a fresh boot: Arcade car select with the Magic '95 in
automatic and manual, left to CCE's Magic (its picture exactly as before),
the Hornet on DUSA's body, back to course select (its colours as before);
2P car select with player 1's Magic '95 and player 2's Hornet.
