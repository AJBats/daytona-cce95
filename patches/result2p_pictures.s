; The two-player result's pictures of cars raced on DUSA's body are ours,
; in the livery of the gearbox each raced with (docs/car_select.md, "The
; name entry's pictures"). Assembled into patches/result2p_pictures.patch
; by tools/mkpatch.py.
;
; The result (RESULT2P.BIN, one file at 06028000) sets its screen up in
; one routine: it copies player 1's picture's chars to VRAM 0x4C80 and
; player 2's to 0xB080, then draws both maps on NBG0, each picture found
; in a table at 0608C344 (chars, map, 32 x 12, the chars' size) by the
; player's car (002FC230, 002FC231). Its call to set NBG0's scroll first
; (06029064, to 06029DE4) now calls the code in RESULT2P.BIN's tail
; (tools/name_pictures.py), which reads the picture of each car on DUSA's
; body and gives that player an entry of its own (11 for player 1, 12 for
; player 2) in a copy of the table, after CCE's eleven; the routine reads
; the table and the cars through the copy and through the code's copies
; of the car bytes. Each literal here is its value's only use.
.target DAYTONA/RESULT2P.BIN 06028000 sh2

.org 06029138
    .long  0x0609B000       ; r2p_setup, was 06029DE4 (NBG0's scroll)
.org 06029170
    .long  0x0609B200       ; table, was 0608C344
.org 06029174
    .long  0x0609B2D0       ; cars, was 002FC230 (player 1's car)
.org 060292CC
    .long  0x0609B2D1       ; cars + 1, was 002FC231 (player 2's car)
.org 06029330
    .long  0x0609B2D0       ; cars, was 002FC230 (both cars, for the maps)
