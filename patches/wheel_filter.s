; Front wheel angle filter, pad (CCE 0604D780, DUSA 0602F0E8), converted to 30 Hz.
; Assembled into patches/wheel_filter.patch by tools/sh2asm.py.
;
; DUSA, 20 Hz: wheel = (steer << 8 + wheel) / 2, half the gap left per tick.
; CCE kept the halving at 30 Hz, so its wheel follows the steering faster.
; 30 Hz: (1/2)^(2/3) = 0.630 of the gap left, so wheel += (t - wheel) x 0.370.
; CCE has no room for the multiply in place; its pad path now calls this
; (r0 = car; keeps r0).
;
; Cave: after the rotation routines in the dead function at 06032918.

.org 060329D8
wheel_pad:
    mov.w  steer,r1
    mov.l  @(r0,r1),r2
    shll8  r2               ; t = scaled steer << 8
    mov.w  wheel,r3
    mov.l  @(r0,r3),r4      ; wheel
    sub    r4,r2
    mov.l  k,r1
    dmuls.l r1,r2
    sts    mach,r1
    sts    macl,r2
    xtrct  r1,r2            ; (t - wheel) x 0.370
    add    r4,r2
    rts
    mov.l  r2,@(r0,r3)
steer:
    .word  0x007C
wheel:
    .word  0x00AC
.align 4
k:
    .long  0x00005EBB       ; 1 - 0.5^(2/3) = 0.370040, x 65536

; Call site: the pad path's filter becomes sts.l pr ; mov.l @lit,r1 ;
; jsr @r1 ; nop ; lds.l pr ; bra 0604D7BE ; nop. The literal reuses
; 0604D7AC, whose two words (0x7C, 0xAC) only the old pad path loaded.
.org 0604D788
    sts.l  pr,@-r15
    mov.l  wheel_pad_at,r1
    jsr    @r1
    nop
    lds.l  @r15+,pr
    bra    0x0604D7BE
    nop

.org 0604D7AC
wheel_pad_at:
    .long  wheel_pad
