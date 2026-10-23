; Tyre grip-limit filter (end of CCE 060354A0, DUSA 0602C690), Hornet path.
; Assembled into patches/grip_filter.patch by tools/mkpatch.py.
;
; DUSA, 20 Hz: limit += (target - limit) / 4 for both axles (+0x140/+0x144).
; CCE (+0xF4/+0xF8) keeps / 4 at 30 Hz for cars with +0x1CB == 2 (the
; Hornet) and / 16 for the rest. 30 Hz equivalent of DUSA's: keep
; (3/4)^(2/3) of the gap per tick, i.e. step 0.1747. The other cars keep
; their CCE ratio to the Hornet's step (1/16 vs 1/4): 0.1747 / 4 = 0.0437.
; Evidence (straight braking, throttle released, patches 16-17 in): with
; CCE's 1/4 the rear limit fell faster than DUSA's (75.1 vs 86.5 at frame
; 18) and the rear locked 2 frames early; converted, it tracks DUSA's within
; 2% (88.4, 78.0, 68.8 vs 86.5, 76.8, 68.0) and locks on the same frame.
; Called from 060355F2 with r0 = car, r1 = 0xF4, r10/r11 = targets;
; returns r1 = 0xF4, r3 = 0xF8, r2/r4 = new limits for the caller to store.
;
; Space: CCE's original throttle function (06036FDE), unused since patch 17
; (its only caller goes through the patched literal 06036DEC). The word at
; 06037014 stays: the function before it loads that literal.

.org 06036FDE
grip_filter:
    mov    r1,r3
    add    #4,r3            ; 0xF8
    mov.l  @(r0,r1),r2
    mov.l  @(r0,r3),r4
    sub    r2,r10
    sub    r4,r11
    mov.w  slide_path,r5
    mov.b  @(r0,r5),r6
    mov    #2,r5
    cmp/eq r6,r5
    mov.l  k,r5
    bt     scale
    mov.l  k_other,r5
scale:
    dmuls.l r5,r10
    sts    mach,r6
    sts    macl,r10
    xtrct  r6,r10           ; (target - limit) x step
    dmuls.l r5,r11
    bra    finish
    sts    mach,r6
.org 06037014
    .long  0x0000001C       ; kept: loaded by 06036FCC
finish:
    sts    macl,r11
    xtrct  r6,r11
    add    r10,r2
    rts
    add    r11,r4
slide_path:
    .word  0x01CB
.align 4
k:
    .long  0x00002CB9       ; 1 - (3/4)^(2/3) = 0.17470, x 65536
k_other:
    .long  0x00000B2E       ; 0.17470 / 4 = 0.04368, x 65536

; Call site: the old filter body from 060355F2 becomes a call, then joins the
; original stores at 0603561A. The literal reuses 06035638 (the 0xF8 and
; 0x1CB words; only the replaced code loaded them).
.org 060355F2
    mov.l  grip_filter_at,r5
    jsr    @r5
    nop
    bra    0x0603561A
    nop

.org 06035638
grip_filter_at:
    .long  grip_filter
