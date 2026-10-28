; Car select shows DUSA's car, in the livery of the gearbox under the
; cursor, for the Hornet (car 1) and the secret car 9, and left/right on
; the Hornet flips it between DUSA's car and CCE's (docs/car_select.md).
; Assembled into patches/car_pictures.patch by tools/mkpatch.py.
;
; tools/car_pictures.py puts the picture and its code in the car-select
; screen files (loaded at 0x250000), in the secret car's picture's place;
; the code's entries are 0x2BA000 (the picture), 0x2BA004 (gearbox moves),
; 0x2BA008 and 0x2BA00C (players 1 and 2 on the car list).
; The picture routine (0602F83E) switches on the player's car (002FC230 +
; player, from 0) through the table at 0602F900; case 8 (0602FA06) now jumps
; to the code and case 0 shares it (the code goes on to case 0's own body,
; 0602F952, for CCE's Hornet). 0602FAE6 draws a player's gearbox cursor
; after every move and when the cursor first shows. 0602EE2C and 0602F1D2
; are each player's car list input, where it tests up.

.target DAYTONA/SLCT.BIN 06028000 sh2

.org 0602EE2C
    mov.l  input_1p_at,r0   ; was the up test, done there
    jmp    @r0
    nop
    nop
input_1p_at:
    .long  0x002BA008

.org 0602F1D2
    mov.l  input_2p_at,r0   ; was the up test, done there
    jmp    @r0
    nop
input_2p_at:
    .long  0x002BA00C

.org 0602F900
    .word  0x011E           ; case 0 (the Hornet) as case 8, was 0x006A

.org 0602FA06
    mov.l  picture_at,r0    ; was case 8's draw of Sega's picture
    jmp    @r0
    nop
picture_at:
    .long  0x002BA000

.org 0602FAE6
    mov.l  gear_at,r0       ; was its first five steps, done there
    jmp    @r0
    nop
gear_at:
    .long  0x002BA004
