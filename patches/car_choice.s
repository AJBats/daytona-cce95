; The Hornet races DUSA's car or CCE's own, and a car with a '95 livery
; races it on DUSA's body or CCE's own car, as chosen with left/right in
; car select (docs/car_select.md, docs/liveries.md). Assembled into
; patches/car_choice.patch by tools/mkpatch.py.
;
; tools/car_convert.py builds DUSA's body as the secret car 9's files
; (PLCAR09, PLCAR29 in two-player) with the Gallop's paint, and a '95
; car's paint as a TEX of its own, PLCAR3n (PLCAR5n in two-player) for car
; n from 1; every car's own PLCARn stays as CCE shipped it. The car load
; (06040280, r12 = player, r11 = player x 6) names the files by car number
; from 1 (060402AC: the config byte 060540B6 + 6 x player, plus 1;
; 0604028C adds 20 in two-player); its literal for 060540B6 now points at
; car_number, which the load calls in the config byte's read's place and
; which gives 9 for a car on DUSA's body. So the load, and
; patches/livery.s after it, see car 9 and load PLCAR09.MDL; the TEX load
; (0604828C) goes through tex_load, which names a '95 car's own TEX.
;
; The choice is 002FC3A9 + player (0 DUSA's body, the default; 1 CCE's
; car), bytes the boot clears and nothing else uses; car select's code
; (tools/car_pictures.py) flips it on the cars that have a choice. The
; attract always has DUSA's car. is_dusa is also called by
; patches/reflection.s (DUSA's window) at its address, 060334FC.
;
; Caves: 060334FC-0603353B, the end of the dead function after
; patches/near_clip.s, and 0603CC34-0603CC63, the end of the unreferenced
; function after patches/reflection.s, nothing reads either; 0602C9C0-
; 0602CA13, after patches/sector_fallback.s in its dead function.

.org 0604037C
    .long  car_number       ; was 060540B6, the config's car bytes

.org 060402AC
    jsr    @r0              ; was mov.b @(r0,r11),r11
    nop                     ; was add #1,r11

.org 0604039C
    .long  tex_load         ; was 0604828C, the TEX load

.org 060334FC
; T = player r1's car is on DUSA's body: the secret car always, a car with
; a choice (the Hornet, the '95 liveries) in the attract or with DUSA's
; body chosen. Uses r0-r2.
is_dusa:
    mov    r1,r0
    shll   r0
    add    r1,r0
    shll   r0               ; player x 6
    mov.l  cars_at,r2
    mov.b  @(r0,r2),r0
    mov.l  bodies_at,r2
    mov.b  @(r0,r2),r0
    cmp/eq #1,r0
    bf/s   is_done
    shlr   r0               ; no choice: T = DUSA's body always (3) or never (0)
    mov.l  demo_at,r2
    mov.b  @r2,r0
    tst    r0,r0
    bf     is_attract
    mov.l  choice_at,r2
    add    r1,r2
    mov.b  @r2,r0
    rts
    tst    r0,r0            ; DUSA's body chosen
is_attract:
    sett
is_done:
    rts
    nop

.align 4
cars_at:
    .long  0x060540B6       ; each player's car, from 0, 6 bytes apart
bodies_at:
    .long  bodies
demo_at:
    .long  0x0601335C       ; the attract's demo, 0 outside it
choice_at:
    .long  0x002FC3A9

.org 0603CC34
; The car load's car number: the config's car from 1, 9 for DUSA's body.
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
; Each car's body, by car from 0: 0 CCE's only, 1 DUSA's or CCE's as
; chosen, 3 DUSA's always (the secret car). The 1s are the Hornet (DUSA's
; own Gallop) and the cars in tools/liveries.py's NINETY_FIVE, which
; tools/car_convert.py checks against this table.
bodies:                     ; a byte a car, two a word
    .word  0x0101           ; Hornet, Gallop
    .word  0x0001           ; Max, Phoenix
    .word  0x0000           ; Oriole, Magic
    .word  0x0000           ; Wolf, Balance
    .word  0x0300           ; the secret car, horse 1
    .word  0x0000           ; horse 2

.org 0602C9C0
; The TEX load (r4 the TEX file's name, r5 where it goes, r12 the player):
; a '95 car on DUSA's body loads its own paint, PLCAR3n (PLCAR5n in
; two-player) for car n from 1, over the name's digits; the Hornet and the
; secret car keep PLCAR09/29's, the Gallop.
tex_load:
    sts.l  pr,@-r15
    mov.l  is_dusa_at2,r0
    jsr    @r0
    mov    r12,r1
    bf     tex_go
    mov    r12,r0
    shll   r0
    add    r12,r0
    shll   r0               ; player x 6
    mov.l  cars_at2,r2
    mov.b  @(r0,r2),r0
    cmp/eq #8,r0
    bt     tex_go
    tst    r0,r0
    bt     tex_go
    add    #0x31,r0         ; '1' + car from 0
    mov.b  r0,@(6,r4)
    mov.l  mode_at,r2
    mov.b  @r2,r0
    cmp/eq #2,r0
    mov    #0x33,r0         ; '3'
    bf     tex_tens
    mov    #0x35,r0         ; '5' in two-player
tex_tens:
    mov.b  r0,@(5,r4)
tex_go:
    lds.l  @r15+,pr
    mov.l  tex_loader,r0
    jmp    @r0
    nop
.align 4
is_dusa_at2:
    .long  is_dusa
cars_at2:
    .long  0x060540B6
mode_at:
    .long  0x002FC233       ; 2 in two-player
tex_loader:
    .long  0x0604828C
