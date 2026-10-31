; The name entry's picture of a car raced on DUSA's body is ours, in the
; livery of the gearbox it raced with (docs/car_select.md, "The name
; entry's pictures"). Assembled into patches/name_pictures.patch by
; tools/mkpatch.py.
;
; The name entry (NAME.BIN) draws the player's car at its state 0
; (06029BE8): a switch on the car (002FC230, from 0) over eleven cases,
; each copying its picture's chars to VRAM 0x40000, then its 32 x 12 map
; (0602D22E), from NAMED.BIN at 0x220000; car 11 and up draws none. The
; switch's load of the car now calls the code in NAMED.BIN's tail
; (tools/name_pictures.py), whose literal was the car byte's only use: it
; draws a car on DUSA's body from that car's picture file and returns 11,
; or returns the car for its own case, as CCE had it.
.target DAYTONA/NAME.BIN 06028000 sh2

.org 06029C04
    jsr    @r0              ; was mov.b @r0,r0
    nop                     ; was mov #11,r1 (the code sets r1 to 11)

.org 06029C30
    .long  0x00278780       ; name_picture, was 002FC230 (the car)
