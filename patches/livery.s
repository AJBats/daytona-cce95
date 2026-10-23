; The Gallop's livery follows the transmission, as in DUSA: automatic is
; red/blue, manual yellow/red. Assembled into patches/livery.patch by
; tools/mkpatch.py.
;
; DUSA's two liveries share the pixels and differ in 16-colour tables 2-7
; (TEX_PL +0x40-0xE0 automatic, +0x100-0x1A0 manual; with the manual car
; DUSA's VRAM tables 2-7 hold the manual set). tools/car_convert.py puts
; the manual set in PLCAR01.TEX tables 8-13 and a copy of the automatic set
; in tables 16-21. After the player car's load relocates its texture table
; (call at 0604030E, r6 = the TEX tables in VRAM), this copies the set for
; player 1's transmission (config byte 060540B8, 0 = automatic, as car
; +0x174) over tables 2-7, before the race and its rolling start.
; Cave: after patches/reflection.s in the unreferenced 0603C304 function.

.org 060403AC
    .long  livery           ; was 060482F8, the relocation

.org 0603C594
livery:
    sts.l  pr,@-r15
    mov.l  relocate_at,r0
    jsr    @r0
    mov.l  r6,@-r15
    mov.l  @r15+,r6         ; tables
    mov.l  transmission_at,r0
    mov.b  @r0,r0
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
    lds.l  @r15+,pr
    rts
    nop
.align 4
relocate_at:
    .long  0x060482F8
transmission_at:
    .long  0x060540B8
