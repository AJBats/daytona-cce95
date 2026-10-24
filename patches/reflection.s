; Rear and side window reflection DUSA's way (DUSA 0601BDEC, 0600705E), at
; 30 Hz. Assembled into patches/reflection.patch by tools/mkpatch.py.
;
; DUSA draws the windows with one 80x40 texture and re-uploads it every car
; tick from an 80-row sky strip (a 40-row image stored twice, 40 bytes a
; row), starting at byte (V/4) x 80 + H/2: two rows per V/4 step, so the
; window scrolls through the whole image before V wraps, and H carries on
; into the next rows. Per 20 Hz tick:
;   V += km/h / 32 + 1, and V -= 80 once V > 80 (unsigned)
;   H += 2 while the heading decreases, -= 2 while it increases;
;   H = 0 once H > 0xA0 (unsigned)
; tools/car_convert.py puts the strip in PLCAR01.MDL (+0x156C) and gives the
; window texture table entry 48, which the loader points at VRAM.
; 30 Hz: the state is kept x3, V3 += 2 x (km/h / 32 + 1) wrapping at 240,
; H3 +-4 reset past 480; start byte (V3 / 12) x 80 + H3 / 6, less 1600 when
; it reaches the second copy (the same pixels), so the copy never runs past
; the strip as DUSA's can at the top of the range.
;
; Runs at the end of the chase camera routine (patches/camera.s, views 2
; and 3) for player 1, whose car uses PLCAR01. In: r9 = player, r12 = car;
; keeps r0 (camera yaw), uses r1-r6.
; Cave: after patches/rotation_clamp.s in the unreferenced 0603C304 function.

.org 0603C4D8
reflect:
    mov.l  r0,@-r15
    extu.b r9,r0
    tst    r0,r0
    bf     out
    mov.l  state_at,r5
    mov.l  @(52,r12),r1     ; km/h
    shar   r1
    shar   r1
    shar   r1
    shar   r1
    shar   r1
    add    #1,r1
    add    r1,r1
    mov.l  @r5,r2
    add    r1,r2
    mov.w  v_wrap,r3
    cmp/hi r3,r2
    bf     v_ok
    sub    r3,r2
v_ok:
    mov.l  r2,@r5           ; V3
    mov.l  @(60,r12),r1     ; heading
    mov.l  @(8,r5),r3
    mov.l  r1,@(8,r5)
    sub    r1,r3
    exts.w r3,r3            ; previous - heading
    mov.l  @(4,r5),r4
    cmp/pl r3
    bf     h_not_up
    bra    h_wrap
    add    #4,r4
h_not_up:
    cmp/pz r3
    bt     h_wrap
    add    #-4,r4
h_wrap:
    mov.w  h_limit,r1
    cmp/hi r1,r4
    bf     h_ok
    mov    #0,r4
h_ok:
    mov.l  r4,@(4,r5)       ; H3
    mov.w  twelfth,r1
    muls.w r1,r2
    sts    macl,r2
    shlr16 r2               ; V3 / 12
    mov    r2,r1
    shll2  r2
    add    r1,r2
    shll2  r2
    shll2  r2               ; x 80
    mov.w  sixth,r1
    muls.w r1,r4
    sts    macl,r4
    shlr16 r4
    add    r4,r2            ; strip offset
    mov.w  size,r1
    cmp/hs r1,r2
    bf     in_strip
    sub    r1,r2
in_strip:
    mov.l  model_at,r1
    mov.l  @r1,r1
    tst    r1,r1
    bt     out
    mov.w  strip_off,r3
    add    r1,r3
    add    r2,r3            ; source
    mov.w  srca_off,r0
    mov.w  @(r0,r1),r4
    extu.w r4,r4
    shll2  r4
    shll   r4
    mov.l  vram,r1
    add    r1,r4            ; window texture
    mov.w  size,r6
copy:
    mov.b  @r3+,r1
    mov.b  r1,@r4
    dt     r6
    bf/s   copy
    add    #1,r4
out:
    rts
    mov.l  @r15+,r0
v_wrap:
    .word  240
h_limit:
    .word  480
twelfth:
    .word  0x1556           ; 65536 / 12 rounded up: floor(x / 12) for these x
sixth:
    .word  0x2AAB           ; 65536 / 6 rounded up
strip_off:
    .word  0x156C
srca_off:
    .word  0x018C           ; texture table +8 + 48 x 8, entry +4
size:
    .word  1600             ; 80 x 40, 4bpp
.align 4
state_at:
    .long  state
model_at:
    .long  0x0605666C       ; PLCAR01.MDL as loaded
vram:
    .long  0x25C00000       ; VDP1 VRAM
state:
    .long  0                ; V3
    .long  0                ; H3
    .long  0                ; previous heading
