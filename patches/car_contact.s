; Impact slip decay in the tyre step (CCE 06035A68, DUSA 0602CBEA): touching
; another car no longer ends a slide, and a wall scrape's decay runs at 30 Hz.
; Assembled into patches/car_contact.patch by tools/mkpatch.py.
;
; While an impact timer runs (DUSA +0x150, CCE +0x190), both games' tyre
; step take a share of the slip angle out each tick, move the yaw with it,
; and zero the lateral forces.
;   DUSA: a quarter per 20 Hz tick. Only a wall scrape sets the timer
;     (06030BA8, to 4); the car contact (06030FC0) leaves the player's
;     timer alone and writes +0x208 on the other car.
;   CCE: half per 30 Hz tick. A wall scrape sets the timer to 8 (0603786E),
;     and so does every car contact: the player faster (0603A9E0) or slower
;     (0603AD86), and the two-player contact (0603B132). Touching a car
;     mid-slide halved the slip on each of 8 ticks, leaving under 1% of it.
;     Players: "it immediately snaps you out of the drift".
;
; The timer also runs the sparks (06038C64) and the scrape sound (06038DD8)
; while it is non-zero, so it stays. Car contacts now set it to 2, wall
; scrapes still to 8, and the decay runs only while it is above 2: 6 ticks
; after a wall scrape (DUSA's 4, x 3/2), none after a car contact. The
; share is 1 - 0.75^(2/3) = 0.1745 a tick. A car's sparks now trail 2 ticks
; after the cars part, not 8 (they still run every tick the cars touch).
;
; Not DUSA's: a car contact during a wall scrape's 6 ticks ends that decay.
;
; Cave: 06035EF4-06035F47, the body of CCE's old camera-yaw function, which
; patches/camera.s leaves from its first instruction; nothing else
; branches into it.

.org 06035A68
    mov.l  decay_at,r1
    jsr    @r1
    nop
    bra    0x06035A96
    nop
    nop
decay_at:
    .long  decay

.org 0603A9E2
    mov    #2,r2            ; car contact, the player faster: timer 2, was 8

.org 0603AD88
    mov    #2,r2            ; car contact, the player slower

.org 0603B134
    mov    #2,r2            ; two-player contact

.org 06035EF4
decay:                      ; r0 = car, kept; uses r1-r4, r7, r11
    mov.w  timer,r1
    mov.w  @(r0,r1),r2
    mov    #2,r3
    cmp/gt r3,r2
    bf     decay_done
    mov.w  yaw,r1
    mov.l  @(r0,r1),r3
    mov.w  slip,r4
    mov.l  @(r0,r4),r7
    mov.l  share,r2
    dmuls.l r7,r2
    sts    mach,r2
    sts    macl,r11
    xtrct  r2,r11           ; r11 = slip x share
    sub    r11,r7
    sub    r11,r3
    mov.l  r3,@(r0,r1)
    mov.l  r7,@(r0,r4)
    mov    #0,r11
    mov.w  lateral,r1
    mov.l  r11,@(r0,r1)     ; lateral forces +0xE8 and +0xEC
    add    #4,r1
    mov.l  r11,@(r0,r1)
decay_done:
    rts
    nop
timer:
    .word  0x0190
yaw:
    .word  0x0064
slip:
    .word  0x0068
lateral:
    .word  0x00E8
.align 4
share:
    .long  0x00002CAD       ; 1 - 0.75^(2/3), 16.16
