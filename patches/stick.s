; The 3D pad's stick (and the Mission Stick's) drives DUSA's d-pad handling.
; Assembled into patches/stick.patch by tools/mkpatch.py.
;
; CCE gives each car a controller type at race setup (0603514C, car +0x16A):
; 0 pad, 1 Arcade Racer wheel (SMPC ID 0x13), 2 any other analog (the 3D pad
; in analog mode, 0x16, and the Mission Stick). Types 1 and 2 used CCE's
; analog core step (0603631C) and front wheels set straight from the steer
; (0604D780), neither of which our handling patches touch, so a 3D pad drove
; mostly CCE's car; and type 2's steering (06037364) followed the stick at
; once, a flick being full lock in one tick (the playtester's "way too
; sensitive"). DUSA's analog path was written for the wheel (the 3D pad came
; out a year later) and also follows at once.
;
; Now type 2 takes the pad's core step and front-wheel filter, the d-pad's
; car through and through (patches/wheel.s routes both analog types there),
; and its steering is Stick Lab's (stickviz/steer.h,
; tried on the Saturn). The handling reads the steer through CCE 0604D580
; (patches/steer_deadzone.patch): under 6 doesn't turn the car and past 80
; turns it no further, the d-pad's target of 112 only setting how fast it
; gets there. The 3D pad reaches its last value (X 0 or 255) with a third of
; the stick's travel to go, so the stick's own range is all of it: past a dead
; zone of 8 around 128 the target is 5 and 5/8 of the tilt, rounded up, 6 at
; the first count and 80 at the last. Outward the steer takes the d-pad's own
; steps (1/14, 1/10, 1/6 of the gap to 112 a tick for HANDLING SLOW, NORMAL,
; QUICK) and stops at the stick's target, so a flick turns no faster than the
; d-pad does and every target is reached; toward the centre it follows the
; stick at once, as the d-pad drops to 0 when let go, and across the centre it
; goes through 0 first, as the d-pad does when the other way is pressed. The
; wheel (type 1) has DUSA's analog path: patches/wheel.s.
;
; The analog triggers stay CCE's (0603740E, 06037442): the pedal follows the
; trigger, gas and brake both, into DUSA's pedal scaling.

; Type 2's steering, in place of CCE's (r0 = r14 = car, r13 = its key
; config; the stick byte through the config's +8, the 2P mirror flag as CCE
; reads it). Works in sizes on the stick's side (r6), the sign put on last.
.org 06037364
    mov.l  @(8,r13),r1
    mov.b  @r1,r1
    mov.l  mirror_at,r7
    mov.w  car_slot,r5
    mov.b  @(r0,r5),r5
    add    r5,r7
    mov.b  @r7,r7
    tst    r7,r7
    bt     upright
    .word  0x6117           ; not r1,r1
upright:
    extu.b r1,r1
    add    #-128,r1         ; -128 .. 127 from the centre
    mov    r1,r6
    cmp/pz r1
    bt     tilt
    neg    r1,r1
tilt:
    add    #-8,r1           ; past the dead zone
    cmp/pl r1
    bf/s   sized
    mov    #0,r5
    mov    r1,r5            ; 5 + ceil(5x / 8) = (5x + 47) / 8
    shll2  r5
    add    r1,r5
    add    #47,r5
    shlr2  r5
    shlr   r5
sized:                      ; r5: the target's size
    mov.w  steer_field,r3
    mov.l  @(r0,r3),r4
    cmp/pz r6
    bt     same_side
    neg    r4,r4
same_side:
    cmp/pz r4
    bt     outward
    mov    #0,r4            ; across the centre: through 0
outward:
    cmp/gt r4,r5
    bf     follow           ; toward the centre: follow at once
    mov.w  handling_field,r2
    mov.b  @(r0,r2),r2
    mova   divisors,r0
    mov.b  @(r0,r2),r0
    mov    #112,r1
    sub    r4,r1            ; the d-pad's gap to its target
    sts.l  pr,@-r15
    mov.l  divide_at,r3
    jsr    @r3              ; r1 / r0 in r1, as the d-pad's ramp calls it (keeps r2-r7)
    nop
    lds.l  @r15+,pr
    add    r1,r4
    mov    r14,r0
    cmp/gt r5,r4
    bf     signed
follow:
    mov    r5,r4            ; the stick's target
signed:
    cmp/pz r6
    bt     store
    neg    r4,r4
store:
    mov.w  steer_field,r3
    rts
    mov.l  r4,@(r0,r3)
.align 4
mirror_at:
    .long  0x060527D8
divide_at:
    .long  0x06048160
car_slot:
    .word  0x0012
steer_field:
    .word  0x0078
handling_field:
    .word  0x01C9
.align 4
divisors:
    .word  0x0E0A           ; SLOW 14, NORMAL 10
    .word  0x0600           ; QUICK 6
