# The backup-memory messages

Before the title, CCE's BKUP.BIN checks the console's backup memory and
the cartridge's. If it finds a problem it shows one of 20 messages, some of
them questions with a choice of two. A new console, or one whose battery
has run down, shows the first one. The Japanese release draws them in
Japanese. The US releases have them in English, but in different files and
code. tools/backup_messages.py draws English versions in place of the
Japanese ones.

## How BKUP.BIN shows a message

BKUP.BIN loads at 06028000. The message's number is the byte at 06036F3E
(1-20).
- 0602A636 loads MES_BG.DAT to 00220000, then the message's MESn.DAT to
  00240000. The names come from the table of pointers at 060353D0.
- 0602A820 switches on the number. Each case sets the picture's size from
  constants in the code:
  - the map's address (00240000 + the chars' size + 4);
  - the address of the long holding the chars' size;
  - the width in pixels (r14);
  - the height in pixels (r12).
  Most share the defaults set before the switch: width 576, and heights of
  64, 104 or 144.
- From 0602AA3C the picture is drawn:
  - the box is centred across the 704-wide screen, (704 - width) / 16 cells
    from the left;
  - the chars are copied to VDP2 VRAM 25E20000;
  - the map is drawn 10 cells down.
- For a question, MES_BG.DAT's chars are copied to 25E30000, and 0602A76A
  draws its two choices with 0602C10E. The choices sit at cells (35, 40)
  and (47, 40). The one picked is drawn in colour bank 0x300, yellow.

A MESn.DAT is:
- 8 x 8 chars of 256 colours. The index is the brightness: the messages'
  colours are a grey ramp, and the choice's colour bank is a yellow one.
- a long holding the chars' size in bytes;
- a map of one word a cell (the char number x 2), width by height cells.

Lines of text are 24 pixels tall, one every 40. The box is sized to the
lines: 1 line 3 cells, 2 lines 8, 3 lines 13, 4 lines 18, then 24, 28 and
33 cells.

MES_BG.DAT holds 50 chars, then a map whose first 51 cells are the two
choices: はい (yes), 7 x 3 cells from cell 0, and いいえ (no), 10 x 3 cells
from cell 21. Colour tables follow.

| n | box (cells) | when |
|---|---|---|
| 1 | 74 x 15 | System Memory not formatted: clear it? |
| 2 | 72 x 8 | (No to 1) clear it with the Memory Manager |
| 3 | 54 x 3 | System Memory cleared |
| 4 | 72 x 8 | System Memory could not be cleared |
| 5 | 72 x 18 | Cartridge Memory not formatted: clear it? |
| 6 | 67 x 3 | Cartridge Memory cleared |
| 7 | 72 x 8 | Cartridge Memory could not be cleared |
| 8 | 72 x 8 | System Memory's save unreadable |
| 9 | 72 x 13 | records can't be saved: start anyway? |
| 10 | 72 x 28 | 64 free blocks needed |
| 11 | 72 x 18 | cartridge too full, System Memory used, no ghosts: start? |
| 12 | 72 x 18 | no records or ghosts saved: start? |
| 13 | 72 x 33 | 64 free blocks and 965 on a cartridge needed |
| 14 | 72 x 13 | ghosts can't be saved: start? |
| 15 | 73 x 24 | 965 free cartridge blocks needed for ghosts |
| 16 | 72 x 8 | Cartridge Memory's save unreadable |
| 17 | 72 x 8 | both saves unreadable |
| 18 | 72 x 13 | cartridge save unreadable, System Memory's used |
| 19 | 73 x 13 | this game's files could not be cleared |
| 20 | 72 x 18 | this game's save unreadable: clear it on the cartridge |

## Ours

The English follows the Japanese meaning, in the US Saturn's own terms:
System Memory, Cartridge Memory, the Memory Manager, and blocks. It is set
in Segoe UI at 24 pixels a em, with a quarter-pixel stroke (drawn 4 times
finer, then averaged), for the Japanese lettering's size and weight. The
lines are left-aligned, and the block is centred in the box.

Each picture keeps its Japanese box, and its chars are padded to the
Japanese picture's count. So every file keeps its size and BKUP.BIN's
constants still hold, with no code changed. The English uses about half
the chars the Japanese does. MES_BG.DAT keeps its map and colours: only
the choices' chars are redrawn, as Yes and No in their boxes. The yellow
bank has colours only at the brightnesses the Japanese choices use (0,
15 and 16, 31 and 32, ... 239, 247, 255), so the choices are drawn on
those alone; on the others the picked choice came out speckled.

Mednafen formats a new backup memory itself. To see message 1, zero the
.bkr file in its sav folder before booting: the message follows the
trademark screen. Checked that way (2026-11-06): message 1 with Yes and
No, the pick moving between them, and No leading to message 2. After Yes
the message stays up without its choices, in the Japanese release too
(Mednafen with a zeroed file).
