# The save

## The files

The Saturn knows a save only by its file name: 11 characters (A-Z, 0-9,
_), which the Memory Manager lists with a comment of up to 10 and the
date. Nothing in a save says which game wrote it, so a game finds its save
by name alone and reads whatever is there.

CCE writes two files:

| CCE's name | ours (1.0.0-beta.2 and 2.1) | comment | size | where |
|---|---|---|---|---|
| DAYTONA96_0 | DAYULT_B2_0 | RECORDS | 4033 bytes | System Memory or the cartridge |
| DAYTONA96_1 | DAYULT_B2_1 | GHOST | 61713 bytes | the cartridge only |

tools/save_name.py names ours for the release, from the version in
patcher/src-tauri/Cargo.toml: 1.0.0-beta.N is DAYULT_BN_0 and _1, 1.0.0
DAYULT_V1_0 and _1. So no release reads another's save, CCE's or an
earlier beta's (beta 1 still wrote CCE's names), and CCE never reads ours.
Each release starts with an empty save and leaves the others' files where
they are; players clear old ones with the Memory Manager. A beta's fix
release keeps its beta's names (1.0.0-beta.2.1 is DAYULT_B2_*), so it must
keep the layout too: beta 2's save carries over to 2.1.

Three programs read and write the save, and each holds both names (12
bytes each, with the terminating zero): BKUP.BIN (06036808), the backup
check before the title; NAME.BIN (0603BD38), the name entry; SLCT.BIN
(06041880), the menus, which save on leaving Options.

## The records file

4029 bytes, then their sum as a long (each program checks it on reading).
Each program packs and unpacks it through a stream pointer of its own
(BKUP.BIN 06036F50 and 06036F54, NAME.BIN 0603C878 and 0603C87C,
SLCT.BIN 060539CC and 060539D0), with the same routines:

| bytes | from |
|---|---|
| 2400 | records, 002FC3AC-002FD1BB |
| 200 | 002FD1BC-002FD2E7 |
| 320 | 002FD3D8-002FD5B7 |
| 200 | 002FD2E8-002FD3D7 |
| 8 | settings bytes, packed (patches/attract_save_*.s keep ATTRACT in one) |
| 3 | 002FC087-002FC08A, packed |
| 64 | ours (below) |
| 20 | 002FC08C-002FC09F |
| 360 | 002FC0A0-002FC207 |
| 360 | 002FD5C0-002FD727 |

CCE's layout ends at 3871 with zeros to 4029; ours at 3935.

## Ours

patches/save_ext.s: after the three bytes of 002FC087, each program's
helper jumps to the main program, which packs them and then copies 64
bytes from 002FE7C0, byte for byte (and back on reading). That's the end
of the stretch CCE's boot clears (002FC000-002FE7FF), which nothing else
reads or writes (checked through the menus, a save and a race), so without
a save it reads as zeros. Zero is every setting's default.

| byte | setting |
|---|---|
| +0 | STEERING, player 1: 0 AUTO, 1 WHEEL, 2 STICK (patches/steering_choice.s) |
| +1 | STEERING, player 2 |
| +2 to +31 | EDIT layouts (patches/edit_keys.s, tools/options_keys.py): 5 bytes each at +2 + 5 x (3 x player + device), the device as KEY CONFIG counts it (0 pad, 1 Arcade Racer or Mission Stick, 2 3D pad); a job code a button for A, B, C, X, Y, Z, L, R, up, down (the Arcade Racer's paddles), 4 bits, high nibble first, 0 for TYPE E's job |
| +32 to +63 | not used yet |

Settings added later go in the unused bytes, so the layout's length never
changes.
