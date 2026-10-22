; Throttle input, DUSA's at 30 Hz (CCE 06036FDE; DUSA 0602FE6E/0602FEAC).
; Assembled into patches/throttle.patch by tools/mkpatch.py.
;
; Raw throttle (CCE +0x88, DUSA +0x74) rests at 56; pedal = (raw - 56) x
; 255 / 128 in both, full at raw 184.
;   pressed:  DUSA +10 per 20 Hz tick, and once raw reaches 160 it jumps to
;             184 (full); CCE +6 per 30 Hz tick, no jump.
;   released: both: while raw > 176, -1 per tick; below, raw -= raw/16;
;             under 111 it drops to 56. Per tick, so CCE ran both phases
;             1.5x faster (on the back straight its engine drive fell from
;             frame 16, DUSA's from frame 28, and its rear locked earlier
;             under braking).
; 30 Hz: +7 per tick (6.67) with DUSA's jump; the slow phase steps -1 on two
; ticks out of three; the fast phase removes raw/24 per tick
; ((15/16)^(2/3) = 0.958 kept).
; Replaces the function: r0 = car, r1 = pad word, r13 = key config; sets
; +0x84 (pressed flag) like the original. (The original also left +0x17C in
; r9; no caller reads it: the input step saves and restores r9.)
;
; Cave: the dead function at 06032918, after the steering hold.

.org 06032A30
throttle:
    mov    #1,r5
    mov    #24,r2           ; key config: throttle mask at +0x18
    add    r13,r2
    mov.w  @r2,r2
    tst    r1,r2
    bt     release
    mov.w  flag_field,r2
    mov.l  r5,@(r0,r2)      ; pressed
    add    #4,r2            ; +0x88 raw
    mov.l  @(r0,r2),r4
    mov.w  full,r8
    cmp/gt r8,r4
    bt     store
    add    #7,r4
    mov.w  jump_at,r3
    cmp/gt r4,r3
    bt     store
    mov    r8,r4            ; reached 160: full
store:
    rts
    mov.l  r4,@(r0,r2)
release:
    mov.w  raw_field,r3
    mov.l  @(r0,r3),r4
    mov.w  slow_above,r2
    cmp/gt r4,r2
    bt     fast
    mov.l  phase_at,r6      ; slow phase: -1 on two ticks of three
    mov.b  @r6,r7
    add    #1,r7
    mov    #3,r2
    cmp/ge r2,r7
    bf     count
    mov    #0,r7
count:
    mov.b  r7,@r6
    tst    r7,r7
    bt     done
    bra    done
    add    #-1,r4
fast:
    mov.w  k24,r2
    muls.w r4,r2
    sts    macl,r6
    shlr16 r6               ; raw / 24
    sub    r6,r4
    mov    #111,r6
    cmp/ge r6,r4
    bt     done
    mov    #56,r4
done:
    mov.l  r4,@(r0,r3)
    mov    #0,r7
    mov.w  flag_field,r2
    rts
    mov.l  r7,@(r0,r2)      ; released
flag_field:
    .word  0x0084
raw_field:
    .word  0x0088
full:
    .word  0x00B8
jump_at:
    .word  0x00A0
slow_above:
    .word  0x00B0
k24:
    .word  0x0AAB           ; 65536 / 24
.align 4
phase_at:
    .long  phase
phase:
    .word  0
    .word  0

; All controller paths call the throttle function through the literal at
; 06036DEC, which patches/steer_hold.s points at the input hold; the hold
; jumps here.
