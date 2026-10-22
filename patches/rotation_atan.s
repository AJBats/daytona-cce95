; Patch 8: core rotation term r6 computed the DUSA way, converted to 30 Hz.
; Assembled into patches/rotation_atan.patch by tools/sh2asm.py.
;
; Replaces CCE's call atan2(den = v^2, num = gripR * grip * gain) at 060360AC
; (core step 06035F48; DUSA 0602D43C). Same contract: r4 = den (>= 1),
; r5 = num, result in r0; clobbers r0-r6 (r6 is reassigned by the caller).
;
; DUSA (06027378, table TABLE.BIN at 002F0000, 1/256 steps):
;   q = |n| / den (16.16); index = (q + 128) >> 8 (rounded); r = table[index];
;   q >= 1 takes DUSA's piecewise atan; negate for n < 0; r == 0 -> +0x7F.
; CCE truncates to 1/512 steps and has no minimum, so a small q gives 0
; where DUSA gives 40: the restoring rotation is missing at corner entry.
;
; Units: CCE's gain is DUSA's x 8/27 (patch 7) and v^2 is x 4/9, so
; n = num x 3/2 is DUSA's numerator over CCE's den, giving DUSA's q.
; CCE's atan table has DUSA's at every even entry (identical values), so
; table[2 * index]. For q >= 1, CCE's atan2 (finer than DUSA's piecewise).
; Minimum: DUSA Hornet +0x7F = 5 (table 0602EE90); used for every car.
; The result is a per-tick rotation, so x 2/3 (rounded) at 30 Hz.
;
; Cave: 06032918, a 408-byte function with no caller: no branch to it in
; RACE.BIN, no pointer to it in any file on the disc, never executed.

.org 06032918
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
    jsr    @r0              ; atan2(den, |n|); leaves r6
    nop
have:
    tst    r0,r0
    bf     sign
    bra    conv
    mov    #5,r0            ; DUSA minimum
sign:
    tst    r6,r6
    bf     conv
    neg    r0,r0
conv:
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
k2_3:
    .word  0x5556
.align 4
table:
    .long  0x0604C33C
atan2:
    .long  0x06047E0C
half:
    .long  0x00008000
