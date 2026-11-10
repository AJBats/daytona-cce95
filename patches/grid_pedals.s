; Throttle and brake on the grid, DUSA's at 30 Hz (CCE 06037592 /
; 060375F6; DUSA 06030380). Patch 28.
; Assembled into patches/grid_pedals.patch by tools/mkpatch.py.
;
; While the cars wait on the grid (car mode 9) both games step the d-pad's
; pedals with their own grid code, and rev the engine from the throttle
; pedal: rpm = 32 x pedal (CCE 06039952, DUSA 0600C302). The pedal at the
; last grid tick decides the start, with the same thresholds in both games
; and CCE's timers converted (27 ticks, DUSA's 18):
;   pedal 230 or more (7360 rpm): the start bogs for 0.9 s
;   (CCE +0x18A, DUSA +0x172);
;   brake 140 or more with the pedal over 155: the fast start for 0.9 s
;   (CCE +0x18C, DUSA +0x174).
; Raw values rest at 56; throttle pedal = (raw - 56) x 255 / 128.
;   throttle pressed: DUSA +4 per 20 Hz tick while <= 184 (to 188);
;                     CCE +8 per 30 Hz tick, clamped at 184.
;   released:         DUSA -2, CCE -4, both down to 56.
;   brake pressed:    DUSA +5 while <= 184 (to 189); CCE +10, clamped.
;   released:         -5 in both.
; So CCE's revs and brake moved 3x as fast. Its fast start needed the gas
; pressed 0.33-0.48 s before GO; DUSA's takes it 1.0-1.43 s before, and
; gas held longer bogs both.
; 30 Hz: throttle +3, +3, +2 and -1, -1, -2; brake +3, +3, +4 and -3, -3,
; -4 (each function keeps its own three-tick phase). No clamp, as in DUSA:
; CCE's pedal stays at 255 above raw 184.
;
; Both functions are rewritten in their own space, 06037592-06037653; the
; brake's callers (literals 06036EFC, 06036F30) follow it. The original
; throttle also left car +0x17C in r9, which its caller (06037484) saves
; and restores unread.

.org 06036EFC
    .long  grid_brake           ; was 060375F6
.org 06036F30
    .long  grid_brake           ; was 060375F6

.org 06037592
grid_throttle:                  ; r0 = car, r13 = key config
    mov.l  @(4,r13),r1
    mov.w  @r1,r1
    extu.w r1,r1                ; the pad word, left for grid_brake
    mov.l  phases,r6            ; the throttle's phase: 2, 1, 0
    mov.w  @r6,r7
    add    #-1,r7
    cmp/pz r7
    bt     t_phase
    mov    #2,r7
t_phase:
    mov.w  r7,@r6
    mov    #24,r2               ; key config: the throttle's mask at +0x18
    add    r13,r2
    mov.w  @r2,r2
    mov.w  raw_throttle,r3
    mov.l  @(r0,r3),r4
    tst    r1,r2
    bt     t_released
    mov.w  full,r8
    cmp/gt r8,r4                ; steps only while <= 184
    bt     t_pressed
    add    #3,r4
    tst    r7,r7
    bf     t_pressed
    add    #-1,r4               ; +3, +3, +2: DUSA's +4 a tick
t_pressed:
    bra    t_store
    mov    #1,r5
t_released:
    add    #-1,r4
    tst    r7,r7
    bf     t_floor
    add    #-1,r4               ; -1, -1, -2: DUSA's -2 a tick
t_floor:
    mov    #56,r5
    cmp/gt r5,r4
    bt     t_up
    mov    r5,r4
t_up:
    mov    #0,r5
t_store:
    mov.w  pressed_throttle,r2
    mov.l  r5,@(r0,r2)
    rts
    mov.l  r4,@(r0,r3)

grid_brake:                     ; r0 = car, r1 = pad word, r13 = key config
    mov.l  phases,r6
    add    #2,r6                ; the brake's phase
    mov.w  @r6,r7
    add    #-1,r7
    cmp/pz r7
    bt     b_phase
    mov    #2,r7
b_phase:
    mov.w  r7,@r6
    mov    #26,r2               ; key config: the brake's mask at +0x1A
    add    r13,r2
    mov.w  @r2,r2
    mov.w  raw_brake,r3
    mov.l  @(r0,r3),r4
    tst    r1,r2
    bt     b_released
    mov.w  full,r8
    cmp/gt r8,r4
    bt     b_pressed
    add    #3,r4
    tst    r7,r7
    bf     b_pressed
    add    #1,r4                ; +3, +3, +4: DUSA's +5 a tick
b_pressed:
    bra    b_store
    mov    #1,r5
b_released:
    add    #-3,r4
    tst    r7,r7
    bf     b_floor
    add    #-1,r4               ; -3, -3, -4: DUSA's -5 a tick
b_floor:
    mov    #56,r5
    cmp/ge r5,r4
    bt     b_up
    mov    r5,r4
b_up:
    mov    #0,r5
b_store:
    mov.w  pressed_brake,r2
    mov.l  r5,@(r0,r2)
    rts
    mov.l  r4,@(r0,r3)

raw_throttle:
    .word  0x0088
pressed_throttle:
    .word  0x0084
raw_brake:
    .word  0x0098
pressed_brake:
    .word  0x0094
full:
    .word  0x00B8
.align 4
phases:
    .long  phase_words
phase_words:
    .word  0                    ; throttle
    .word  0                    ; brake
