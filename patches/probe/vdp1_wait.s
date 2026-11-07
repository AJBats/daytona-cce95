; A frame VDP1 hasn't finished drawing waits instead of going to the screen
; cut short. Assembled into patches/probe/vdp1_wait.patch by
; tools/mkpatch.py probe/vdp1_wait.
;
; In no build. Tried on the Saturn (2026-11-07, with the probe disc): no
; frame went out cut short, but frames dropped all over Dinosaur Canyon and
; the race ran slow (the race runs a tick a frame), far worse than the
; polygons CCE loses. CCE holds 30 frames a second whatever VDP1 has left
; to draw, and so do we; the work is to keep VDP1 inside the frame. To try
; it again, point patches/attract.s's literal at 06028EA0 to 0603702C and
; add this patch to the build. A frame it holds is one VDP1 was late with,
; so the frames it drops count them.
;
; CCE's kernel shows a frame as soon as the CPU has built the next list. The
; race program returns, the main loop marks the list ready (06011F89), and at
; the next VBlank-IN that finds it ready (06005568, at least one vertical
; blank on) a VBlank task copies it over VDP1's command table (06047B90, a DMA
; to 25C00000); at the VBlank-OUT after that the kernel changes frames
; (06005652 -> 060071AE, FBCR = 3) and VDP1 starts on the new list. Whether
; or not VDP1 has drawn the last list to its end: when it hasn't, the copy
; replaces the commands it has yet to read and the change stops it, and
; whatever comes last in the list never appears, the player's car first (it
; is drawn last): the car that vanished or came out half-drawn in heavy
; moments on the Saturn (a playtester's report). A probe disc
; (patches/probe/vdp1_late.s) tinted such frames red: about 11 a minute in
; ours on Dinosaur Canyon, about 5 in unmodified CCE, which loses its car the
; same way.
;
; Now the race program, at the end of its frame, waits until VDP1 has drawn
; the list on its way to the screen before it returns, so the list isn't
; ready until then and the copy and the change wait for the next VBlank-IN: a
; late frame stays on screen a vertical blank longer instead of losing
; polygons, as the Tomb Raider project's renderer does. VDP1's deadline is
; the VBlank-IN the ready flag has to beat, so the wait costs a frame only
; when VDP1 would have lost it, or finishes in the last millisecond before
; that VBlank-IN (the main loop's work between the race program and the
; ready flag).
;
; It waits only while EDSR reads 1: the last frame was drawn to its end (BEF)
; and this one is still being drawn (CEF clear). The race program also runs
; while the kernel isn't changing frames for it (mode 1 at 06011F9C, in the
; attract's hand-over to the ranking and the title): VDP1 draws nothing then,
; EDSR reads 0 and there is nothing to wait for. Should VDP1 never finish, the
; wait gives up after 0xC8F8 polls (the low half of attract_fade's address;
; about 4 vertical blanks) and the frame is cut as before.
;
; The race frame's last call (from 06028D9E, through the literal at 06028EA0
; that patches/attract.s points here) comes here first, then goes on to
; attract.s's attract_fade (0603C8F8) and CCE's fade engine.
; Cave: the tail of CCE's original throttle function, after
; patches/grip_filter.s (0603702C-06037049; no code loads from it).

.org 0603702C
vdp1_wait:
    mov.l  next_at,r3
    mov.l  edsr_at,r1
    extu.w r3,r2
poll:
    mov.w  @r1,r0
    cmp/eq #1,r0
    bf     drawn
    dt     r2
    bf     poll
drawn:
    jmp    @r3
    nop
.align 4
edsr_at:
    .long  0x25D00010
next_at:
    .long  0x0603C8F8
