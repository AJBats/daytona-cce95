# Player car model: DUSA vs CCE

Goal: DUSA's Gallop (automatic livery, red/blue) replaces CCE's Hornet
(PLCAR01) in races, with DUSA's rear-window reflection.

## Drawing (VDP1 command lists, tools/vdp1list.py on VDP1 VRAM dumps)

Both games draw the car the same way: distorted sprites in 4bpp
colour-lookup-table mode (CMDPMOD 0x14C8; 0x1488 where colour 0 is
transparent), 16 colours per texture, the lookup tables in VDP1 VRAM. A few
flat polygons (CCE 0x04C0/0x05C0) for the shadow and underside. So textures
and their 16-colour tables carry over as they are; only geometry and the
model layout need converting:

- DUSA model (POLYGON.BIN, player car at RAM 060F9E24): 143 vertices,
  16.16 world units; faces 24 bytes (attribute, texture, 4 vertex indices,
  normal).
- CCE model (PLCAR01.MDL): starts with a 65-entry texture table (8 bytes:
  CMDPMOD 0x14C8, lookup-table offset, CMDSRCA offset, CMDSIZE); 138
  vertices at +0x2444 as 16-bit values in 1/1024 world units.
  PLCAR01.TEX starts with the 16-colour tables (RGB555).

## Rear window

DUSA (state build/states/dusa_ta_speed.mcs, automatic Gallop): the rear
and side windows are drawn with one 80x40 texture (VDP1 0x13E98, lookup
table 0x193C), re-uploaded every car tick (3 frames) by DMA from a RAM
strip at 0606B178..: a 40-row sky image stored twice so a 40-row window
can start on any row. The DMA source advances 2-4 rows per tick and wraps
(0606B178..0606B768), so the reflection scrolls past continuously. The
manual car adds a second layer on top (0x1488, transparent pixels: the
window struts).

CCE: three rear-window quads with a shared 32x32 glass texture (VDP1
0x4F100, mode 0x1488) plus a 16x16 overlay (0x58FE0); no texture upload
between frames (VRAM unchanged over 10 frames). Its subtle animation comes
from elsewhere (not yet found).

## DUSA car, from the disc

- Model table (RAM 0606212C vertices, 060620D8 faces, 060621D8 vertex
  counts, 06062180 face counts; 20 models). Model 0 is the player body:
  142 vertices at POLYGON.BIN +0x1E24 (16.16 x, y, z; y up, nose at -z),
  132 faces at +0x24CC. POLYGON.BIN is loaded at 060F8000.
- Face, 24 bytes: normal (3 x 16.16), attribute word, texture word, four
  vertex indices (quads; triangles repeat a vertex).
  Attribute: bits 0-2 depth-sort mode (06031D78: average, min, max, max +
  0x20/0x40 bias ...); bit 3 skips the normal (backface) test; bit 4
  transparent (CMDPMOD 0x1488 instead of 0x14C8); bits 6-7 flip (CMDCTRL
  0x02/0x22/0x12/0x32 for 0, 0x40, 0x80, 0xC0).
- Texture word -> slot via 060684EC[bank * 64 + tex] (bank 0 for the body),
  slot -> 06063F64 + 8 x slot: VRAM address / 8, CMDSIZE, lookup-table
  offset (+0x1900 base). The two Gallop liveries use the same pixels and
  different 16-colour tables.
- TEX_PL.BIN (loaded at 002A0000): 16-colour tables first (0x000-0x0E0 the
  automatic livery's tables 0-7, 0x100-0x1A0 the manual livery's tables
  2-7, 0x1C0/0x1E0 shared), then LZSS-compressed textures
  (tools/dusa_lzss.py, DUSA 06028654). Texture -> TEX_PL offset for every
  body texture is in the converter. The window reflection strip (80 x 80,
  4bpp) is at TEX_PL +0x3457.

## CCE car file PLCAR01.MDL

- +0: texture table, word count (0x41) then 8-byte entries: CMDPMOD,
  lookup-table offset, CMDSRCA offset, CMDSIZE. On load the offsets become
  absolute (lookup tables from the TEX base, pixels from TEX base + 0x800),
  and entry 9 is replaced by the shared 32x32 glass texture (mode 0x1488).
- Model blocks: header (count of vertices, count of polygons, offset to
  vertices, offset to polygons = 0x14, offset to the texture table), all
  offsets from the header. Four 138-vertex blocks (damage states; the race
  uses 0x1320, vertices at +0x2444) and two 23-vertex low-detail blocks.
  A 9-entry table follows at +0x280A (not decoded).
- Polygon: attribute, texture (byte offset into the table), 3 or 4 vertex
  offsets (vertex index x 16). Attribute (CCE 060457B8, 06045E44): bit 0
  triangle; bits 1-3 depth sort (06045D04: average, min, max, max + bias);
  bit 4 backface test (screen winding); bits 5-8 draw mode (2 = textured
  distorted sprite, 0 = flat polygon with the texture word as colour);
  bits 9-11 triangle vertex layout; bits 12-13 flip.
- Vertices: 16-bit x, y, z in 1/1024 world units, same axes as DUSA.
- PLCAR01.TEX: 64 lookup tables (0x800 bytes), then 4bpp pixels.

## Converter (tools/car_convert.py, run by make disc)

Builds PLCAR01.MDL/.TEX from DUSA's POLYGON.BIN and TEX_PL.BIN. Findings
from getting it to load:

- Both CCE files end in a symbol trailer the loader reads from the end of
  the file: (id, offset from the trailer start) pairs, then their count.
  MDL ids 0x27 texture table, 0x28 the entry the loader replaces with
  glass, 0x29-0x2C the damage-state headers (states 0-3 = 0x2C, 0x2A,
  0x2B, 0x29), 0x2D/0x2E low detail. TEX ids 0xB9 tables, 0xBA pixels.
  The disc keeps the original directory entries, so both files are
  padded to the original sizes with the trailer at the end.
- CCE's polygon order is DUSA's face order unchanged: same corner order,
  same flips (DUSA CMDCTRL direction bits = CCE attribute bits 12-13).
- DUSA damage: on big crashes DUSA draws model 13 (136 vertices, 132
  faces, POLYGON.BIN +0x4470/+0x4AD0) instead of model 0; it uses the same
  textures plus id 53. CCE damage states 1-3 get model 13.

First result: the Gallop draws correctly in the chase view and the
rolling-start close-up (build/states/cce_gallop_start.mcs). The rear
window shows the first 40 rows of the reflection strip, not yet scrolling.

Window reflection (patches/reflection.s): DUSA's per-tick scroll state
(0601BDEC: V += km/h / 32 + 1 wrapping past 80, H +-2 against the heading
change, reset past 0xA0) kept x3 for 30 Hz, and the 1600-byte window
texture copied from the strip in PLCAR01.MDL to VRAM (entry 48's address)
at the end of the chase camera routine, player 1 only. Checked on the
fresh disc: the state advances once per 2 frames (km/h 170: V3 +12), and
VRAM matches the strip at the computed row.

Fix (2026-10-24, the user saw the reflection scroll, then jump): DUSA's
start byte is (V/4) x 80 + H/2 (0600705E), two strip rows per V/4 step;
the first version used one row (x 40), so it scrolled at half speed and
wrapped half-way through the 40-row image, a 20-row jump. Now x 80, and
the offset drops by 1600 once it reaches the second copy of the image, so
the copy stays inside the strip. Over 10 s of driving (state
build/states/cce95_refl_5000.mcs, VRAM 25C53700 sampled every frame) the
window advances 2-4 rows per tick, as DUSA's does, and wraps without a
jump. The faint horizontal cut the user also saw across the window went
with it: the old wrap kept the sky image's own top/bottom seam in the
lower middle of the window.

Livery by transmission (patches/livery.s): DUSA's manual car has VRAM
tables 2-7 = TEX_PL +0x100-0x1A0 (checked in dusa_stopped_manual.mcs);
the automatic car TEX_PL +0x40-0xE0. The converter stores both sets in
PLCAR01.TEX (manual 8-13, automatic 16-21) and the patch copies player
1's set over tables 2-7 right after the car's load relocation (0604030E),
so the rolling start already shows it. Checked from boot: red/blue with
build/cce_start_auto_script.txt, yellow/red with cce_start_script.txt.

The copy ran for whatever car was loaded, and every other CCE car uses its
tables 8-21 for its own textures (each texture entry has its own table),
so in 1P their tables 2-7 took colours from elsewhere in the car: car 2's
left-side decals lost their red lettering. The patch now copies only when
the loaded car is car 1 (r11 at the call), and reads the transmission of
the player being loaded (060540B8 + 6 x player, r12). Checked by forcing
the car and transmission at the loader (06040280) from boot: cars 2 and 5
keep their own tables 2-7, the Gallop gets 16-21 automatic and 8-13 manual.

Brake lights: neither game has them on the player car. Braking in DUSA
(dusa_ta_racing.mcs, pad B) and in CCE95 changes no texture, lookup table
or car texture table entry, only which polygons are visible.
