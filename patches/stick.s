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
; car through and through, and its steering is Stick Lab's (stickviz/steer.h,
; tried on the Saturn): stick X less 128, a dead zone of 8, the rest scaled so
; full tilt is the d-pad's 112. Outward the steer eases toward it at the
; d-pad's rate (1/14, 1/10, 1/6 of the gap a tick for HANDLING SLOW, NORMAL,
; QUICK), so a flick turns no faster than the d-pad; toward the centre it
; follows the stick at once, as the d-pad drops to 0 when let go, and across
; the centre it goes through 0 first, as the d-pad does when the other way is
; pressed. The wheel (type 1) keeps CCE's path as it was.
;
; The analog triggers stay CCE's (0603740E, 06037442): the pedal follows the
; trigger, gas and brake both, into DUSA's pedal scaling.

; Type 2's steering, in place of CCE's (r0 = r14 = car, r13 = its key
; config; the stick byte through the config's +8, the 2P mirror flag as CCE
; reads it).
.org 06037364
    mov.l  stick_at,r3
    add    r13,r3
    mov.l  @r3,r1
    mov.b  @r1,r1
    mov.l  mirror_at,r7
    mov.w  car_slot,r5
    add    r0,r5
    mov.b  @r5,r5
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
    mov    #127,r2
    cmp/gt r2,r1
    bf     tilt_held
    mov    r2,r1
tilt_held:
    add    #-8,r1           ; the dead zone
    cmp/pz r1
    bt     scale
    mov    #0,r1
scale:
    mov.w  full_scale,r2    ; 112 / 119, as 964 / 1024
    muls.w r1,r2
    sts    macl,r1
    shlr8  r1
    shlr2  r1
    mov    r1,r5            ; the target's size
    cmp/pz r6
    bt     target
    neg    r1,r1
target:
    mov.w  steer_field,r3
    mov.l  @(r0,r3),r4
    muls.w r4,r1            ; negative: the stick is across the centre from the steer
    sts    macl,r2
    cmp/pz r2
    bt     same_side
    mov    #0,r4
same_side:
    mov    r4,r2
    cmp/pz r2
    bt     size
    neg    r2,r2
size:
    cmp/gt r2,r5
    bt     ease
    bra    store            ; toward the centre: follow at once
    mov    r1,r4
ease:
    mov.w  handling_field,r2
    add    r0,r2
    mov.b  @r2,r2
    mov.l  divisors_at,r3
    add    r2,r3
    mov.b  @r3,r0
    sub    r4,r1
    mov.l  r4,@-r15
    sts.l  pr,@-r15
    mov.l  divide_at,r3
    jsr    @r3              ; r1 / r0 in r1, as the d-pad's ramp calls it
    nop
    lds.l  @r15+,pr
    mov.l  @r15+,r4
    add    r1,r4
    mov    r14,r0
store:
    mov.w  steer_field,r3
    rts
    mov.l  r4,@(r0,r3)
.align 4
stick_at:
    .long  8
mirror_at:
    .long  0x060527D8
divisors_at:
    .long  divisors
divide_at:
    .long  0x06048160
car_slot:
    .word  0x0012
full_scale:
    .word  964
steer_field:
    .word  0x0078
handling_field:
    .word  0x01C9
divisors:
    .word  0x0E0A           ; SLOW 14, NORMAL 10
    .word  0x0600           ; QUICK 6

; The core step: the analog one (0603631C) for the wheel only.
.org 0604D406
    dt     r2
    bf     0x0604D438

; The front wheels: set straight from the steer for the wheel only; the pad's
; filter (patches/wheel_filter.s) for the rest.
.org 0604D784
    dt     r2
    bt     0x0604D7B4
