; Car select shows DUSA's car, in the livery of the gearbox under the
; cursor, for the Hornet (car 1) and the secret car 9 (docs/car_select.md).
; Assembled into patches/car_pictures.patch by tools/mkpatch.py.
;
; tools/car_pictures.py puts the picture and its code in the car-select
; screen files (loaded at 0x250000), in the secret car's picture's place;
; the code's entries are 0x2BA5F4 (the picture) and 0x2BA5F8 (gearbox moves).
; The picture routine (0602F83E) switches on the player's car (002FC230 +
; player, from 0) through the table at 0602F900; case 8 (0602FA06) now jumps
; to the code and case 0 shares it. 0602FAE6 draws a player's gearbox
; cursor after every move and when the cursor first shows.

.target DAYTONA/SLCT.BIN 06028000 sh2

.org 0602F900
    .word  0x011E           ; case 0 (the Hornet) as case 8, was 0x006A

.org 0602FA06
    mov.l  picture_at,r0    ; was case 8's draw of Sega's picture
    jmp    @r0
    nop
picture_at:
    .long  0x002BA5F4

.org 0602FAE6
    mov.l  gear_at,r0       ; was its first five steps, done there
    jmp    @r0
    nop
gear_at:
    .long  0x002BA5F8
