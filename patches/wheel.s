; The Arcade Racer wheel drives DUSA's analog path. Patch 33.
; Assembled into patches/wheel.patch by tools/mkpatch.py.
;
; A car's controller type is car +0x16A (0603514C): 0 pad, 1 Arcade Racer
; wheel (SMPC ID 0x13), 2 the 3D pad and other analog pads. DUSA has two:
; +0x9E clear for the pad, set for the wheel. DUSA's wheel path is its pad
; path but for three things, all keyed on +0x9E (its only readers):
; - Steering (0603004C): steer = wheel byte - 128 at once, no dead zone, no
;   table; HANDLING doesn't exist. The pad's ramp is skipped.
; - Rotation gains (car init 0602ED7A): table 0602EE58, not the pad's
;   0602EE20. The Hornet's front gain 0x1180 -> 0x10C0, rear 0x1180 -> 0xF80.
; - The core step (0602D08A, the pad's 0602D43C): the same code but for the
;   high-speed grip loss, and the front term's speed slope 4 for the pad's 3
;   (patches/rotation_atan.s).
; The pedals, gears and front-wheel filter are the pad's: buttons on the
; wheel, as on the pad.
;
; CCE's wheel ran all of its own: the byte doubled through a table with a
; dead zone (06037200, so full lock came at 38% of the wheel's turn; DUSA's
; scaling saturates at 80, 63%), CCE's analog core step (0603631C, none of
; our handling patches), the pad's gains and the front wheels set straight
; from the raw steer with no filter. Now the wheel takes the pad's core step
; and filter (all our handling) with DUSA's three differences on top. The
; 3D pad (type 2) keeps the pad's gains and grip loss (patches/stick.s).
;
; Cave: CCE's analog core step, 0603631C-060366EB, which only the wheel ran
; (one literal at 0604D434 pointed at it).

; Steering, DUSA's (r0 = r14 = car, r13 = key config, the wheel's byte
; through the config's +8). Both games centre the wheel at 127 (DUSA
; inverts the byte and takes 128; CCE subtracted 1 and then 126); CCE's
; sign is kept, and the mirrored courses negate it as CCE meant to (its
; byte arithmetic left them 3 off centre). HANDLING doesn't apply, as in
; both games.
.org 06037200
wheel_steer:
    mov.l  @(8,r13),r1
    mov.b  @r1,r1
    extu.b r1,r1
    add    #-127,r1         ; -127 .. 128
    mov.l  mirror_at,r7
    mov.w  car_slot,r5
    mov.b  @(r0,r5),r5
    add    r5,r7
    mov.b  @r7,r7
    tst    r7,r7
    bt     steer_store
    neg    r1,r1            ; a mirrored course
steer_store:
    mov.w  steer_field,r3
    rts
    mov.l  r1,@(r0,r3)
.align 4
mirror_at:
    .long  0x060527D8
car_slot:
    .word  0x0012
steer_field:
    .word  0x0078

; Gains: the wheel's own table (car init 060353EA). CCE kept DUSA's branch
; on the type but pointed both ways at the pad's table, and the 3D pad
; (type 2) took that way too: now only type 1 does.
.org 060353EE
    dt     r4               ; was tst: type 1 only
.org 060353F2
    bf     0x060353F6
.org 0603548C
    .long  wheel_gains

; The core step: the pad's for every car (CCE sent type 1 to 0603631C).
.org 0604D406
    bra    0x0604D438
    nop

; The front wheels: the pad's filter (patches/wheel_filter.s) for every car
; (CCE set them straight from the raw steer for analog types).
.org 0604D784
    nop
    nop

; High-speed grip loss: the wheel's in the cave, the pad's in place.
.org 06035F56
    bra    hs_select
    cmp/pl r7

.org 0603631C
; DUSA's analog gains in CCE's units, x 8/27 (patch 7): the Hornet front
; 0x10C0 -> 0x4F7, rear 0xF80 -> 0x498. DUSA has no counterparts for CCE's
; other cars, so each keeps its CCE ratio to the Hornet, as for the pad's
; (tools/car_rescale.py): CCE value x 0x4F7 / 0x3A0 (front), x 0x498 /
; 0x3A0 (rear). Per car: front, rear.
wheel_gains:
    .word  0x04F7           ; 0 Hornet
    .word  0x0498
    .word  0x054F           ; 1
    .word  0x04E9
    .word  0x05FE           ; 2
    .word  0x058B
    .word  0x04F7           ; 3
    .word  0x0498
    .word  0x0565           ; 4
    .word  0x046F
    .word  0x057A           ; 5
    .word  0x0512
    .word  0x03F0           ; 6
    .word  0x03A5
    .word  0x05FE           ; 7
    .word  0x0656
    .word  0x0838           ; 8
    .word  0x08DF
    .word  0x057A           ; 9
    .word  0x0512
    .word  0x0996           ; 10
    .word  0x08DF
    .word  0x057A           ; 11
    .word  0x0512
    .word  0x050D           ; 12
    .word  0x0526
    .word  0x050D           ; 13
    .word  0x0526

; From the core step's start (r0 = r14 = car, r7 = the grip-loss timer
; +0x176, r10 = slip rate +0x44, r11 = 0x18E, the countdown's field).
; DUSA's analog grip loss (0602D08A), 20 Hz: if the timer is out, km/h >=
; 260, |slip angle| <= 0x300 and |slip rate| > 0x2E0: n = clamp(excess, 4,
; 15). Then while n > 0: n -= 1 (3 while +0x11C < 0), grip *= (15 - n)/15.
; The pad's: km/h >= 240, +0x40 set, grip <= 0x6800, |slip rate| > 0x2F8,
; n up to 10, -3 while +0x11C = 0, divisor 10. At 30 Hz as the pad's is
; (patches/high_speed_grip_loss.s): slip rate x 2/3 (0x1EB), counts and
; divisor x 3/2 (6 to 22, 22.5). Neither DUSA core floors n at 0, so a
; countdown that ends below 0 gives a last tick over 1 (16/15 or 17/15,
; 23.5/22.5 or 24.5/22.5 here). The flag in +0x30 is CCE's, as in the pad's.
hs_select:
    mov.w  type_field,r1
    mov.w  @(r0,r1),r1
    dt     r1
    bt     hs_wheel
    cmp/pl r7
    bf     hs_pad_onset
    bra    0x06035FD0       ; the pad's countdown
    nop
hs_pad_onset:
    bra    0x06035F5A       ; the pad's onset
    nop
hs_wheel:
    cmp/pl r7
    bt     hs_count
    mov.l  @(52,r0),r7      ; km/h
    mov.w  hs_kmh,r8
    cmp/gt r7,r8
    bt     hs_count
    mov.w  slip_angle,r2
    mov.l  @(r0,r2),r9
    mov.w  hs_angle,r5
    neg    r5,r6
    cmp/gt r5,r9
    bt     hs_count
    cmp/gt r9,r6
    bt     hs_count
    mov.w  hs_rate,r3
    neg    r3,r4
    mov    r10,r8
    cmp/gt r3,r10
    bt     hs_over
    cmp/ge r4,r10
    bt     hs_count
    neg    r8,r8
hs_over:
    sub    r3,r8            ; the excess
    mov    #6,r1
    cmp/gt r1,r8
    bt     hs_cap
    bra    hs_onset
    mov    r1,r8
hs_cap:
    mov    #22,r2
    cmp/gt r8,r2
    bt     hs_onset
    mov    r2,r8
hs_onset:
    mov.l  @(48,r0),r1
    mov    #2,r3
    or     r3,r1
    mov.l  r1,@(48,r0)
    mov.w  r8,@(r0,r11)
hs_count:
    mov.w  @(r0,r11),r3
    cmp/pl r3
    bf     hs_none
    mov.w  rear_field,r1    ; +0xC4, DUSA's +0x11C
    mov.l  @(r0,r1),r4
    cmp/pz r4
    bt     hs_one
    add    #-2,r3
hs_one:
    add    #-1,r3
    mov.l  @(48,r0),r2
    mov    #2,r4
    or     r4,r2
    mov.l  r2,@(48,r0)
    mov.w  r3,@(r0,r11)
    mov.l  hs_divisor,r4
    bra    0x06035FF4       ; the pad's grip scaling, with this divisor
    nop
hs_none:
    bra    0x06036026
    nop
type_field:
    .word  0x016A
hs_kmh:
    .word  260
slip_angle:
    .word  0x0068
hs_angle:
    .word  0x0300
hs_rate:
    .word  0x01EB           ; 0x2E0 x 2/3
rear_field:
    .word  0x00C4
.align 4
hs_divisor:
    .long  0x00168000       ; 22.5
