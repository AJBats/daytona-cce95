; Test build only (make disc PROBE=1): the picture turns red while the frame on
; screen was cut short because VDP1 hadn't finished drawing it. Assembled into
; patches/probe/vdp1_late.patch by tools/mkpatch.py probe/vdp1_late.
;
; In races (the kernel's frame mode 2) the VBlank-IN handler (06005568) takes
; a ready list once a vertical blank has gone by: it turns VBlank erase on
; (0600718E with r4 = 1), and a VBlank task copies the list over VDP1's
; command table (06047B90); the VBlank-OUT after that changes frames. A list
; VDP1 is still drawing at the copy goes on with the new list's commands and
; is stopped at the change: that frame goes out cut short (docs/performance.md).
; So at the handler's call of 0600718E with r4 = 1, before the copy, this reads
; EDSR's CEF: clear, VDP1 hasn't finished, and the frame it's drawing (the one
; on screen from the change) gets +255 red in the colour offsets: B for the
; sprite layer (VDP1's 3D, CLOFSL 0x40) and A for NBG1, both enabled in races
; (CLOFEN 0x42) at 0 in a day race. The next list finished in time puts them
; back to 0. Day races only: dusk and night keep their tint in those
; registers. It counts them too, at count (0600A904), for the debugger.
;
; (The first version read BEF at the change, and missed most: after the copy
; VDP1 often runs to the new list's end before the change and reports done.)
;
; The handler's literal for 0600718E (06005710, shared with the VBlank-OUT
; handler's call with r4 = 0, which goes straight on) points here; this ends
; by jumping to 0600718E.
;
; Cave: GFS_Load (0600A8B2), patches/attract_load.s's in the real build; the
; probe build leaves out attract_load and attract_choice, so the attract
; reads the whole of DEMOTTL.BIN as CCE did (ours comes out on top). Its
; neighbour's literal at 0600A950 stays.
.target DAYTONA/0 06005200 sh2

.org 06005710
    .long  probe

.org 0600A8B2
probe:
    mov    r4,r0
    cmp/eq #1,r0
    bf     go               ; the VBlank-OUT handler's call
    mov.l  edsr_at,r1
    mov.w  @r1,r0
    mov.l  coar_at,r1
    mov.l  flag_at,r2
    tst    #2,r0            ; T: VDP1 still drawing the last list at its copy
    bf     drawn
    mov.w  red,r0
    mov.w  r0,@r1           ; COAR: NBG1
    mov.w  r0,@(6,r1)       ; COBR: the sprite layer
    mov.l  @(4,r2),r0
    add    #1,r0
    mov.l  r0,@(4,r2)       ; count
    mov    #1,r0
    bra    go
    mov.b  r0,@r2
drawn:
    mov.b  @r2,r0
    tst    r0,r0
    bt     go
    mov    #0,r0
    mov.w  r0,@r1
    mov.w  r0,@(6,r1)
    mov.b  r0,@r2
go:
    mov.l  next_at,r0
    jmp    @r0
    nop
.align 4
edsr_at:
    .long  0x25D00010
coar_at:
    .long  0x25F80114
flag_at:
    .long  flag
next_at:
    .long  0x0600718E
red:
    .word  0x00FF
.align 4
flag:
    .long  0                ; byte: the colour offsets are red
count:
    .long  0                ; cut frames so far
