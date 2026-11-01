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
; The lens is set for the race in 06034CEC and again by the car's state
; handler (pit lane); 0x80 in two-player split is kept. Replay cameras and
; other modes set their own.
;
; One player only: two-player split (game mode byte 002FC233 = 2, the test
; the race lens uses) keeps CCE's camera, DUSA has no split screen. The
; view table keeps CCE's view 2; the 1P render setup writes DUSA's into it,
; so view switches move to DUSA's offset, and the 2P setup writes CCE's
; back. The chase pitch takes DUSA's view-2 pitch as a constant, since the
; camera may copy the table before the setup runs.
;
; Scripted cameras (the rolling start, the pit lane and the others the
; player at 060308C0 plays: keyframe tables 0604F0D8-0604F3A8) run with the
; pivot on the car and keyframes (distance, pitch, yaw) that start or end at
; CCE's chase framing (7.0, -6.5 deg; 21 of them). Their offset y comes
; from literals (060304E8 at the rolling start, 06030788 in the reset after
; a script; the pit lane eases it to 0 and back to 0603087C) or stays what
; the camera had. The chase routine folds DUSA's pivot shift into its
; offsets (below), so in 1P the setup writes that framing into the chase
; keyframes (distance 4.550, -18.3 deg) and the y literals (-0.314). The
; other keyframes are CCE's, made for CCE's y of -1.6: with -0.314 in them
; the pit lane's side view sat 1.3 units lower, the road's near edge in
; view. So the scripts keep CCE's y and the blend (script_blend) adds the
; chase's 1.286 in the measure the chase keyframes have where the script
; is: all of it at one, none between two of CCE's. The scripts then start
; and end at the chase framing without a jump, the rolling start too, and
; their sweeps are CCE's.
;
; Caves: the yaw routine after patches/ground_pitch.s in the unreferenced
; 0603C304 function; the chase routine in the unreferenced function at
; 0603C796 and the setup at 0603C994 (no calls, branches or pointers into
; them, never executed in 1P and 2P races with pit stops and every view).
; The chase starts after 0603C796's literals at 0603C7E0-0603C7FB, which
; 0603C5CC also reads. The blend in 0603CC64-0603CD33, a function only the
; unreferenced one before it branches to.

.org 06034D6A
    .word  0x00A0           ; race lens, was 0xE0

; The car's state handler (r14 = car) sets the race lens again when the
; pit lane takes the car over (06038168) and in a second state (0603827C),
; with the same 2-player 0x80 / else 0xE0 choice as the race start. Without
; these the lens stays at 0xE0 after a pit stop, and view switches keep it.
.org 06038252
    .word  0x00A0           ; was 0xE0
.org 06038378
    .word  0x00A0           ; was 0xE0

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

; view 2 (default chase) offset and pitch per mode, from the render setups
.org 060453A0
    .long  view_1p          ; was 060479D6, the 1P VDP1 setup
.org 060455F8
    .long  view_2p          ; was 06047A08, the 2P VDP1 setup

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
; The function jumps to its replacement in the cave; r0 = car.
.org 06035EE8
    mov.l  yaw_at,r1
    jmp    @r1
    nop
    nop
yaw_at:
    .long  yaw

; The yaw routine and the view-2 setup.
.org 0603C3B4
yaw:
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
    mov.l  game_mode_at,r1
    mov.b  @r1,r1
    add    #-2,r1
    tst    r1,r1
    bf     yaw_smooth
    add    r6,r3            ; two-player: CCE's halfway step
    shar   r3
    rts
    mov.l  r3,@r2
yaw_smooth:
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

.align 4
game_mode_at:
    .long  0x002FC233

; Render setups, once a race: write the chase framing for the mode into the
; view table (views 2 and 3 offset y, z; view 2 pitch), the scripts' chase
; keyframes and y literals (view 2's), clear the blend, then go on to the
; VDP1 setup they called.
.org 0603C994
view_1p:
    mov.l  vdp1_1p_at,r3
    mov.l  framing_dusa_at,r0
    bra    set_framing
    nop
view_2p:
    mov.l  vdp1_2p_at,r3
    mov.l  framing_cce_at,r0
set_framing:
    mov.l  view2_offset_at,r1
    mov.l  @r0+,r4
    mov.l  r4,@r1            ; view 2 offset y, the scripts' after a reset
    mov.l  @r0+,r5
    mov.l  r5,@(4,r1)        ; view 2 offset z, the scripts' chase keyframe distance
    mov.l  @r0+,r2
    mov.l  r2,@(12,r1)       ; view 3 offset y
    mov.l  @r0+,r2
    mov.l  r2,@(16,r1)       ; view 3 offset z
    mov.w  @r0,r0            ; pitch
    mov.l  view2_pitch_at,r1
    mov.w  r0,@r1
    mov.l  keyframes_at,r2
    mov    #21,r6
keyframe:
    mov.l  @r2+,r1
    mov.l  r5,@r1
    dt     r6
    bf/s   keyframe
    mov.w  r0,@(4,r1)
    mov.l  script_y_at,r2
    mov    #2,r6
script_y:
    mov.l  @r2+,r1
    dt     r6
    bf/s   script_y
    mov.l  r4,@r1
    mov.l  r6,@r2            ; the blend, after the literals' addresses
    jmp    @r3
    mov.l  r6,@(4,r2)
.align 4
vdp1_1p_at:
    .long  0x060479D6
vdp1_2p_at:
    .long  0x06047A08
view2_offset_at:
    .long  0x0604F0BC
view2_pitch_at:
    .long  0x0604F0D4
framing_dusa_at:
    .long  framing_dusa
framing_cce_at:
    .long  framing_cce
keyframes_at:
    .long  keyframes
script_y_at:
    .long  script_y_literals
framing_dusa:                ; 20 bytes, framing_cce after it
    .long  0xFFFFAFB3       ; view 2: y -0.314
    .long  0x00048CEC       ;         z 4.550
    .long  0xFFFD0B2A       ; view 3: y -2.956
    .long  0x00098326       ;         z 9.512
    .word  0xF300           ; pitch -18.3 deg
    .word  0
framing_cce:
    .long  0xFFFE6667       ; -1.6
    .long  0x00070000       ; 7.0
    .long  0xFFFD3334       ; -2.8
    .long  0x000A8000       ; 10.5
    .word  0xFB61           ; -6.5 deg
    .word  0
keyframes:                  ; (distance, pitch) of the chase framing
    .long  0x0604F118
    .long  0x0604F120
    .long  0x0604F154
    .long  0x0604F15C
    .long  0x0604F170
    .long  0x0604F178
    .long  0x0604F1B4
    .long  0x0604F1BC
    .long  0x0604F1D0
    .long  0x0604F1D8
    .long  0x0604F204
    .long  0x0604F20C
    .long  0x0604F218
    .long  0x0604F29C
    .long  0x0604F2A4
    .long  0x0604F2B0
    .long  0x0604F334
    .long  0x0604F33C
    .long  0x0604F348
    .long  0x0604F374
    .long  0x0604F3A0
script_y_literals:
    .long  0x06030788
    .long  0x0603087C
blend:
    .long  0                ; the bias a script's y carries
    .long  0                ; nonzero: the chase ran since a script last did

; The script player's first instructions go to the blend, which does them.
.org 060308C0
    mov.l  script_blend_at,r1
    jmp    @r1
    nop
    nop
script_blend_at:
    .long  script_blend

; In: r4 = keyframes, r5 = the script (steps a keyframe, keyframes), the
; camera at *06052094 with its keyframe at +60 and step at +62. Once the 1P
; setup has put the chase framing in the view table and the keyframes (not
; in two-player races, nor in the attract before a 1P race): the bias is our
; chase y's lead on CCE's times the weight of chase keyframes where the
; script is, ((this one's ? steps - step : 0) + (the next's ? step : 0)) /
; steps, and y takes its change. A script that starts
; from the chase finds y with its view's lead in it (views 2, 3), from
; views 0 and 1 without. The reset between scripts and the pit lane's ease
; back aim at CCE's y plus the bias, so the next script or the chase takes
; over with y as it was.
.org 0603CC64
script_blend:
    mov.l  sb_framing_at,r3
    mov.l  sb_view2_at,r0
    mov.l  @r0,r0
    mov.l  @r3,r1
    cmp/eq r1,r0
    bf     sb_play          ; CCE's framing in the view table: two players, or no 1P race yet
    sts.l  macl,@-r15
    mov.l  sb_cam_at,r6
    mov.l  @r6,r6
    mov.l  sb_blend_at,r7
    mov.l  @(4,r7),r0
    tst    r0,r0
    bt     sb_weight
    mov    #0,r2
    mov.l  r2,@(4,r7)
    mov    #44,r0
    mov.b  @(r0,r6),r0      ; view
    add    #-2,r0
    mov    #2,r1
    cmp/hs r1,r0
    bt     sb_lead
    shll2  r0
    shll   r0               ; view 3's entries 8 bytes on
    add    r3,r0
    mov.l  @r0,r2           ; our chase y
    mov.l  @(20,r0),r1      ; CCE's
    sub    r1,r2
sb_lead:
    mov.l  r2,@r7
sb_weight:
    mov.w  @r5,r1           ; steps
    mov    #62,r0
    mov.w  @(r0,r6),r2      ; step
    mov    #60,r0
    mov.w  @(r0,r6),r0      ; keyframe
    shll2  r0
    shll   r0
    add    r4,r0
    mov.l  @(4,r3),r7       ; the chase keyframes' distance
    mov.l  @(8,r0),r3       ; the next keyframe's
    cmp/eq r7,r3
    mov    #0,r3
    bf     sb_this
    mov    r2,r3
sb_this:
    mov.l  @r0,r0           ; this one's
    cmp/eq r7,r0
    bf     sb_bias
    add    r1,r3
    sub    r2,r3
sb_bias:
    mov.l  sb_framing_at,r7
    mov.l  @r7,r0
    mov.l  @(20,r7),r7
    sub    r7,r0            ; the chase's lead, 1.286
    mul.l  r0,r3
    sts    macl,r3
    mov    #-1,r7
    shll8  r7               ; the divider, FFFFFF00
    stc    sr,r2
    mov    r2,r0
    or     #0xF0,r0
    ldc    r0,sr
    mov.l  r1,@r7
    mov.l  r3,@(4,r7)
    mov.l  @(4,r7),r3       ; bias
    ldc    r2,sr
    mov.l  sb_blend_at,r7
    mov.l  @r7,r0
    mov.l  r3,@r7
    sub    r0,r3
    mov.l  @(24,r6),r0      ; offset y
    add    r3,r0
    mov.l  r0,@(24,r6)
    mov.l  sb_framing_at,r0
    mov.l  @(20,r0),r0      ; CCE's y
    mov.l  @r7,r3
    add    r3,r0
    mov.l  sb_literals_at,r1
    mov.l  @r1,r2
    mov.l  r0,@r2           ; the reset's
    mov.l  @(4,r1),r2
    mov.l  r0,@r2           ; the pit lane's
    lds.l  @r15+,macl
sb_play:
    mov.l  sb_back_at,r1
    mov.l  r14,@-r15
    mov    #60,r0
    mov.l  r13,@-r15
    mov.l  r12,@-r15
    mov.l  r11,@-r15
    jmp    @r1
    mov.l  r10,@-r15
.align 4
sb_view2_at:
    .long  0x0604F0BC
sb_cam_at:
    .long  0x06052094
sb_blend_at:
    .long  blend
sb_framing_at:
    .long  framing_dusa
sb_literals_at:
    .long  script_y_literals
sb_back_at:
    .long  0x060308CC

; In: r9 = player, r12 = car, r14 = camera (pivot = car position).
; Sets pitch and roll; returns r0 = camera yaw (+0x142).
; DUSA's pivot 1.0 ahead along the camera yaw is folded into the offset:
; seen from the camera it puts the car at (0, -sin t, -cos t) from the
; pivot, t the camera's downward pitch, whatever the yaw. The setup writes
; views 2 and 3 with it at their view pitch (t varies with the car's pitch
; by a few degrees: under 0.1 apart). So scripts, which keep the pivot on
; the car, can end exactly at the chase framing.
; Outside view switches the offset eases 1/8 per tick to the view's table
; entry: no change after a script, which ends at the chase framing.
; Two-player: CCE's code (pitch = car pitch / 2 + view pitch; the caller
; already set roll to the car's), then the two-player window reflection.
.org 0603C7FC
chase:
    mov.l  chase_mode_at,r0
    mov.b  @r0,r0
    cmp/eq #2,r0
    bf     chase_1p
    mov    #0,r3
    mov.w  @(12,r12),r0     ; car pitch
    mov    #50,r2
    cmp/gt r0,r3
    addc   r3,r0
    shar   r0
    add    r14,r2
    mov.w  @r2,r2           ; view pitch
    add    r2,r0
    mov.w  r0,@(12,r14)
    mov.w  cam_yaw,r0
    bra    0x0603CAD4       ; window reflection, patches/reflection.s
    mov.w  @(r0,r12),r0
chase_1p:
    mov.w  cam_yaw,r0
    mov.w  @(r0,r12),r0
    mov.l  r0,@-r15
    sts.l  pr,@-r15
    mov.l  blend_at,r1
    mov.l  r1,@(4,r1)       ; for the blend: a script next finds y in the chase's form
    mov    #46,r0
    mov.b  @(r0,r14),r0
    tst    r0,r0
    bf     eased            ; switching views: the transition sets the offset
    mov    #44,r0
    mov.b  @(r0,r14),r0
    extu.b r0,r0
    mov    r0,r1
    shll   r0
    add    r1,r0
    shll2  r0               ; view x 12
    mov.l  views_at,r2
    add    r0,r2
    mov    r14,r5
    add    #20,r5           ; camera offset (x, y, z)
    mov    #3,r6
ease:
    mov.l  @r2+,r3
    mov.l  @r5,r4
    sub    r4,r3
    shar   r3
    shar   r3
    shar   r3
    add    r3,r4
    mov.l  r4,@r5
    dt     r6
    bf/s   ease
    add    #4,r5
eased:
    mov.w  @(12,r12),r0     ; car pitch
    mov.l  pitch_gain,r1
    dmuls.l r0,r1
    sts    mach,r1
    sts    macl,r2
    xtrct  r1,r2
    mov    #44,r0
    mov.b  @(r0,r14),r0
    cmp/eq #2,r0
    mov.w  view2_pitch,r0   ; DUSA's view 2
    bt     pitch_base
    mov    #50,r0
    mov.w  @(r0,r14),r0     ; view pitch
pitch_base:
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
    mov.l  cos_at,r1
    mov.l  @(4,r15),r4
    mov.l  @(60,r12),r0     ; heading
    jsr    @r1
    sub    r0,r4
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
    lds.l  @r15+,pr
    rts
    mov.l  @r15+,r0
cam_yaw:
    .word  0x0142
roll_step:
    .word  0x5EBB           ; 0.370
view2_pitch:
    .word  0xF300           ; -18.3 deg
.align 4
chase_mode_at:
    .long  0x002FC233
pitch_gain:
    .long  0x0000E100       ; 0x384 / 1024 = 0.879
pitch_step:
    .long  0x000026D8       ; 1 - 0.78125^(2/3) = 0.152
views_at:
    .long  0x0604F0A0       ; view offsets, 12 bytes per view
cos_at:
    .long  0x06047D3C
roll_at:
    .long  roll
blend_at:
    .long  blend
roll:
    .word  0
    .word  0
