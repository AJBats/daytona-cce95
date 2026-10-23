; Default chase camera DUSA's way (CCE 06030090 view 2 and 06035EE8; DUSA
; 0600BB94, 0600BF70, 0602CF96, 060053AC). Assembled into patches/camera.patch
; by tools/mkpatch.py.
;
; Both games build the view as offset + R(world - pivot) and project with
; screen = k x X / Z. DUSA vs CCE (view 2):
;   lens k         160 (0xA0)                  224 (0xE0)
;   pivot          car + 1.0 along camera yaw  car
;   offset         (0, 0, 5.5)                 (0, -1.6, 7.0)
;   pitch          car pitch x 0.879 - 18.3 deg,  car pitch / 2 - 6.5 deg
;                  smoothed 0.219 per 20 Hz tick
;   roll           car roll x cos(camera yaw - heading), car roll
;                  smoothed 1/2 per tick
;   yaw            travel + (heading - travel) / 4 + lead, smoothed 1/2 per
;                  tick in both; CCE's at 30 Hz, so it caught up 1.5x faster
; 30 Hz: pitch keeps 0.78125^(2/3) = 0.848 of the gap per tick, roll and yaw
; 0.5^(2/3) = 0.630.
; The lens is set for the race in 06034CEC (0x80 in two-player split, kept);
; replay cameras and other modes set their own.
;
; Cave: after patches/ground_pitch.s in the unreferenced 0603C304 function.

.org 06034D6A
    .word  0x00A0           ; race lens, was 0xE0

; Lens shift: DUSA's projection centre is 127 lines below the top of its
; 3D frame (its first VDP1 command spans y -127..), CCE's 112 of 224. On the
; TV DUSA's centre sits on line 143, CCE's on 120; 23 lines lower puts it on
; the same line. VDP1 local coordinates for the 3D pass (template copied to
; 0601BD20); the HUD is drawn with its own (0, 0) locals.
.org 06047A06
    .word  0x0087           ; local y 135, was 0x70 (112)

; Block culling (0602A9F0 -> 06047670) projects each track block's corners
; and drops the block when all of them fall outside +-176 x +-112 of the
; projection centre (render context +0x18, set from these templates). With
; the centre moved 23 lines down the screen reaches 135 lines above it, so
; mountains in the top lines were dropped (turn 3, the Sonic wall). The
; half-height becomes 135: the bottom bound is then 46 lines generous.
.org 06045406
    .word  0x0087           ; context 06057800, was 0x70
.org 060454C6
    .word  0x0087           ; context 06057C00, was 0x70

; view 2 (default chase): offset and pitch
.org 0604F0BC
    .long  0x00000000       ; offset y, was -1.6
    .long  0x00058000       ; offset z 5.5, was 7.0
.org 0604F0D4
    .word  0xF300           ; -18.3 deg, was 0xFB61 (-6.5 deg)

; views 2 and 3: pitch, roll and the pivot shift in the cave
.org 060303E6
    mov.l  chase_at,r0
    jsr    @r0
    nop
    bra    chase_yaw
    nop
chase_at:
    .long  chase
    nop
    nop
    nop
    nop
    nop
chase_yaw:

; camera yaw (car +0x134): same target, smoothing converted to 30 Hz.
; Replaces the function; r0 = car.
.org 06035EE8
    mov.l  @(60,r0),r3      ; heading
    mov.l  @(56,r0),r4      ; travel
    sub    r4,r3
    exts.w r3,r3
    shar   r3
    shar   r3
    add    r4,r3
    mov.w  lead_field,r1
    mov.w  yaw_field,r2
    add    r0,r2
    mov.l  @(r0,r1),r4
    shar   r4
    shar   r4
    shar   r4
    shar   r4
    shar   r4
    add    r4,r3            ; target
    mov.l  @r2,r6           ; previous
    mov    r6,r4
    mov    r6,r7
    mov.w  quarter,r8
    cmp/pz r7
    bt     yaw_abs
    neg    r7,r7
yaw_abs:
    cmp/gt r7,r8
    bt     yaw_step
    xor    r3,r4
    cmp/pz r4
    bt     yaw_step
    mov    #-1,r4           ; across +-0x8000: move previous by a turn
    shll16 r4
    xor    r4,r6
yaw_step:
    sub    r6,r3
    mov.w  yaw_keep,r1
    dmuls.l r1,r3
    sts    mach,r1
    sts    macl,r3
    xtrct  r1,r3
    add    r6,r3
    rts
    mov.l  r3,@r2
lead_field:
    .word  0x00AC
yaw_field:
    .word  0x0134
quarter:
    .word  0x4000
yaw_keep:
    .word  0x5EBB           ; 1 - 0.5^(2/3) = 0.370

; In: r9 = player, r12 = car, r14 = camera (pivot already = car position).
; Sets pitch and roll, shifts the pivot; returns r0 = camera yaw (+0x142).
.org 0603C3B4
chase:
    sts.l  pr,@-r15
    mov.w  cam_yaw,r0
    mov.w  @(r0,r12),r0
    mov.l  r0,@-r15
    mov.l  sin_at,r1
    jsr    @r1
    mov    r0,r4
    mov.l  @r14,r1
    sub    r0,r1
    mov.l  r1,@r14          ; pivot 1.0 ahead: x -= sin(yaw)
    mov.l  @r15,r4
    mov.l  cos_at,r1
    jsr    @r1
    nop
    mov.l  @(8,r14),r1
    add    r0,r1
    mov.l  r1,@(8,r14)      ; z += cos(yaw)
    mov.w  @(12,r12),r0     ; car pitch
    mov.l  pitch_gain,r1
    dmuls.l r0,r1
    sts    mach,r1
    sts    macl,r2
    xtrct  r1,r2
    mov    #50,r0
    mov.w  @(r0,r14),r0     ; view pitch
    add    r0,r2            ; target
    mov    #46,r0
    mov.b  @(r0,r14),r0
    tst    r0,r0
    bf     set_pitch        ; switching views: no smoothing
    mov.w  @(12,r14),r0
    sub    r0,r2
    mov.l  pitch_step,r1
    dmuls.l r1,r2
    sts    mach,r1
    sts    macl,r2
    xtrct  r1,r2
    add    r0,r2
set_pitch:
    mov    r2,r0
    mov.w  r0,@(12,r14)
    mov.l  @r15,r4
    mov.l  @(60,r12),r0     ; heading
    sub    r0,r4
    mov.l  cos_at,r1
    jsr    @r1
    nop
    mov    r0,r2
    mov.w  @(16,r12),r0     ; car roll
    dmuls.l r0,r2
    sts    mach,r1
    sts    macl,r3
    xtrct  r1,r3            ; target
    extu.b r9,r0
    add    r0,r0
    mov.l  roll_at,r1
    mov.w  @(r0,r1),r4      ; previous, per player
    sub    r4,r3
    mov.w  roll_step,r5
    dmuls.l r5,r3
    sts    mach,r5
    sts    macl,r3
    xtrct  r5,r3
    add    r4,r3
    mov.w  r3,@(r0,r1)
    mov    r3,r0
    mov.w  r0,@(16,r14)
    mov.l  @r15+,r0
    lds.l  @r15+,pr
    rts
    nop
cam_yaw:
    .word  0x0142
roll_step:
    .word  0x5EBB           ; 0.370
.align 4
pitch_gain:
    .long  0x0000E100       ; 0x384 / 1024 = 0.879
pitch_step:
    .long  0x000026D8       ; 1 - 0.78125^(2/3) = 0.152
sin_at:
    .long  0x06047D20
cos_at:
    .long  0x06047D3C
roll_at:
    .long  roll
roll:
    .word  0
    .word  0
