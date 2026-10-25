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
; word, r0 = car, r13 = key config); jumps on to it with the OR'ed word in
; r1, which the throttle and brake functions only read, so the steering
; function gets it too. The previous word is kept per key-config struct, in
; two slots, one per player in 2-player play (the input step runs once a
; tick for each player's car, and only for players' cars).
;
; Cave: in the dead function at 06032918, after the wheel filter; the slots
; in the gap left at the end of the unreferenced 0603C304 function.

.org 060329FC
steer_hold:
    mov.l  slots_at,r2      ; slot: key config (long), previous pad word (long)
    mov.l  @r2,r3
    cmp/eq r13,r3
    bt     have
    tst    r3,r3
    bt     claim            ; slot 0 free
    add    #8,r2            ; slot 1
    mov.l  @r2,r3
    cmp/eq r13,r3
    bt     have
claim:
    mov.l  r13,@r2          ; a new controller: no previous word
    mov    #0,r3
    mov.l  r3,@(4,r2)
have:
    mov.l  @(4,r2),r3       ; pad word at the previous tick
    extu.w r1,r4
    mov.l  r4,@(4,r2)
    or     r3,r1
    mov.l  steer,r12
    jmp    @r12
    nop
.align 4
slots_at:
    .long  slots
steer:
    .long  0x06032A30       ; throttle routine (patches/throttle.s)

.org 0603C5B8
slots:
    .long  0
    .long  0
    .long  0
    .long  0

.org 06036DEC
    .long  steer_hold
