; Test build only (make disc PROBE=1): the picture turns red while the frame on
; screen was cut short because VDP1 hadn't finished drawing it. Assembled into
; patches/probe/vdp1_late.patch by tools/mkpatch.py probe/vdp1_late.
;
; In races (the kernel's frame mode 2) the VBlank handler asks VDP1 for a
; frame change with 060071AE (FBCR = 3) once the game's list is ready, and
; the change comes whether or not VDP1 has drawn the last list to its end.
; EDSR bit 0 (BEF) says whether it had at the last change. Each time a change
; is asked for, this reads BEF for the frame now on screen and, if it was cut
; short, adds +255 red to the colour offsets: B for the sprite layer (VDP1's
; 3D, CLOFSL 0x40) and A for NBG1, both enabled in races (CLOFEN 0x42) at 0 in
; a day race. The next frame drawn in time puts them back to 0. Day races
; only: dusk and night keep their tint in those registers.
;
; A dozen instructions a frame; VDP1 never sees them. The handler's literal
; for 060071AE (06005728) points here; this ends with 060071AE's own write.
;
; Cave: GFS_Load (0600A8B2), patches/attract_load.s's in the real build; the
; probe build leaves out attract_load and attract_choice, so the attract
; reads the whole of DEMOTTL.BIN as CCE did (ours comes out on top). Its
; neighbour's literal at 0600A950 stays.
.target DAYTONA/0 06005200 sh2

.org 06005728
    .long  probe

.org 0600A8B2
probe:
    mov.l  edsr_at,r1
    mov.w  @r1,r0
    tst    #1,r0            ; T: the frame on screen was cut short
    mov.l  coar_at,r1
    mov.l  flag_at,r2
    bf     drawn
    mov.w  red,r0
    mov.w  r0,@r1           ; COAR: NBG1
    mov.w  r0,@(6,r1)       ; COBR: the sprite layer
    mov    #1,r0
    bra    change
    mov.b  r0,@r2
drawn:
    mov.b  @r2,r0
    tst    r0,r0
    bt     change
    mov    #0,r0
    mov.w  r0,@r1
    mov.w  r0,@(6,r1)
    mov.b  r0,@r2
change:
    mov    #3,r3
    mov.l  fbcr_at,r2
    rts
    mov.w  r3,@r2
.align 4
edsr_at:
    .long  0x25D00010
coar_at:
    .long  0x25F80114
flag_at:
    .long  flag
fbcr_at:
    .long  0x25D00002
red:
    .word  0x00FF
flag:
    .word  0
