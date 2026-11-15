; Rear and side window reflection DUSA's way (DUSA 0601BDEC, 06006F3C), at
; 30 Hz. Assembled into patches/reflection.patch by tools/mkpatch.py.
;
; DUSA draws the windows with one 80x40 texture and re-uploads it every frame
; from an 80-row sky strip in work RAM (a 40-row image stored twice, 40 bytes
; a row), starting at byte (V/4) x 80 + H/2: two rows per V/4 step, so the
; window scrolls through the whole image before V wraps, and H carries on
; into the next rows. Its car tick only moves the scroll (0601BDEC), per
; 20 Hz tick:
;   V += km/h / 32 + 1, and V -= 80 once V > 80 (unsigned)
;   H += 2 while the heading decreases, -= 2 while it increases;
;   H = 0 once H > 0xA0 (unsigned)
; and the frame's end flags the upload (060079A6, bit 0x20000000 of
; 0605B6D8); its VBlank-IN handler (06006F3C, installed at 06004B2C) works
; out the start and DMAs the 1600 bytes into the texture (06007058, through
; 0602766C, SCU level 0), between frames, when VDP1 isn't drawing. A CPU
; that touches VDP1's VRAM while it draws slows the drawing.
; tools/car_convert.py puts the strip in PLCAR09.MDL (+0x156C) and gives the
; window texture table entry 48, which the loader points at VRAM.
; 30 Hz: the state is kept x3, V3 += 2 x (km/h / 32 + 1) wrapping at 240,
; H3 +-4 reset past 480; start byte (V3 / 12) x 80 + H3 / 6, less 1600 when
; it reaches the second copy (the same pixels), so the copy never runs past
; the strip as DUSA's can at the top of the range.
;
; Runs for player 1 when the car is DUSA's (PLCAR09: the secret car, or
; the Hornet with DUSA's car chosen, patches/car_choice.s; any other car's
; texture 48 is its own, and copying the strip over it scrambled it), every tick
; whatever the camera, as DUSA runs it in its car tick: the race loop's
; call to player 1's car effects (06037E28, from 0602831A, in races and the
; attract) goes through reflect_tick. The upload goes into slot 0 of the
; race block's window slots (src/race_block.s, 06018710: source, window,
; bytes), which its win_upload DMAs at the race's list copy in VBlank-IN
; (patches/vdp1x.s). Without the block (the attract before the first race:
; CCE's loader copies SCREEN.BIN's blocks in at a race start) the tick
; copies the window itself, as before. The race block's first byte, 0x52,
; tells; before the first race those bytes are the main program's zeros.
; Caves: after patches/rotation_clamp.s in the unreferenced 0603C304
; function; reflect_tick and the scroll state in the unreferenced function
; at 0603C796, before its literals (0603C7E0, which 0603C5CC reads).

.org 06028350
    .long  reflect_tick     ; was 06037E28

.org 0603C796
reflect_tick:
    sts.l  pr,@-r15
    mov.l  effects_at,r0
    jsr    @r0              ; r4 = player as the caller set it
    nop
    mov.l  mode_at,r0
    mov.b  @r0,r0
    cmp/eq #2,r0
    bt     tick_out         ; two-player: reflect_2p, from its chase camera
    mov.l  is_dusa_at,r0
    jsr    @r0
    mov    #0,r1            ; DUSA's car has DUSA's window; others keep theirs
    bf     tick_out
    lds.l  @r15+,pr
    bra    reflect
    nop
tick_out:
    lds.l  @r15+,pr
    rts
    nop
.align 4
effects_at:
    .long  0x06037E28
mode_at:
    .long  0x002FC233       ; 2 in two-player races
is_dusa_at:
    .long  0x060334FC       ; patches/car_choice.s: T = player r1's car is DUSA's
state:
    .long  0                ; V3
    .long  0                ; H3
    .long  0                ; previous heading

.org 0603C4D8
reflect:
    mov.l  p1_at,r7
    mov.l  state_at,r5
    mov.l  @(52,r7),r1      ; km/h
    shar   r1
    shar   r1
    shar   r1
    shar   r1
    shar   r1
    add    #1,r1
    add    r1,r1
    mov.l  @r5,r2
    add    r1,r2
    mov.w  v_wrap,r6
    cmp/hi r6,r2
    bf     v_ok
    sub    r6,r2
v_ok:
    mov.l  r2,@r5           ; V3
    mov.l  @(60,r7),r1      ; heading
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
    add    r6,r6            ; 480
    cmp/hi r6,r4
    bf     h_ok
    mov    #0,r4
h_ok:
    mov.l  r4,@(4,r5)       ; H3
    mov.w  twelfth,r1
    muls.w r1,r2
    sts    macl,r2
    add    r1,r1            ; a sixth: floor(x / 6) for these x as well
    muls.w r1,r4
    shlr16 r2               ; V3 / 12
    sts    macl,r4
    shlr16 r4               ; H3 / 6
    mov    r2,r1
    shll2  r2
    add    r1,r2
    shll2  r2
    shll2  r2               ; x 80
    add    r4,r2            ; strip offset
    mov.w  size,r6
    cmp/hs r6,r2
    bf     in_strip
    sub    r6,r2
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
    mov.l  block_at,r1
    mov.b  @r1,r0
    cmp/eq #0x52,r0
    bf     copy             ; no race block: copied now
    mov.l  r3,@(16,r1)      ; slot 0: the source,
    mov.l  r4,@(20,r1)      ; the window,
    rts
    mov.l  r6,@(24,r1)      ; 1600 bytes (last: the slot is whole once it counts)
copy:
    mov.b  @r3+,r1
    mov.b  r1,@r4
    dt     r6
    bf/s   copy
    add    #1,r4
out:
    rts
    nop
v_wrap:
    .word  240
twelfth:
    .word  0x1556           ; 65536 / 12 rounded up: floor(x / 12) for these x
strip_off:
    .word  0x156C
srca_off:
    .word  0x018C           ; texture table +8 + 48 x 8, entry +4
size:
    .word  1600             ; 80 x 40, 4bpp
.align 4
p1_at:
    .long  0x0605224C
state_at:
    .long  state
model_at:
    .long  0x0605666C       ; PLCAR09.MDL as loaded
vram:
    .long  0x25C00000       ; VDP1 VRAM
block_at:
    .long  0x06018700       ; src/race_block.s

; Two-player: the routine is in the race block (src/race_block.s,
; tools/race_block.py: at 06018700, its entry right after the magic word),
; so this cave holds patches/camera.s's replay selectors and the BGM tables.
; From the two-player chase (patches/camera.s): r9 = player, r12 = car;
; keeps r0. The block's loader copies it in at every race start, not in the
; attract; without its magic word, no reflection this tick. In the
; unreferenced function at 0603C994, after patches/livery.s.
.org 0603CAD4
reflect_2p:
    mov.l  block_2p_at,r1
    mov.w  @r1+,r2          ; the magic word; r1 the reflection's entry after it
    mov.w  magic_2p,r3
    cmp/eq r3,r2
    bf     no_block_2p
    jmp    @r1
    nop
no_block_2p:
    rts
    nop
magic_2p:
    .word  0x5232
.align 4
block_2p_at:
    .long  0x06018700
