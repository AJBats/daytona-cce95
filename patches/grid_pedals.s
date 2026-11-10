; Throttle and brake on the grid, DUSA's at 30 Hz (CCE 06037592 /
; 060375F6, analog 0603740E / 06037442; DUSA 06030380). Patch 28.
; Assembled into patches/grid_pedals.patch by tools/mkpatch.py.
;
; While the cars wait on the grid (car mode 9) both games step the pedals
; with their own grid code, and rev the engine from the throttle pedal:
; rpm = 32 x pedal (CCE 06039952, DUSA 0600C302). The pedals at the last
; grid tick decide the start, with the same thresholds in both games and
; CCE's timers converted (27 ticks, DUSA's 18):
;   pedal 230 or more (7360 rpm): the start bogs for 0.9 s
;   (CCE +0x18A, DUSA +0x172);
;   brake 140 or more with the pedal over 155: the fast start for 0.9 s
;   (CCE +0x18C, DUSA +0x174).
; Raw values rest at 56; throttle pedal = (raw - 56) x 255 / 128.
;   throttle pressed: DUSA +4 per 20 Hz tick while <= 184 (to 188);
;                     CCE +8 per 30 Hz tick, clamped at 184.
;   released:         DUSA -2, CCE -4, both down to 56.
;   brake pressed:    DUSA +5 while <= 184 (to 186); CCE +10, clamped.
;   released:         -5 in both.
; So CCE's revs and brake moved 3x as fast. Its fast start needed the gas
; pressed 0.33-0.48 s before GO; DUSA's takes it 1.0-1.43 s before, and
; gas held longer bogs both.
; DUSA has no analog pedals (the Arcade Racer's are buttons). CCE's
; analog triggers set the raw value at once (throttle trigger / 2 + 56,
; brake trigger / 2 + 88 when pressed) and, for pad type 2, chase rpm at
; +-400 a tick: 2.3x DUSA's revs.
;
; Here every pedal moves toward a target at DUSA's rates at 30 Hz: up
; +3, +3, +2 (throttle) or +3, +3, +4 (brake), down -1, -1, -2 or -3, -3,
; -4, each pedal with its own three-tick phase. Buttons aim at DUSA's
; highest values (188, 186) or 56; a trigger aims at CCE's value for it,
; so a full trigger revs exactly as DUSA's button does and a part trigger
; holds part revs. CCE's pedal stays 255 above raw 184.
;
; The grid functions are rewritten in their own space, 06037592-06037653;
; the callers' literals (06036EFC, 06036F30 brake, 06036F2C, 06036F68
; analog) follow them. Racing keeps its own pedal functions. Register use
; as the originals: r0 = car, r1 = pad word (grid_throttle leaves it for
; grid_brake), r13 = key config; r8-r11 are saved by the input step
; 06037484, which also restores the r9 the original throttle left.

.org 06036EFC
    .long  grid_brake           ; was 060375F6
.org 06036F2C
    .long  grid_athrottle       ; was 0603740E
.org 06036F30
    .long  grid_brake           ; was 060375F6
.org 06036F68
    .long  grid_abrake          ; was 06037442

.org 06037592
grid_throttle:                  ; the button
    mov.l  @(4,r13),r1
    mov.w  @r1,r1               ; the pad word (sign-extended, as the masks)
    mov    #24,r2               ; key config: the throttle's mask at +0x18
    add    r13,r2
    mov.w  @r2,r2
    mov    #56,r4
    tst    r1,r2
    bt/s   t_common
    mov    #0,r5
    mov.w  t_top,r4
    mov    #1,r5
t_common:                       ; r4 = target, r5 = pressed
    mov.w  raw_throttle,r3
    mov.l  phases,r6
    mov    #3,r8
    mov    #-1,r9
    bra    step
    mov    #1,r10

grid_athrottle:                 ; the analog trigger
    mov.l  @(12,r13),r2
    mov.b  @r2,r2
    extu.b r2,r2
    shlr   r2
    cmp/pl r2
    movt   r5
    mov    #56,r4
    bra    t_common
    add    r2,r4

grid_brake:                     ; the button; r1 = pad word
    mov    #26,r2               ; key config: the brake's mask at +0x1A
    add    r13,r2
    mov.w  @r2,r2
    mov    #56,r4
    tst    r1,r2
    bt/s   b_common
    mov    #0,r5
    mov.w  b_top,r4
    mov    #1,r5
b_common:
    mov.w  raw_brake,r3
    mov.l  phases,r6
    add    #2,r6
    mov    #3,r8
    mov    #1,r9
    bra    step
    mov    #3,r10

grid_abrake:                    ; the analog trigger
    mov.l  @(16,r13),r2
    mov.b  @r2,r2
    extu.b r2,r2
    shlr   r2
    mov    #56,r4
    cmp/pl r2
    bf/s   b_common
    movt   r5
    add    #32,r2
    bra    b_common
    add    r2,r4

step:   ; r3 = raw field, r4 = target, r5 = pressed, r6 = phase word,
        ; r8 = step up, r9 = its change on phase 0, r10 = step down
    mov.w  @r6,r7
    add    #-1,r7
    cmp/pz r7
    bt     s_phase
    mov    #2,r7
s_phase:
    mov.w  r7,@r6               ; 2, 1, 0
    mov    r3,r2
    add    #-4,r2
    mov.l  r5,@(r0,r2)          ; pressed flag, the field before raw
    mov.l  @(r0,r3),r11
    mov    #56,r2
    cmp/ge r2,r11
    bt     s_rest
    mov    r2,r11               ; below rest (CCE's car init leaves 0): rest,
s_rest:                         ; as DUSA's release floors it
    cmp/gt r11,r4
    bt     s_up
    cmp/gt r4,r11
    bf     s_store
    sub    r10,r11
    tst    r7,r7
    bf     s_down
    add    #-1,r11
s_down:
    cmp/gt r11,r4
    bf     s_store
    bra    s_store
    mov    r4,r11
s_up:
    add    r8,r11
    tst    r7,r7
    bf     s_upped
    add    r9,r11
s_upped:
    cmp/gt r4,r11
    bf     s_store
    mov    r4,r11
s_store:
    rts
    mov.l  r11,@(r0,r3)

t_top:
    .word  188
b_top:
    .word  186
raw_throttle:
    .word  0x0088
raw_brake:
    .word  0x0098
.align 4
phases:
    .long  phase_words
phase_words:
    .word  0                    ; throttle
    .word  0                    ; brake
