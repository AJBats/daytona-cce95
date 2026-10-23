; Core step rear rotation clamp (CCE 06036100, DUSA 0602D5DC), at 30 Hz.
; Assembled into patches/rotation_clamp.patch by tools/mkpatch.py.
;
; The slide rate is set to (front term) - r11 per tick, where r11 = -r6 and
; r6 = 3 x the rear rotation term, clamped so it never exceeds the slip angle
; (+0x68 CCE, +0x5C DUSA): one tick can rotate the car at most back to
; straight. The rotation term is per tick (patch 8 scales it by 2/3), but the
; clamp is an angle that CCE left unscaled, so whenever the clamp applies CCE
; rotates 1.5x DUSA's amount per unit time. At 30 Hz the per-tick limit is
; 2/3 of the slip angle.
; Evidence (forced DUSA state, early-upshift peel-out, rel 192-198 and
; 246-252): unclamped ticks match DUSA (CCE r11 x 1.5 = -486 vs -486,
; -976 vs -975), clamped ticks are 1.5x (-1042 vs -738, -1371 vs -931).
;
; The scaled limit rounds away from zero, so a residual slip of a unit or
; two still straightens out (rounding it to 0 left the car with a
; permanent tiny slip on straights).
; The block at 06036100 calls the cave and returns r6; its old tail
; (06036124-0603612E) becomes unreachable. r7, written only on one clamp
; path, is dead (next written at 060361F2 before any read).
;
; Cave: the unreferenced function at 0603C304, after the camera routine.

.org 06036100
    mov.l  clamp_at,r1
    jsr    @r1
    nop
    bra    0x06036130
    nop
    nop
clamp_at:
    .long  clamp

.org 0603C4A0
clamp:                      ; r6 = rear rotation term, r5 = slip angle
    mov    #3,r4
    muls.w r4,r6
    neg    r5,r5
    sts    macl,r6          ; r6 = 3 x rotation
    mov.w  third,r1
    cmp/pz r5
    bf     negative
    muls.w r1,r5            ; r5 = -slip x 2/3 as r5 - floor(r5 / 3):
    sts    macl,r1          ; rounded away from 0, so a slip of one unit
    shlr16 r1               ; still straightens
    sub    r1,r5
    cmp/gt r5,r6
    bf     done
    rts
    mov    r5,r6
negative:
    neg    r5,r5
    muls.w r1,r5
    sts    macl,r1
    shlr16 r1
    sub    r1,r5
    neg    r5,r5
    neg    r6,r6
    cmp/gt r6,r5
    bf     done
    mov    r5,r6
done:
    rts
    nop
third:
    .word  0x5556           ; 65536 / 3 rounded up: exact floor(x / 3) for x < 32768
