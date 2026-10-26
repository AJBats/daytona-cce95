; DUSA's title in CCE's attract (docs/attract.md). Assembled into
; patches/title.patch by tools/mkpatch.py.
;
; CCE: the attract demo (06031DFA, a tick every 2 frames) counts ticks in
; 060520D6. At 0x906 it calls 0602F564, which crossfades its CIRCUIT
; EDITION title in over the demo in hi-res; 0602F65C then makes it a still
; title (and 06051619 = 1 stops the race drawing), and 0602F7C0 blinks its
; Press Start Button every tick. Start returns 2 (a fade to black, then the
; main menu), the timeout at 0xAC8 returns 1 (a fade, then the logos).
;
; DUSA, frames from its first slide frame (t = 0): four black frames, then
; the white striped background with a pale ghost of the logo (NBG2) and the
; black logo (NBG3) sliding in from the left 16 pixels a frame (X scroll
; 336 at t = 0 to 0 at t = 21), the shake (-8, 8, -4, 4, -2, 2, -1, 1 at
; t = 23-30, then -1 on odd frames to t = 61), PRESS START BUTTON (NBG3
; rows 23-24) blinking 4 frames on, 4 off from t = 64, and a cut to black
; at t = 600. Its demo runs 2760 frames from the cut-in to the first black
; frame.
;
; Here the demo ends after DUSA's 46 s (the title at tick 1407, its first
; black frame 2760 frames after patches/attract.s's cut), and CCE's three
; title routines are replaced in place: title_start (0602F564) sets DUSA's
; title up, the VBlank-IN interrupt runs it a frame at a time (its vector at
; 06000100 points at title_vbl while the title is up; the attract runs at
; 30 Hz), and title_tick (0602F7C0) ends it at t = 600 as CCE's timeout.
; Start, or the timeout, fades to black (CCE's colour offset fade, which
; takes NBG2 and NBG3 too); title_leave then gives the vector back from the
; race's teardown, before the next screen loads over RACE.BIN. The graphics come from
; tools/title_convert.py through DEMOTTL.BIN: chars, background map and
; logo map staged in VRAM at 0x40040 and palettes 48-63 in CRAM, where CCE
; kept its title. title_start copies the chars to VRAM 0, the background
; map to 0x5E000 and the logo map to 0x7C000, as DUSA's banks, and sets
; VDP2 as DUSA's title but for NBG3's plane, 2 pages wide (0x7E000 blank) so
; the logo comes in from the left without wrapping round.

.org 06031EB6
    .word  1407             ; the title's tick, was 0x906 (77 s)
.org 06031EBA
    .word  1742             ; CCE's timeout, was 0xAC8; title_tick ends first
.org 06028E6C
    .long  title_leave      ; was 0602E732, in the race's teardown

.org 0602F564
title_start:
    sts.l  pr,@-r15
    mov.l  tvmd_at,r1
wait_vblank:
    mov.w  @(4,r1),r0       ; TVSTAT
    tst    #8,r0
    bt     wait_vblank      ; the demo's last frame whole
    mov.w  @r1,r0
    mov.w  k_7fff,r2
    and    r2,r0
    mov.w  r0,@r1           ; display off
    mov.l  stage_at,r4
    mov.l  chars_to,r5
    mov.w  n_chars,r6
    bsr    copy
    nop
    mov.l  bg_to,r5
    mov.w  n_map,r6
    bsr    copy
    nop
    mov.l  logo_to,r5
    mov.w  n_map,r6
    bsr    copy
    nop
    mov.l  page1_to,r5      ; NBG3's second page blank
    mov.w  n_map,r6
    mov    #0,r0
blank:
    dt     r6
    mov.l  r0,@r5
    bf/s   blank
    add    #4,r5
    mova   regs,r0
    bsr    set_regs
    mov    r0,r4
    mov.l  xfade_at,r1
    mov    #0,r0
    mov.b  r0,@r1           ; no crossfade: the attract goes straight to its still title
    mov.l  still_at,r1
    mov    #1,r0
    mov.b  r0,@r1           ; the race stops drawing, as for CCE's still title,
    mov.l  vdp1_mode,r1     ; so VDP1 changes frames by itself, as there too
    jsr    @r1
    mov    #0,r4
    mova   vars,r0
    mov    r0,r2
    mov    #-4,r0
    mov.w  r0,@r2           ; t
    mov    #0,r0
    mov.b  r0,@(2,r2)       ; PRESS START hidden
    mov.l  vec_at,r1
    mov.l  @r1,r0
    mov.l  vbl_at,r3
    cmp/eq r3,r0
    bt     hooked
    mov.l  r0,@(4,r2)       ; CCE's VBlank-IN handler, chained to
    mov.l  r3,@r1
hooked:
    lds.l  @r15+,pr
    rts
    nop

copy:
    mov.l  @r4+,r0
    dt     r6
    mov.l  r0,@r5
    bf/s   copy
    add    #4,r5
    rts
    nop

set_regs:                   ; r4: VDP2 (register offset, value) words, -1 ends
    mov.l  tvmd_at,r5
set_reg:
    mov.w  @r4+,r1
    cmp/pz r1
    bf     set_done
    mov.w  @r4+,r2
    mov    r1,r0
    bra    set_reg
    mov.w  r2,@(r0,r5)
set_done:
    rts
    nop

; The race's teardown (its call to 0602E732, made once the fade to black is
; over): the race's values in the registers CCE's own title leaves alone,
; as the screens after it take them as the race left them (the attract's
; opening hides sprites too, src/attract.c); and with the title up, CCE's
; VBlank-IN handler back
title_leave:
    sts.l  pr,@-r15
    mova   race_regs,r0
    bsr    set_regs
    mov    r0,r4
    mov.l  vec_at,r2
    mov.l  @r2,r3
    mov.l  vbl_at,r0
    cmp/eq r0,r3
    bf     leave_done
    mova   vars,r0
    mov.l  @(4,r0),r1
    mov.l  r1,@r2
leave_done:
    mov.l  @r2,r3           ; the demo's frame counter (patches/attract.s):
    mov.l  demo_vbl_at,r0   ; the handler it replaced back
    cmp/eq r0,r3
    bf     leave_out
    mov.l  @(24,r0),r1
    mov.l  r1,@r2
leave_out:
    lds.l  @r15+,pr
    mov.l  teardown_at,r0
    jmp    @r0
    nop
k_7fff:
    .word  0x7FFF
n_chars:
    .word  4800             ; 600 chars, in longs
n_map:
    .word  896              ; 28 rows of 64 cells, in longs

; VBlank-IN: one frame of the title, then CCE's handler
title_vbl:
    mov.l  r0,@-r15
    mov.l  r1,@-r15
    mov.l  r2,@-r15
    mov.l  r3,@-r15
    mov.l  r4,@-r15
    mova   vars,r0
    mov    r0,r4
    mov.w  @r4,r1
    add    #1,r1
    mov.w  r1,@r4           ; t
    cmp/pz r1
    bf     vbl_done         ; black
    mov.l  tvmd_at,r3
    mov.w  @r3,r0
    mov.w  k_8000,r2
    or     r2,r0
    mov.w  r0,@r3           ; display on
    mov    #22,r0
    cmp/ge r0,r1
    bt     vbl_shake
    mov    r1,r2
    shll2  r2
    shll2  r2
    mov.w  k_336,r0
    bra    vbl_x
    sub    r2,r0            ; the slide: 336 - 16 t
vbl_shake:
    mov    #63,r2
    cmp/ge r2,r1
    bt/s   vbl_x
    mov    #0,r0            ; settled
    mov    #31,r2
    cmp/ge r2,r1
    bf     vbl_kick
    mov    r1,r0
    and    #1,r0
    bra    vbl_x
    neg    r0,r0            ; t = 31-61: -1 on odd frames
vbl_kick:
    mova   shake,r0
    mov    r1,r2
    add    #-22,r2
    mov.b  @(r0,r2),r0
vbl_x:
    mov.l  scxn2_at,r3
    mov.w  r0,@(4,r3)       ; NBG3 X
    mov    #0,r0
    mov.w  r0,@r3           ; NBG2 X, Y and NBG3 Y stay 0
    mov.w  r0,@(2,r3)
    mov.w  r0,@(6,r3)
    mov    #64,r0
    cmp/ge r0,r1
    bf     vbl_end
    mov    r1,r0
    add    #-63,r0
    tst    #4,r0
    movt   r2               ; 1: PRESS START shown
    mov.b  @(2,r4),r0
    cmp/eq r2,r0
    bt     vbl_end
    mov    r2,r0
    mov.b  r0,@(2,r4)
    mov.l  ps_cells,r3
    mov.w  ps_first,r0
    tst    r2,r2
    bf     vbl_ps
    mov    #0,r0            ; hidden: blank cells
vbl_ps:
    mov    #22,r4
vbl_row23:
    mov.w  r0,@r3
    add    r2,r0
    dt     r4
    bf/s   vbl_row23
    add    #2,r3
    add    #84,r3           ; row 24, column 11
    mov    #22,r4
vbl_row24:
    mov.w  r0,@r3
    add    r2,r0
    dt     r4
    bf/s   vbl_row24
    add    #2,r3
vbl_end:
    mov.w  k_600,r0
    cmp/eq r0,r1
    bf     vbl_done
    mov.l  clofen_at,r3     ; the cut to black: colour offset -255 on
    mov    #127,r0          ; everything, as the fade engine's current
    mov.w  r0,@r3           ; offset, so CCE's fade out after the timeout
    mov    #0,r0            ; stays black
    mov.w  r0,@(2,r3)
    mov.w  k_m255,r0
    mov.w  r0,@(4,r3)
    mov.w  r0,@(6,r3)
    mov.w  r0,@(8,r3)
    mov.l  fade_cur,r3
    mov.w  r0,@r3
    mov.w  r0,@(2,r3)
    mov.w  r0,@(4,r3)
vbl_done:
    mov.l  @r15+,r4
    mov.l  @r15+,r3
    mov.l  @r15+,r2
    mov.l  @r15+,r1
    mova   vars,r0
    mov.l  @(4,r0),r0
    jmp    @r0
    mov.l  @r15+,r0
.align 4
tvmd_at:
    .long  0x25F80000
stage_at:
    .long  0x25E40040
chars_to:
    .long  0x25E00000
bg_to:
    .long  0x25E5E000
logo_to:
    .long  0x25E7C000
page1_to:
    .long  0x25E7E000
xfade_at:
    .long  0x060520D8
still_at:
    .long  0x06051619
vec_at:
    .long  0x06000100
vbl_at:
    .long  title_vbl
demo_vbl_at:
    .long  0x0603C970       ; patches/attract.s's demo_vbl; its saved handler at +24
scxn2_at:
    .long  0x25F80090
ps_cells:
    .long  0x25E7CB96       ; NBG3 row 23, column 11
clofen_at:
    .long  0x25F80110
fade_cur:
    .long  0x06051F58
vdp1_mode:
    .long  0x06005530
teardown_at:
    .long  0x0602E732
k_8000:
    .word  0x8000
k_336:
    .word  336
ps_first:
    .word  0x522C           ; palette 5, char 556
k_600:
    .word  600
k_m255:
    .word  0xFF01
.align 4
; VDP2 as DUSA's title: NBG2 and NBG3 only, 16-colour 8x8 cells, chars in
; bank A0, maps in B0 (NBG2) and B1 (NBG3), DUSA's VRAM cycle patterns,
; palettes 48-63, no sprites, colour offset on (0) for CCE's fade out. The
; registers left out are already as DUSA's title has them in CCE's race.
regs:
    .word  0x0010           ; CYCA0L-CYCB1U
    .word  0x67FF
    .word  0x0012
    .word  0xFFFF
    .word  0x0014
    .word  0xFFFF
    .word  0x0016
    .word  0xFF45
    .word  0x0018
    .word  0xD012
    .word  0x001A
    .word  0xFFFF
    .word  0x001C
    .word  0xFFF3
    .word  0x001E
    .word  0xFFFF
    .word  0x0020           ; BGON: NBG2, NBG3
    .word  0x000C
    .word  0x0034           ; PNCN2: 1-word names, 12-bit chars, palette + 48
    .word  0xC060
    .word  0x0036           ; PNCN3
    .word  0xC060
    .word  0x003A           ; PLSZ: NBG3 2 x 1 pages
    .word  0x0040
    .word  0x0048           ; MPABN2, MPCDN2: 0x5E000
    .word  0x2F2F
    .word  0x004A
    .word  0x2F2F
    .word  0x004C           ; MPABN3, MPCDN3: 0x7C000
    .word  0x3E3E
    .word  0x004E
    .word  0x3E3E
    .word  0x0094           ; SCXN3
    .word  336
    .word  0x00F0           ; PRISA: sprites hidden
    .word  0x0000
    .word  0x00F8           ; PRINA: NBG0, NBG1 hidden
    .word  0x0000
    .word  0x00FA           ; PRINB: NBG2 6, NBG3 7
    .word  0x0706
    .word  0x0110           ; CLOFEN
    .word  0x007F
    .word  0xFFFF
.align 4
race_regs:
    .word  0x003A           ; PLSZ
    .word  0x0000
    .word  0x0034           ; PNCN2
    .word  0xC044
    .word  0x0048           ; MPABN2, MPCDN2
    .word  0x3535
    .word  0x004A
    .word  0x3535
    .word  0x00F0           ; PRISA
    .word  0x0604
    .word  0xFFFF
.align 4
shake:                      ; NBG3 X at t = 22-30
    .word  0x00F8
    .word  0x08FC
    .word  0x04FE
    .word  0x02FF
    .word  0x0100

.org 0602F7C0
title_tick:
    mova   vars,r0
    mov.w  @r0,r1
    mov.w  k_600b,r2
    cmp/ge r2,r1
    bf     tick_ret
    tst    r14,r14          ; r14: the attract's answer (2: Start)
    bf     tick_ret
    mov    #1,r14           ; the title's 10 s are up
tick_ret:
    rts
    nop
.align 4
vars:
    .word  0                ; t
    .word  0                ; PRESS START shown (high byte)
    .long  0                ; CCE's VBlank-IN handler
k_600b:
    .word  600
