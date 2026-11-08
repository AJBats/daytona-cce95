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
