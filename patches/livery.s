; The Gallop's livery follows the transmission, as in DUSA: automatic is
; red/blue, manual yellow/red. Assembled into patches/livery.patch by
; tools/mkpatch.py.
;
; DUSA's two liveries share the pixels and differ in 16-colour tables 2-7
; (TEX_PL +0x40-0xE0 automatic, +0x100-0x1A0 manual; with the manual car
; DUSA's VRAM tables 2-7 hold the manual set). tools/car_convert.py puts
; the manual set in PLCAR09.TEX tables 8-13 and a copy of the automatic set
; in tables 16-21. After a player car's load relocates its texture table
; (call at 0604030E, r6 = the TEX tables in VRAM, r11 = car number from 1,
; r12 = player), this copies the set for that player's transmission
; (config byte 060540B8 + 6 x player, 0 = automatic, as car +0x174) over
; tables 2-7, before the race and its rolling start. Only for car 9's
; files, DUSA's car, which the load also takes for the Hornet when DUSA's
; car is chosen (patches/car_choice.s): every other car's tables 8-21 are
; its own colours. Two-player split loads the low-detail cars PLCAR21+
; instead (0604028C adds 20); PLCAR29 is DUSA's low-detail Gallop with the
; same tables, so both players get their transmission's livery.
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
    cmp/eq #9,r0            ; DUSA's car (of 1-11)
    bf     livery_done
    mov    r12,r0
    shll   r0
    add    r12,r0
    shll   r0               ; player x 6
    mov.l  transmission_at,r1
    mov.b  @(r0,r1),r0
    tst    r0,r0
    movt   r1
    add    #1,r1
    shll8  r1
    add    r6,r1            ; tables 8 (manual) or 16 (automatic)
    add    #64,r6           ; table 2
    mov    #48,r2           ; 6 tables of 32 bytes
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
