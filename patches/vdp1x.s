; The race frame's list through src/vdp1x.c's block before it goes to VDP1
; (docs/performance.md, "Race-time quads"). Assembled into
; patches/vdp1x.patch by tools/mkpatch.py.
;
; The race frame's last call (from 06028D9E, through the literal at 06028EA0
; that patches/attract.s points here) comes when the frame's list is whole,
; before the main loop marks it ready. Here it checks for the block's magic
; word ('VX') at 06015140: the block is a block of SCREEN.BIN
; (tools/vdp1x.py), which CCE's block loader copies there at every race
; start, not in the attract. With it, the call goes through the block's
; entry (06015142), which runs its pass over the list and goes on to
; attract.s's attract_fade (0603C8F8); without it, straight there. Either
; way with PR the race frame's, so attract_fade returns to it.
;
; Cave: the tail of CCE's original throttle function after
; patches/grip_filter.s (0603702C-06037049; no code loads from it).

.org 0603702C
    mov.l  block_at,r1
    mov.w  @r1+,r0          ; the magic word; r1 the entry after it
    mov.w  magic,r2
    cmp/eq r2,r0
    bf     plain
    jmp    @r1
    nop
plain:
    mov.l  fade_at,r1
    jmp    @r1
    nop
.align 4
block_at:
    .long  0x06015140
fade_at:
    .long  0x0603C8F8       ; patches/attract.s's attract_fade
magic:
    .word  0x5658

; Whether VDP1 drew each list to its end: the race registers its list copy
; (06047B90, which DMAs the next list over VDP1's command table) as a VBlank
; task, from the literal at 060291B8; the kernel runs it in the VBlank-IN
; handler when it takes a list, VDP1's deadline. Registered here instead,
; the copy first notes VDP1's end status: late (0603E438) is 1 when VDP1 was
; still drawing the list the copy replaces (the frame goes out cut short,
; its end lost), and count (0603E43C) counts those frames in the race, for
; the debugger and the measuring tools (docs/performance.md).
;
; Cave: 0603E414-0603E447, in the dead function at 0603E3E8 after
; patches/course_list.s; its literals at 0603E448-0603E453 stay, the live
; AI code at 0603E340 and 0603E394 loads them.

.org 060291B8
    .long  0x0603E414       ; was 06047B90

.org 0603E414
list_copy:
    mov.l  edsr_at,r1
    mov.w  @r1,r0
    mov.l  late_at,r1
    tst    #2,r0            ; T: VDP1 still drawing the list this copy replaces
    movt   r0
    mov.b  r0,@r1
    mov.l  @(4,r1),r2
    add    r0,r2
    mov.l  r2,@(4,r1)
    mov.l  copy_at,r1
    jmp    @r1
    nop
.align 4
edsr_at:
    .long  0x25D00010
late_at:
    .long  0x0603E438
copy_at:
    .long  0x06047B90
late:
    .long  0
count:
    .long  0
