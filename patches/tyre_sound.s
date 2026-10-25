; DUSA's tyre sounds on CCE95, car tick side (docs/tyre_sound.md).
; Assembled into patches/tyre_sound.patch by tools/mkpatch.py.
;
; DUSA's car-tick sound routine (0602F7EA) drives two channels and a
; one-shot from the player's car, which CCE has no sound for: CCE plays a
; slide loop whenever either axle's grip is under 1.0 and retriggers a
; screech on its peel-out timer instead. Here CCE's car tick (06030AFA)
; runs DUSA's rules on CCE's fields, at 30 Hz, before it sends the engine
; values (06007940), and writes the results after the engine values in the
; player's mailbox (r4 = player: 6F10 player 1, 6F30 player 2 in 2P) for
; the driver (patches/tyre_sound_drv.s, patches/tyre_sound_bank0.s,
; patches/sound_2p_bank0.s):
;   6F10 |slip angle +0x68| >> 10 (DUSA +0x5C; the driver caps v at 7)
;   6F11 brake hold: 15 while moving (+0x24) with the pedal (+0x90) over
;        200, counting down after, off the tick it reaches 0 (DUSA: 10
;        ticks at 20 Hz)
;   6F12 count, 6F13 kind: the peel-out, when CCE's peel-out timer +0x176
;        (DUSA +0x166: onset 10, end 3) turns 15 (onset, kind 1) or 4 (the
;        end, kind 2); 6F14 the timer last tick. DUSA also waits for its
;        +0x1BC to be 0, which it always is in a race.
; CCE's slide loop (song 17) and screech (song 19) no longer start: their
; part of 06039014 is the cave, split around the literals at 06039064-
; 0603906D, which the function before it reads.

.org 06030BF8
    .long  tyres                ; was 06007940, called from 06030B70

.org 06039014
    mov.l  r14,@-r15            ; 06039014's entry, as before
    mov    r4,r14
    sts.l  pr,@-r15
    bra    0x060390B0           ; the rest: flag clears, bank 1 songs 9 and 12
    nop
tyres:                          ; r2 = the player's car; r4, r5 for 06007940
    mov.l  mailboxes,r6         ; 06007940's, by player
    extu.b r4,r0
    shll2  r0
    mov.l  @(r0,r6),r6
    add    #0x10,r6
    mov    #0x68,r0
    mov.l  @(r0,r2),r3          ; slip angle
    cmp/pz r3
    bt     slip_abs
    neg    r3,r3
slip_abs:
    shlr8  r3
    shlr2  r3
    mov    r3,r0
    mov.b  r0,@r6
    mov.b  @(1,r6),r0           ; brake hold
    tst    r0,r0
    bt     brake_check
    add    #-1,r0
    mov.b  r0,@(1,r6)
    tst    r0,r0
    bt     brake_done           ; ran out this tick: off, no check (DUSA)
brake_check:
    mov    #0x24,r0
    mov.l  @(r0,r2),r3          ; speed
    tst    r3,r3
    bt     brake_done
    bra    brake_pedal
    mov    #0x48,r0
    .align 4
mailboxes:
    .long  0x06010AB0

.org 0603906E
brake_pedal:
    shll   r0
    mov.l  @(r0,r2),r3          ; brake pedal, 0-255
    mov    #-56,r0
    extu.b r0,r0
    cmp/gt r0,r3                ; over 200
    bf     brake_done
    mov    #15,r0
    mov.b  r0,@(1,r6)
brake_done:
    mov.w  peel_timer,r0
    mov.w  @(r0,r2),r3
    mov.b  @(4,r6),r0
    cmp/eq r3,r0
    bt     send
    mov    r3,r0
    mov.b  r0,@(4,r6)
    mov    #1,r3
    cmp/eq #15,r0
    bt     peel
    mov    #2,r3
    cmp/eq #4,r0
    bf     send
peel:
    mov    r3,r0
    mov.b  r0,@(3,r6)
    mov.b  @(2,r6),r0
    add    #1,r0
    mov.b  r0,@(2,r6)
send:
    mov.l  engine_send,r0
    jmp    @r0
    nop
    .align 4
engine_send:
    .long  0x06007940
peel_timer:
    .word  0x0176
