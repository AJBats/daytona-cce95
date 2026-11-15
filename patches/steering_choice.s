; STEERING : AUTO / WHEEL / STICK, per player (Options > KEY CONFIG): which
; analog steering a car gets, whatever device it comes in on. Assembled
; into patches/steering_choice.patch by tools/mkpatch.py.
;
; Car setup (0603514C) gives each car its device in +0x16A from the port's
; SMPC ID: 0 pad, 1 Arcade Racer wheel, 2 the 3D pad and other analog pads.
; The device decides the inputs: the key table (06034D90), the input step
; (06036D06: the wheel's buttons, or the 3D pad's analog triggers), the
; grid's pedals (0603749E) and rpm chase (06039952). All of that stays.
; Four readers decide the steering, DUSA's analog model (patches/wheel.s)
; for 1 against the stick's (patches/stick.s) for 2:
; - the steering itself, which the wheel's input step (06036D7C) and the
;   stick's (06036DA6) each call last;
; - the rotation gains, at car init (060353EA);
; - the high-speed grip loss (wheel.s hs_select);
; - the front term's slope (patches/rotation_atan.s).
; They now ask steer_model: the device's own steering, or the player's
; choice (002FE7C0 + player, patches/save_ext.s, kept in the save) when it
; isn't AUTO. So a USB wheel on a 3D pad adapter, its pedals the triggers,
; can steer as the Arcade Racer does with WHEEL, and the Arcade Racer can
; take the stick's steering with STICK. A pad has no analog steering: the
; choice doesn't apply.
;
; Cave: CCE's analog core step (patches/wheel.s), after the grip loss.
; steer_model stays at 06036400: wheel.s and rotation_atan.s call it there.

; The gains (060353EA), r0 = GBR = car: r4 = the steering for the test
; after (060353EE, wheel.s), r0 kept. The gains' function saves no PR.
.org 060363E8
gains_hook:
    mov.l  r0,@-r15
    sts.l  pr,@-r15
    bsr    steer_model
    nop
    lds.l  @r15+,pr
    mov    r0,r4
    mov.l  @r15+,r0
    mov.l  gh_back,r1
    jmp    @r1
    nop
.align 4
gh_back:
    .long  0x060353EE

; GBR = car. r0: 1 the wheel's steering, 2 the stick's, 0 none (a pad);
; T set for the wheel's. Everything else kept.
.org 06036400
steer_model:
    mov.w  @(362,gbr),r0    ; +0x16A, the device
    tst    r0,r0
    bt     sm_out           ; a pad
    mov.l  r1,@-r15
    mov.l  r0,@-r15         ; the device
    mov.b  @(18,gbr),r0     ; the player
    mov.l  sm_choice,r1
    mov.b  @(r0,r1),r1      ; 0 AUTO, 1 WHEEL, 2 STICK
    mov    r1,r0
    add    #-1,r0
    shlr   r0
    tst    r0,r0            ; a choice: 1 or 2
    mov.l  @r15+,r0         ; the device, for AUTO
    bf     sm_pop
    mov    r1,r0            ; the choice
sm_pop:
    mov.l  @r15+,r1
sm_out:
    rts
    cmp/eq #1,r0

; The wheel's and the stick's input steps call here for their steering
; (r0 = r14 = car, r13 = the key config), and go on to the chosen one.
steer_dispatch:
    sts.l  pr,@-r15
    bsr    steer_model
    nop
    lds.l  @r15+,pr
    bt/s   sd_wheel
    mov    r14,r0
    mov.l  sd_stick,r12
    jmp    @r12
    nop
sd_wheel:
    mov.l  sd_wheel_at,r12
    jmp    @r12
    nop
.align 4
sm_choice:
    .long  0x002FE7C0
sd_stick:
    .long  0x06037364
sd_wheel_at:
    .long  0x06037200

.org 060353EA
    bra    gains_hook       ; was the type's load
    nop

.org 06036DF8
    .long  steer_dispatch   ; the wheel's input step's steering, was 06037200
.org 06036EEC
    .long  steer_dispatch   ; the stick's, was 06037364
