# ULTIMATE under the main menu's logo

CCE's main menu shows DAYTONA USA with CIRCUIT EDITION under it. Ours
says ULTIMATE there instead (tools/menu_subtitle.py, 2026-11-17). The disc
header names the game DAYTONA USA ULTIMATE too (tools/mkdisc.py, TITLE);
the product number stays GS-9100.

## Where CCE shows the logo

The logo and the grey background behind the menu are one picture, the
menu's NBG0. CCE shows it in two places:
- **The main menu** (SLCT.BIN), from DAYTONA/TITLED.BIN. In normal play this
  is the only place CIRCUIT EDITION is still seen. The attract and the
  press-start page show DUSA's title (docs/attract.md), and Options,
  Records and course select carry only the small DAYTONA logo.
- **The XBAND modem's start**, from DAYTONA/LOGO2.DAT. At its start
  BKUP.BIN reads LOGO2.DAT when the XBAND flag (byte 0601336C) is set and
  LOGO.DAT otherwise (06028050), then goes on to the XBAND course select.
  LOGO2.DAT holds the same picture byte for byte, at 0x11A84. To see it in
  Mednafen, set a poke breakpoint at 0602804E writing 1 to 0601336C.

CCE's own attract title, in DEMOTTL.BIN, has already been replaced by
DUSA's in both attract choices (tools/title_convert.py).

## The picture

| Offset | What |
|---|---|
| 0x00000 | chars, 8 x 8 in 256 colors, 64 bytes each |
| 0x18140 | a long holding the chars' size, 0x18140 |
| 0x18144 | the map: 88 x 56 words, each a char number in 32-byte units |
| 0x1A7C4 | the palette, 256 colors (CRAM palette 1) |

The menu runs at 704 x 448 interlaced. NBG0 is 256 colors with 1-word
pattern names, chars at VRAM 0x20000 (bank A1), and maps at 0x64000 and
0x66000. The map leaves the palette bits clear; the menu adds palette 1.
The picture uses 1540 different cells, and 253 of its 256 colors.

## CCE's lettering

CIRCUIT EDITION is 15 letters with equal gaps of about 29 px between their
fills (45 at the word space). They run from x 23.6 (the C) to 667.3 (the
N), with the TM after them at x 672-691, y 195-205. Each letter has:
- a maroon fill (136, 8, 24), 13.46 lines tall from y 199.3;
- a white keyline (248, 248, 240), 2.4 px wide;
- a soft dark shadow, offset about 0.8 px right and 1 px down;
- a slight blur over everything (sigma about 0.5 px).

Vertical stems are about 6.3 px wide, horizontal bars about 3.4 px, and
the N's diagonal about 5 px measured square to its slope. The E has a
rounded back (radius 6.5), with 1.45 px slits for counters. The U's
bottom corners are rounded (5.4 outside, 3.5 inside).

These numbers were fitted to CCE's own pixels:
- the style on the I;
- the shapes on U, T, E and N.

The tool draws its letters with the same model. The fitted U, T and E match
CCE's to within the dithering CCE's art carries (an RMS error of about 10-22
in 0-255 RGB).

## The new word

- **U, I, T and E:** the fitted shapes.
- **L:** the E's spine and rounded corner, with a bar.
- **M:** two stems, with diagonals of the N's weight that meet at the
  baseline.
- **A:** legs of the N's diagonal weight, a flat top and a bar.

The 8 letters are spread over CIRCUIT EDITION's span with equal gaps
(66.5 px), as CCE spread its own, and the TM is gone.

Each letter is drawn from signed distances to its outline, at 8 x 8 samples
a pixel, over the picture's own colors. Each changed pixel then takes the
nearest of the colors CCE's strip already used, so the palette doesn't
change.

## Taking the old word out

- **The strip:** each maroon pixel and the 5 px around it (rows 197-218),
  plus the TM's box, is filled from its row. Each masked run is bridged
  between the pixels on either side when they're alike; otherwise it takes
  the side nearer the background grey.
- **The O of DAYTONA:** its bottom dips into the strip (x 262-293, rows
  197-199), and the old second I covered part of its keyline. Each masked
  pixel within 3.5 px of the logo's black takes the keyline's color at that
  distance. The colors were measured on the unmasked keyline nearby.

## Cells

The strip touches cell rows 24-27, and those rows are cut again:
- a cell equal to one used anywhere else in the picture is shared;
- a cell equal to one of the old strip's keeps that cell;
- a new cell takes a cell only the old strip used.

The four rows held 235 cells of their own. ULTIMATE needs 148 new ones, and
the 68 left over are cleared. The chars' size, the map's place and the
palette don't change.

## Another word

`--word` takes any word made of the letters in GLYPHS (U I T E N L M A).
Other letters need shapes first, in the same strokes.
