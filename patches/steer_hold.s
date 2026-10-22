; Input timing as DUSA has it (CCE input step 06036CEC: throttle, brake,
; steering functions). Assembled into patches/steer_hold.patch by
; tools/mkpatch.py.
;
; DUSA's 20 Hz car tick treats a button as pressed if it was down in any
; frame since its previous tick: a 12-frame tap steers for 12, 15 or 15
; frames depending on tick phase (14 on average), and its brake pedal
; starts to release ~2 frames later than CCE's. CCE samples the pad once per
; 30 Hz tick. Here the input step sees the pad word OR'ed with the word from
; the previous tick, which gives the same +2 frames on average.
;
; Called in place of the throttle function, the first of the three (r1 = pad
; word, r13 = key config); jumps on to it with the OR'ed word in r1, which
; the throttle and brake functions only read, so the steering function gets
; it too. The previous word is kept per key-config struct (one slot: with
; two players alternating, the tag never matches and the hold simply doesn't
; apply).
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
    .long  0x06032A30       ; throttle routine (patches/throttle.s)
tag:
    .long  0
prev:
    .word  0
    .word  0

.org 06036DEC
    .long  steer_hold
