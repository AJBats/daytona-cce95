; High-speed grip loss in the core handling step (CCE 06035F48 pad variant,
; DUSA 0602D43C). Code: all cars. Assembled into
; patches/high_speed_grip_loss.patch by tools/mkpatch.py.
; DUSA, 20 Hz: if timer +0x166 <= 0, km/h >= 240, +0x40 != 0, grip +0x10C
;   <= 0x6800 and |slip rate +0x154| > 0x2F8: n = clamp(excess, 4, 10);
;   then each tick grip *= (10 - n)/10 while n counts down.
; CCE rewrote it: km/h >= 100, rear grip limit <= per-car value +0x148, only
;   when |slip angle +0x68| <= 0x300 (so never mid-slide), threshold 0x1B0,
;   n up to 48, divisor 48.
; Restored at 30 Hz: slip rate per tick x2/3, durations x3/2.
; Per car: CCE's +0x148 scales DUSA's grip threshold, as DUSA's coders would
; have made their 0x6800 a per-car number. Threshold = (+0x148 >> 16) x 13,
; so the Hornet (0x8000000) keeps 0x6800; Phoenix (0x9000000) 0x7500, sooner;
; the secret car and horse 2 (0x6000000) 0x4E00; Balance (0x1000000) 0x0D00,
; almost never. Bigger snaps more easily in both games.
; CCE also floored the countdown at 0 (06035FE2); DUSA doesn't, so when the
; -3 step (+0xC4 = 0, DUSA +0x11C) passes 0 its last tick multiplies grip
; by (10 + 1)/10 or (10 + 2)/10. With the floor gone the same tick here is
; (15 + 1)/15 or (15 + 2)/15, 1.067 and 1.133 (DUSA's to the power 2/3:
; 1.066, 1.129). Checked with n = 2 and +0xC4 = 0 poked in: n -> -1, grip
; 65536 -> 69905; with the floor n -> 0 and grip unchanged.

.org 06035F72
    mov.l  @(328,gbr),r0    ; +0x148 (was: load the rear grip limit for CCE's check)
    shlr16 r0
    mov    #13,r2
    mulu.w r2,r0
    mov    r14,r0
    sts    macl,r5          ; grip threshold
    neg    r5,r6

.org 06035F9A
    mov    #6,r1            ; n >= 6 ticks
.org 06035F9C
    mov    #15,r2           ; n <= 15 ticks

.org 06035FAE
    .word  0x01FB           ; slip-rate threshold 0x2F8 x 2/3
.org 06035FB0
    .word  0x00F0           ; speed >= 240 km/h
.org 06035FB6
    .word  0x0070           ; check grip +0x70 instead of the slip angle
.org 06035FBC
    .long  0x00006800       ; the Hornet's threshold, replaced per car above

.org 06035FE2
    nop                     ; was: cmp/pz r3, bt, mov #0,r3 (CCE's floor)
    nop
    nop

.org 0603608C
    .long  0x000F0000       ; grip *= (15 - n)/15
