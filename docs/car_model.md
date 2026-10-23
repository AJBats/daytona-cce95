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
