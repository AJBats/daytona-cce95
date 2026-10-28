; Each car on DUSA's body has its livery follow the transmission, as in
; DUSA: the Gallop automatic red/blue and manual yellow/red, a '95 car its
; two versions (docs/liveries.md). Assembled into patches/livery.patch by
; tools/mkpatch.py.
;
; The two liveries share the pixels and differ in 16-colour tables 2-14;
; tools/car_convert.py puts the automatic set there and the manual set in
; tables 16-28 of the car's TEX. After a player car's load relocates its
; texture table (call at 0604030E, r6 = the TEX tables in VRAM, r11 = car
; number from 1, r12 = player), this copies the manual set over tables
; 2-14 when that player's transmission is manual (config byte 060540B8 +
; 6 x player, 0 = automatic, as car +0x174), before the race and its
; rolling start. Only for car 9's files, DUSA's body, which the load also
; takes for a car with DUSA's body chosen (patches/car_choice.s): every
; other car's tables are its own colours. Two-player split loads the
; low-detail cars PLCAR21+ instead (0604028C adds 20); PLCAR29 and the
; '95 cars' PLCAR5n have the same tables, so both players get their
; transmission's livery.
; Cave: after the render setup of patches/camera.s in the unreferenced
; function at 0603C994.

.org 060403AC
    .long  livery           ; was 060482F8, the relocation

.org 0603CA90
livery:
    sts.l  pr,@-r15
    mov.l  relocate_at,r0
    jsr    @r0
    mov.l  r6,@-r15
    mov.l  @r15+,r6         ; tables
    mov    r11,r0
    cmp/eq #9,r0            ; DUSA's body (of 1-11)
    bf     livery_done
    mov    r12,r0
    shll   r0
    add    r12,r0
    shll   r0               ; player x 6
    mov.l  transmission_at,r1
    mov.b  @(r0,r1),r0
    tst    r0,r0
    bt     livery_done      ; automatic: the tables as loaded
    mov    #2,r1
    shll8  r1
    add    r6,r1            ; table 16, the manual set
    add    #64,r6           ; table 2
    mov    #104,r2          ; 13 tables of 32 bytes
copy:
    mov.l  @r1+,r0
    mov.l  r0,@r6
    dt     r2
    bf/s   copy
    add    #4,r6
livery_done:
    lds.l  @r15+,pr
    rts
    nop
.align 4
relocate_at:
    .long  0x060482F8
transmission_at:
    .long  0x060540B8
