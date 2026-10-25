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
; Runs for player 1, whose car uses PLCAR01 (two-player below), every tick
; whatever the camera, as DUSA runs it in its car tick: the race loop's
; call to player 1's car effects (06037E28, from 0602831A, in races and the
; attract) goes through reflect_tick. The rolling start, the attract and the
; in-car views don't use the chase camera, so with it there the window
; stood still until the chase took over. In: r9 = player, r12 = car; keeps
; r0, uses r1-r6.
; Caves: after patches/rotation_clamp.s in the unreferenced 0603C304
; function; reflect_tick in the unreferenced function at 0603C796, before
; its literals (0603C7E0, which 0603C5CC reads).

.org 06028350
    .long  reflect_tick     ; was 06037E28

.org 0603C796
reflect_tick:
    sts.l  pr,@-r15
    mov.l  r9,@-r15
    mov.l  r12,@-r15
    mov.l  effects_at,r0
    jsr    @r0              ; r4 = player as the caller set it
    nop
    mov.l  mode_at,r0
    mov.b  @r0,r0
    cmp/eq #2,r0
    bt     tick_done        ; two-player: reflect_2p, from its chase camera
    mov    #0,r9
    mov.l  p1_at,r12
    bsr    reflect
    nop
tick_done:
    mov.l  @r15+,r12
    mov.l  @r15+,r9
    lds.l  @r15+,pr
    rts
    nop
.align 4
effects_at:
    .long  0x06037E28
mode_at:
    .long  0x002FC233       ; 2 in two-player races
p1_at:
    .long  0x0605224C

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

; Two-player: PLCAR21 has no room for the strip, but its window texture
; holds the whole 40-row image as loaded (the strip is that image twice), so
; the same state picks the same start and the texture is rotated in place
; by the change of start, in passes of at most 256 bytes through a buffer.
; The state (V3, H3, previous heading, start) and the buffer live in the
; spare end of that player's PLCAR21.MDL in RAM, zero as loaded. From the
; two-player chase (patches/camera.s): r9 = player, r12 = car; keeps r0,
; uses r1-r7.
.org 0603CAD4
reflect_2p:
    mov.l  r0,@-r15
    mov.l  r7,@-r15
    sts.l  pr,@-r15
    extu.b r9,r0
    shll2  r0
    shll2  r0
    shll   r0               ; player x 32
    mov.l  models_at,r1
    mov.l  @(r0,r1),r1      ; that player's undamaged model header
    mov.l  @(12,r1),r3      ; its offset back to the texture table
    add    r3,r1            ; PLCAR21.MDL as loaded
    mov.w  spare_off,r5
    add    r1,r5            ; the state, then the buffer
    mov.w  srca_2p,r0
    mov.w  @(r0,r1),r7
    extu.w r7,r7
    shll2  r7
    shll   r7
    mov.l  vram_2p,r1
    add    r1,r7            ; the window texture
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
    mov.w  v_wrap_2p,r3
    cmp/hi r3,r2
    bf     v_ok_2p
    sub    r3,r2
v_ok_2p:
    mov.l  r2,@r5           ; V3
    mov.l  @(60,r12),r1     ; heading
    mov.l  @(8,r5),r3
    mov.l  r1,@(8,r5)
    sub    r1,r3
    exts.w r3,r3            ; previous - heading
    mov.l  @(4,r5),r4
    cmp/pl r3
    bf     h_not_up_2p
    bra    h_wrap_2p
    add    #4,r4
h_not_up_2p:
    cmp/pz r3
    bt     h_wrap_2p
    add    #-4,r4
h_wrap_2p:
    mov.w  h_limit_2p,r1
    cmp/hi r1,r4
    bf     h_ok_2p
    mov    #0,r4
h_ok_2p:
    mov.l  r4,@(4,r5)       ; H3
    mov.w  twelfth_2p,r1
    muls.w r1,r2
    sts    macl,r2
    shlr16 r2               ; V3 / 12
    mov    r2,r1
    shll2  r2
    add    r1,r2
    shll2  r2
    shll2  r2               ; x 80
    mov.w  sixth_2p,r1
    muls.w r1,r4
    sts    macl,r4
    shlr16 r4
    add    r4,r2            ; start
    mov.w  size_2p,r1
    cmp/hs r1,r2
    bf     start_ok
    sub    r1,r2
start_ok:
    mov.l  @(12,r5),r3
    mov.l  r2,@(12,r5)
    sub    r3,r2            ; d = new start - old
    cmp/pz r2
    bt     d_ok
    add    r1,r2
d_ok:
    tst    r2,r2
    bt     done_2p
    add    #16,r5           ; the buffer
    mov.w  half_2p,r3
    cmp/hi r3,r2
    bt     right
    mov    r2,r6            ; rotate left by d
left_pass:
    mov    r6,r4
    mov.w  chunk_2p,r3
    cmp/hi r3,r4
    bf     left_k
    mov    r3,r4            ; k: at most 256
left_k:
    mov    r7,r1            ; buffer = W[0, k)
    mov    r5,r2
    bsr    copy_2p
    mov    r4,r3
    mov    r7,r1            ; W[0, 1600 - k) = W[k, 1600)
    add    r4,r1
    mov    r7,r2
    mov.w  size_2p,r3
    bsr    copy_2p
    sub    r4,r3
    mov    r5,r1            ; W[1600 - k, 1600) = buffer
    bsr    copy_2p
    mov    r4,r3
    sub    r4,r6
    tst    r6,r6
    bf     left_pass
    bra    done_2p
    nop
right:
    mov.w  size_2p,r6
    sub    r2,r6            ; rotate right by 1600 - d
right_pass:
    mov    r6,r4
    mov.w  chunk_2p,r3
    cmp/hi r3,r4
    bf     right_k
    mov    r3,r4
right_k:
    mov.w  size_2p,r1       ; buffer = W[1600 - k, 1600)
    sub    r4,r1
    add    r7,r1
    mov    r5,r2
    bsr    copy_2p
    mov    r4,r3
    mov.w  size_2p,r3       ; W[k, 1600) = W[0, 1600 - k), from the end down
    sub    r4,r3
    mov    r7,r1
    add    r3,r1
    mov.w  size_2p,r2
    add    r7,r2
down:
    add    #-1,r1
    mov.b  @r1,r0
    add    #-1,r2
    dt     r3
    bf/s   down
    mov.b  r0,@r2
    mov    r5,r1            ; W[0, k) = buffer
    mov    r7,r2
    bsr    copy_2p
    mov    r4,r3
    sub    r4,r6
    tst    r6,r6
    bf     right_pass
done_2p:
    lds.l  @r15+,pr
    mov.l  @r15+,r7
    rts
    mov.l  @r15+,r0
copy_2p:                    ; r3 bytes from r1 to r2 (at least 1)
    mov.b  @r1+,r0
    mov.b  r0,@r2
    dt     r3
    bf/s   copy_2p
    add    #1,r2
    rts
    nop
v_wrap_2p:
    .word  240
h_limit_2p:
    .word  480
twelfth_2p:
    .word  0x1556
sixth_2p:
    .word  0x2AAB
size_2p:
    .word  1600
half_2p:
    .word  800
chunk_2p:
    .word  256
spare_off:
    .word  0x0BA0           ; after the body's 2956 bytes, before the trailer
srca_2p:
    .word  0x018C           ; texture table +8 + 48 x 8, entry +4
.align 4
models_at:
    .long  0x06056578       ; per player, 8 model header pointers
vram_2p:
    .long  0x25C00000
