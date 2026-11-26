; The 3D pad's analog triggers while racing: the trigger sets a target and
; the pedal moves toward it at DUSA's button rates (CCE 0603740E gas,
; 06037442 brake; Stick Lab's NEW TRIG, stickviz/pedal.h). Assembled into
; patches/trigger_pedals.patch by tools/mkpatch.py.
;
; CCE set the raw pedal straight from the trigger: gas trigger / 2 + 56,
; brake trigger / 2 + 88 at any touch. Through DUSA's brake scaling
; (patches/brake_pedal.s) the lightest touch was a third of the brake and
; half a pull all of it, and letting go dropped both pedals at once. DUSA
; has no analog pedals (the Arcade Racer's are buttons).
;
; Here the travel past a dead zone of 8 is spread over the pedal: gas raw
; 56 + travel x 128 / 240 (full, 184, from trigger 248), brake raw 56 +
; travel x 96 / 240 (full brake, 152, at trigger 247). Below the target the
; pedal takes one tick of the button held, above it one tick of the button
; let go, and either way stops at the target: the button's own functions
; (patches/throttle.s, patches/brake_pedal.s) do the tick. So the gas
; climbs +7 a tick and jumps from 160 to the target, and falls with DUSA's
; slow then fast release; the brake climbs +27 a tick and keeps 5/8 a tick
; falling. From trigger 248 the brake is the button itself, its overshoot
; to 191 or more included. A full trigger is DUSA's button tick for tick;
; a part trigger holds part of the pedal. The pressed flags (+0x84 gas,
; +0x94 brake) are the trigger past the dead zone.
;
; Called from the stick's input routine (06036DFC, 06036E30) with r0 = car,
; r1 = pad word, r13 = key config, GBR = car (the button brake's release
; reads the car through it); r1 is kept for the button brake and the
; steering that follow. The trigger bytes come through the key config's
; +0xC (gas) and +0x10 (brake), as CCE's did.
;
; The entries are rewritten in their own space (0603740E-06037483, nothing
; else calls them since patch 28); the shared part goes in the cave
; 06036670-060366EB, the tail of CCE's analog core step (patches/wheel.s)
; before the speed / rpm function at 060366EC.

.org 0603740E
trigger_gas:
    mov.l  @(12,r13),r2
    mov.b  @r2,r2
    extu.b r2,r2            ; the trigger
    mov    #56,r6           ; target: rest
    mov    #8,r3
    cmp/hi r3,r2
    bf/s   g_go             ; within the dead zone
    movt   r5               ; pressed: past it
    add    #-8,r2           ; the travel past it
    mov    #-16,r3
    extu.b r3,r3            ; 240
    cmp/hs r3,r2
    bf     g_part
    mov    r3,r2            ; full travel
g_part:
    shll2  r2
    shll   r2
    mov.w  k15,r3
    mulu.w r3,r2
    sts    macl,r2
    shlr16 r2               ; travel x 8 / 15 = travel x 128 / 240
    add    r2,r6
g_go:
    bra    gas_approach
    nop
k15:
    .word  4370             ; 65536 / 15, rounded up: exact for travel x 8 up to 1920

.org 06037442
trigger_brake:
    mov.l  @(16,r13),r2
    mov.b  @r2,r2
    extu.b r2,r2            ; the trigger
    mov    #56,r6           ; target: rest
    mov    #8,r3
    cmp/hi r3,r2
    bf/s   b_go             ; within the dead zone
    movt   r5               ; pressed: past it
    add    #-8,r2           ; the travel past it
    mov    #-16,r3
    extu.b r3,r3            ; 240
    cmp/hs r3,r2
    bt     b_full
    shll   r2
    mov.w  k5,r3
    mulu.w r3,r2
    sts    macl,r2
    shlr16 r2               ; travel x 2 / 5 = travel x 96 / 240
    bra    b_go
    add    r2,r6
b_full:                     ; the button itself: a target it never reaches
    mov    #127,r6
    shll   r6               ; 254
b_go:
    bra    brake_approach
    nop
k5:
    .word  13108            ; 65536 / 5, rounded up: exact for travel x 2 up to 478

.cave 06036670 060366C7
.org 06036670
gas_approach:               ; r5 = pressed, r6 = target
    mov.l  throttle_at,r3
    mov    #-120,r7
    bra    approach
    extu.b r7,r7            ; +0x88, the raw gas
brake_approach:
    mov.l  brake_at,r3
    mov    #-104,r7
    extu.b r7,r7            ; +0x98, the raw brake
approach:                   ; r3 = the button's function, r7 = the raw field
    sts.l  pr,@-r15
    mov.l  r1,@-r15
    mov.l  @(r0,r7),r4
    cmp/eq r4,r6
    bt     a_flag           ; at the target
    mov    #0,r1            ; the button let go, unless below the target
    cmp/gt r4,r6
    bf     a_tick
    mov    #-1,r1           ; held: every mask bit
a_tick:
    mov.l  r7,@-r15
    mov.l  r6,@-r15
    mov.l  r5,@-r15
    jsr    @r3              ; one tick of DUSA's button
    nop
    mov.l  @r15+,r5
    mov.l  @r15+,r6
    mov.l  @r15+,r7
    mov.l  @(r0,r7),r4
    tst    r1,r1
    bt     a_down
    cmp/gt r6,r4            ; held: no further than the target
    bf     a_flag
    bra    a_flag
    mov.l  r6,@(r0,r7)
a_down:
    cmp/ge r6,r4            ; let go: no lower than the target
    bt     a_flag
    mov.l  r6,@(r0,r7)
a_flag:
    add    #-4,r7
    mov.l  r5,@(r0,r7)      ; +0x84 / +0x94: pressed
    mov.l  @r15+,r1
    lds.l  @r15+,pr
    rts
    nop
.align 4
throttle_at:
    .long  0x06032A30       ; patches/throttle.s (r1 = pad word, r13 = key config)
brake_at:
    .long  0x0603704A       ; CCE's brake input with patches/brake_pedal.s
