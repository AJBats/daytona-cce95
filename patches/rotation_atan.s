; Core step rotation terms (CCE 06035F48, DUSA 0602D43C), computed DUSA's way.
; Assembled into patches/rotation_atan.patch by tools/sh2asm.py.
;
; The core step computes atan(grip_limit * grip * gain / v^2) twice:
;   rear  (gripR, gain +0x16E) -> a per-tick rotation limit on the slide rate
;   front (gripF, gain +0x16C) -> an angle that sets the yaw field +0x64
; CCE calls atan2(den = v^2, num) at 060360AC (rear) and 060361E4 (front).
;
; DUSA's atan (06027378, table TABLE.BIN at 002F0000, 1/256 steps):
;   q = |n| / den (16.16); index = (q + 128) >> 8 (rounded); r = table[index];
;   q >= 1 takes DUSA's piecewise atan; negate for n < 0; r == 0 -> a per-car
;   minimum (+0x7F rear, +0x7E front).
; CCE truncates to 1/512 steps and has no minimum.
;
; Units: CCE's gain is DUSA's x 8/27 (patch 7) and v^2 is x 4/9, so
; n = num x 3/2 over CCE's den gives DUSA's q exactly. CCE's atan table holds
; DUSA's at every even entry (identical values): table[2 * index]. For
; q >= 1, CCE's atan2 (finer than DUSA's piecewise).
; Minimums: DUSA Hornet +0x7F = 5, +0x7E = 7 (table 0602EE90), every car.
; The rear result is a per-tick rotation: x 2/3 (rounded) at 30 Hz. The
; front result is an angle: unchanged.
;
; The front angle then becomes yaw: DUSA yaw = t - (t - yaw) / 8 per tick
; (t: the new target), which CCE dropped (yaw = t). A filter like this has
; no exact 30 Hz twin: keeping (1/8)^(2/3) = 1/4 per tick matches its decay,
; keeping 3/17 matches its lag behind a moving target (k/(1-k) ticks:
; 1/7 x 50 ms = 3/14 x 33 ms). Yaw moves steadily through a slide, and the
; forced test favours lag: heading step error 132 -> 107, travel 166 -> 150. CCE has no room for it
; in place, so yaw_div replaces the divide helper call at 06036294 that
; produces t + (front - slip) and folds the smoothing into its result.
;
; Cave: 06032918, a 408-byte function with no caller: no branch to it in
; RACE.BIN, no pointer to it in any file on the disc, never executed.

.org 06032918
atan_rear:                  ; call site 060360AC: r4 = den, r5 = num
    sts.l  pr,@-r15
    bsr    dusa_atan
    mov    #5,r7
    mov.w  k2_3,r1
    muls.w r0,r1
    sts    macl,r0
    add    r0,r0            ; r x 43692 = r x 2/3 x 65536
    mov.l  half,r1
    add    r1,r0
    swap.w r0,r0
    exts.w r0,r0            ; round(r x 2/3)
    lds.l  @r15+,pr
    rts
    nop

atan_front:                 ; call site 060361E4: r4 = den, r5 = num
    sts.l  pr,@-r15
    bsr    dusa_atan
    mov    #7,r7
    lds.l  @r15+,pr
    rts
    nop

yaw_div:                    ; call site 06036294: r0 = r1 / r0, then yaw smoothing
    sts.l  pr,@-r15         ; caller: yaw = r0 - r5 (r5 = front - slip)
    mov.l  divide,r2
    jsr    @r2
    nop
    mov    r0,r3
    sub    r5,r3            ; t = new yaw target
    mov.w  yaw,r1
    mov    r14,r2
    add    r1,r2
    mov.l  @r2,r2           ; old yaw
    sub    r2,r3
    mov.l  yaw_keep,r1
    dmuls.l r1,r3
    sts    mach,r1
    sts    macl,r3
    xtrct  r1,r3            ; (t - old) x keep
    sub    r3,r0            ; caller stores t - (t - old) x keep
    lds.l  @r15+,pr
    rts
    nop

dusa_atan:                  ; r4 = den (>= 1), r5 = num, r7 = minimum; returns r0
    sts.l  pr,@-r15
    mov    r5,r0
    shar   r0
    add    r0,r5            ; n = num x 3/2
    cmp/pz r5
    movt   r6               ; r6 = 1 when n >= 0
    bt     pos
    neg    r5,r5
pos:
    mov    #-1,r2
    shll8  r2               ; r2 = FFFFFF00, divider
    mov.l  r4,@(0,r2)       ; DVSR = den
    mov    r5,r1
    shlr16 r1
    mov.l  r1,@(16,r2)      ; DVDNTH
    mov    r5,r3
    shll16 r3
    mov.l  r3,@(20,r2)      ; DVDNTL, starts the divide
    mov.l  @(28,r2),r0      ; q = |n| / den, 16.16
    add    #64,r0
    add    #64,r0           ; q + 128: round to DUSA's 1/256 step
    mov    #1,r1
    shll16 r1
    cmp/hi r0,r1
    bf     big              ; q >= 1
    shlr8  r0               ; DUSA index
    shll2  r0               ; CCE entry 2 x index, 2 bytes each
    mov.l  table,r1
    add    r1,r0
    bra    have
    mov.w  @r0,r0
big:
    mov.l  atan2,r0
    jsr    @r0              ; atan2(den, |n|); leaves r6, r7
    nop
have:
    tst    r0,r0
    bf     sign
    bra    done
    mov    r7,r0            ; DUSA minimum
sign:
    tst    r6,r6
    bf     done
    neg    r0,r0
done:
    lds.l  @r15+,pr
    rts
    nop

k2_3:
    .word  0x5556
yaw:
    .word  0x0064
.align 4
table:
    .long  0x0604C33C
atan2:
    .long  0x06047E0C
half:
    .long  0x00008000
divide:
    .long  0x06048160
yaw_keep:
    .long  0x00002D2D       ; 3/17, x 65536

; Call sites: the two atan2 calls and the yaw divide call get the routines.
.org 0603611C
    .long  atan_rear
.org 06036200
    .long  atan_front
.org 060362D0
    .long  yaw_div

; Front term scaling: DUSA (r * k) >> 8 (shlr8); CCE shifted >> 7 (seven
; shar, interleaved with other code) to make up for its smaller gain.
.org 0603623C
    shlr8  r6
.org 06036240
    nop
.org 06036244
    nop
    nop
    nop
    nop
    nop
