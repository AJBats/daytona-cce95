; Options > Sound's BGM list with DUSA's '95 songs (docs/music.md). Assembled
; into patches/bgm_menu.patch by tools/mkpatch.py.
;
; The page draws a course's BGM choice (rows 12-16) and the BGM test's
; entry (row 17) from its name table (06031E8C, through the literal at
; 06031F98), and the BGM test plays the entry's track from its track table
; (06032E4A, through 06032F34). tools/options_sound.py puts both in OPT.DAT's
; block, which the Options screens have at 0x250000: the 13 choices of
; patches/bgm_tables.s first, then CCE's other 21 entries. Left and right
; wrap a row's value at its maximum (060411FC, rows 10-19, copied to
; 06042562 when the page opens): the course rows take the 13 choices
; (options_sound.py steps them in its own order), the BGM test 34 entries.

.target DAYTONA/SLCT.BIN 06028000 sh2

.org 06031F98
    .long  0x002AD470       ; the name table, was 0603F860
.org 06032F34
    .long  0x002AD5F0       ; the track table, was 0603FCF8
.org 060411FE
    .byte  12, 12, 12, 12, 12, 33   ; rows 12-16, the courses (were 8); row 17, the BGM test (29)
