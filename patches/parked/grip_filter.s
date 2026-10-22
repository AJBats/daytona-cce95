; Tyre grip-limit filter (end of CCE 060354A0, DUSA 0602C690), Hornet path.
; Assembled into patches/grip_filter.patch by tools/sh2asm.py.
;
; DUSA, 20 Hz: limit += (target - limit) / 4 for both axles (+0x140/+0x144).
; CCE (+0xF4/+0xF8) keeps / 4 at 30 Hz for cars with +0x1CB == 2 (the
; Hornet) and / 16 for the rest. 30 Hz equivalent of DUSA's: keep
; (3/4)^(2/3) of the gap per tick, i.e. step 0.1747. Other cars keep / 16.
; Called from 060355F2 with r0 = car, r1 = 0xF4, r10/r11 = targets;
; returns r1 = 0xF4, r3 = 0xF8, r2/r4 = new limits for the caller to store.
;
; Cave: after the wheel filter in the dead function at 06032918.

.org 06032A40
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
    bf     other
    mov.l  k,r5
    dmuls.l r5,r10
    sts    mach,r6
    sts    macl,r10
    xtrct  r6,r10           ; (target - limit) x 0.1747
    dmuls.l r5,r11
    sts    mach,r6
    sts    macl,r11
    bra    done
    xtrct  r6,r11
other:
    shar   r10
    shar   r10
    shar   r10
    shar   r10
    shar   r11
    shar   r11
    shar   r11
    shar   r11
done:
    add    r10,r2
    rts
    add    r11,r4
slide_path:
    .word  0x01CB
.align 4
k:
    .long  0x00002CB9       ; 1 - (3/4)^(2/3) = 0.17470, x 65536

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
