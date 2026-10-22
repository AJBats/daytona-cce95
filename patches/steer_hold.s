; Steering input timing as DUSA has it (CCE pad path 06036D52 -> 060370A0).
; Assembled into patches/steer_hold.patch by tools/sh2asm.py.
;
; DUSA's 20 Hz car tick treats LEFT/RIGHT as pressed if they were down in
; any frame since its previous tick: a 12-frame tap steers for 12, 15 or 15
; frames depending on tick phase (14 on average). CCE samples the pad once
; per 30 Hz tick, so a 12-frame tap steers for exactly 12. Here the steering
; step sees the pad word OR'ed with the word from the previous tick, which
; gives the same +2 frames on average. Only the steering function gets the
; OR'ed word; pedals and gears read the pad as before.
;
; Called in place of the steering function (r1 = pad word, r13 = key
; config); jumps on to it. The previous word is kept per key-config struct
; (one slot: with two players alternating, the tag never matches and the
; hold simply doesn't apply).
;
; Cave: in the dead function at 06032918, after the wheel filter.

.org 060329FC
steer_hold:
    mov.l  tag_at,r2
    mov.l  @r2,r3
    mov.l  prev_at,r4
    cmp/eq r13,r3
    bt     same
    mov.l  r13,@r2          ; new controller: no previous word
    mov    #0,r3
    mov.w  r3,@r4
same:
    mov.w  @r4,r3
    extu.w r3,r3            ; pad word at the previous tick
    mov.w  r1,@r4
    or     r3,r1
    mov.l  steer,r12
    jmp    @r12
    nop
.align 4
tag_at:
    .long  tag
prev_at:
    .long  prev
steer:
    .long  0x060370A0
tag:
    .long  0
prev:
    .word  0
    .word  0

.org 06036DF4
    .long  steer_hold
