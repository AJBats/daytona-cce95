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
;
; The course's dear quads are cut as CCE builds them, in its polygon
; routines' common tail (below), and the late frames are counted at the
; list copy (further below).

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

; A polygon's commands, written (at slot @(136,gbr), @(155,gbr) slots of
; them; GBR the list area's context at 06057800 or 06057C00), go into its
; depth's list (06045E06, which returns its last slot) and the area's count
; past them: the common tail of CCE's quad and triangle routines (06045BC4,
; 06045C00; the near plane's pieces come through them too). A polygon whose
; attribute has bit 14 or 15 set (tools/vdp1x.py marks the course's
; polygons with a texture that has strips, and the car effects' smoke and
; sparks; CCE masks both bits off everywhere else) goes through the block's
; emit entry (06015140 + 28) while the block is there: it cuts the
; polygon's quads and links the pieces in itself, leaves an effect out, or
; hands back to the tail here. The triangle routine's tail is the quad
; routine's; the count is the link's return + 4 (its own sum of
; @(155,gbr), shorter).

.org 06045BE6
face_tail:
    mov.b  @(128,gbr),r0    ; the attribute's high byte
    tst    #192,r0
    bf     face_marked
face_link:
    mov.l  @(156,gbr),r0    ; the polygon's depth
    mov    r0,r4
    bsr    0x06045E06
    mov.w  @(136,gbr),r0
    add    #4,r0
    mov.w  r0,@(136,gbr)
face_out:                   ; 06045BF8, also the way out past the far plane
    lds.l  @r15+,pr
    rts
    nop

.org 06045C14
    bt     face_out         ; past the far plane (was 06045C34)

.org 06045C22
    bra    0x06045BE8
    mov.b  @(128,gbr),r0
face_marked:
    mov.l  vx_block,r1
    mov.w  @r1,r2
    mov.w  vx_magic,r3
    cmp/eq r2,r3
    bf     face_link
    add    #28,r1           ; the block's emit entry, r0 the depth
    jmp    @r1
    mov.l  @(156,gbr),r0
vx_magic:
    .word  0x5658
vx_block:
    .long  0x06015140

; The player car's effects (06040860, from the car's draw at 060407B4): a
; spark at each corner whose flag is up (the model at *060565F4) and the
; tire smoke (one of four frames, *06056650-*0605665C), through CCE's model
; draw for models wholly in view (060457DC: the cars, their shadows and the
; course blocks in view). Its quad and triangle routines (06045A2C,
; 06045A7E) have no screen tests and linked their polygon themselves; they
; end in the tail above instead (the depth to @(156,gbr) first), so the
; block can leave the effects out. Through the course's model draw
; (06045958) the nearest smoke puffs went missing (its near plane), so the
; draw stays CCE's.

.org 06045A66
    mov    #4,r0
    mov.b  r0,@(155,gbr)
    mov    r4,r0
    bra    face_tail
    mov.l  r0,@(156,gbr)

.org 06045AA8
    mov    #4,r0
    mov.b  r0,@(155,gbr)
    mov    r4,r0
    bra    face_tail
    mov.l  r0,@(156,gbr)
