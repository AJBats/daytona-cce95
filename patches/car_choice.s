; The Hornet races DUSA's car or CCE's own, as chosen with left/right in car
; select (docs/car_select.md). Assembled into patches/car_choice.patch by
; tools/mkpatch.py.
;
; tools/car_convert.py builds DUSA's car as the secret car 9's files
; (PLCAR09, PLCAR29 in two-player) and leaves the Hornet's PLCAR01/PLCAR21
; as CCE shipped them. The car load (06040280, r12 = player, r11 = player x
; 6) names the file by car number from 1 (060402AC: the config byte 060540B6
; + 6 x player, plus 1; 0604028C adds 20 in two-player); its literal for
; 060540B6 now points at car_number, which the load calls in the config
; byte's read's place and which gives 9 for the Hornet when DUSA's car is
; chosen. So the load, and patches/livery.s after it, see car 9.
;
; The choice is 002FC3A9 + player (0 DUSA's car, 1 CCE's), bytes the boot
; clears and nothing else uses; car select's code (tools/car_pictures.py)
; flips it. The attract always has DUSA's car. is_dusa is also called by
; patches/reflection.s (DUSA's window) at its address, 060334FC.
;
; Caves: 060334FC-0603353B, the end of the dead function after
; patches/near_clip.s, and 0603CC34-0603CC63, the end of the unreferenced
; function after patches/reflection.s; nothing reads either.

.org 0604037C
    .long  car_number       ; was 060540B6, the config's car bytes

.org 060402AC
    jsr    @r0              ; was mov.b @(r0,r11),r11
    nop                     ; was add #1,r11

.org 060334FC
; T = player r1's car is DUSA's: car 8 (the secret car), or car 0 (the
; Hornet) in the attract or with DUSA's car chosen. Uses r0-r2.
is_dusa:
    mov    r1,r0
    shll   r0
    add    r1,r0
    shll   r0               ; player x 6
    mov.l  cars_at,r2
    mov.b  @(r0,r2),r0
    cmp/eq #8,r0
    bt     is_done
    tst    r0,r0
    bf     is_done
    mov.l  demo_at,r2
    mov.b  @r2,r0
    tst    r0,r0
    bf     is_attract
    mov.l  choice_at,r2
    add    r1,r2
    mov.b  @r2,r0
    rts
    tst    r0,r0            ; DUSA's car chosen
is_attract:
    sett
is_done:
    rts
    nop

.align 4
cars_at:
    .long  0x060540B6       ; each player's car, from 0, 6 bytes apart
demo_at:
    .long  0x0601335C       ; the attract's demo, 0 outside it
choice_at:
    .long  0x002FC3A9

.org 0603CC34
; The car load's car number: the config's car from 1, 9 for DUSA's car.
car_number:
    sts.l  pr,@-r15
    mov.l  number_cars,r0
    mov.b  @(r0,r11),r11
    add    #1,r11
    mov.l  is_dusa_at,r0
    jsr    @r0
    mov    r12,r1
    bf     number_done
    mov    #9,r11
number_done:
    lds.l  @r15+,pr
    rts
    nop
.align 4
number_cars:
    .long  0x060540B6
is_dusa_at:
    .long  is_dusa
