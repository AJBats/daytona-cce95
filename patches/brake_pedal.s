; Brake pedal, DUSA's at 30 Hz (CCE brake input 0603704A and pedal scaling
; in 0604D580; DUSA 0602FED0 / 0602FF0C and 0602EFF0).
; Assembled into patches/brake_pedal.patch by tools/sh2asm.py.
;
; Raw brake value (CCE +0x98, DUSA +0x90) rests at 56.
;   pressed:  DUSA +40 per 20 Hz tick while <= 184, no clamp (overshoots to
;             216); CCE +32 per 30 Hz tick, clamped at 184.
;   released: both halve per tick, floor 56.
;   pedal:    DUSA (raw - 56) x 255 / 96, raw clamped to 152;
;             CCE  (raw - 56) x 255 / 128, raw clamped to 184.
; DUSA's pedal: 0 -> 106 -> 212 -> 255 on press, 255 -> 138 -> 0 on release.
; 30 Hz: +40 x 2/3 = +27 per tick, DUSA's overshoot, DUSA's scaling (levels,
; unchanged), and on release keep (1/2)^(2/3) = 0.63 per tick (here 5/8).
; The release block is rewritten in place (same length) using GBR = car.

.org 06037064
    add    #27,r4           ; was +32

.org 0603706A
    nop                     ; was mov r8,r4: DUSA doesn't clamp at 184

.org 06037080
    mov.l  @(152,gbr),r0    ; raw (+0x98)
    mov    r0,r2
    shlr2  r2
    sub    r2,r0            ; - 1/4
    shlr   r2
    sub    r2,r0            ; - 1/8: keep 5/8
    mov    #56,r3
    cmp/ge r3,r0
    bt     floor_ok
    mov    r3,r0
floor_ok:
    mov.l  r0,@(152,gbr)
    mov    #0,r0
    mov.l  r0,@(148,gbr)    ; +0x94 = 0 (released), as before
    stc    gbr,r0           ; callers expect r0 = car

.org 0604D688
    .long  0x00000098       ; pedal: raw clamp 184 -> 152

.org 0604D6D8
    .word  0x0060           ; pedal: / 128 -> / 96
