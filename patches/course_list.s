; DUSA's attract draws the course blocks its recording lists. Assembled into
; patches/course_list.patch by tools/mkpatch.py.
;
; CCE draws the course by the sector under the camera's eye: the view build
; (06029D8C) draws a run of blocks from the sector's own, as many as the
; sector's record gives for the way the camera looks, then the blocks the
; record lists (0602A118). That suits a camera driving down the road. DUSA's
; attract cameras hang beside it and look every way, and on Seaside
; Galaxy's opening crane, over the sea beside the bridge, the sector nearest
; the eye changes between the two roads as the crane moves: the far side's
; blocks came and went (the user's report, 2026-10-26).
;
; src/attract.c now keeps, while DUSA's demo plays, a list of blocks for
; that frame (CCE's own choice there, and the blocks on screen that CCE
; draws elsewhere in the shot: tools/attract_vis.py, tools/build_attract.py)
; and points list_at at it (a count, then block numbers, 16-bit).
; course_draw stands in for 06029D8C: with a list, it does what 06029D8C
; does but draws only the list, through 0602A118, which takes it from
; list_of (master and slave share it as they share a record's list);
; outside the attract it clears list_at and goes to 06029D8C.
;
; Caves: 06043C20-06043CCB and 0603E3E8-0603E459, functions nothing
; branches to or points at, dead in DaytonaCCEReverse's sweeps and never run
; in the attract, a 1P race or a 2P race. 0602A118's literals for 0x60 and
; 0x6E become immediates, and one slot holds list_of.

.org 06029C9C
    .long  course_draw      ; the view build's course drawing, was 06029D8C

.org 0602A11E
    mov    #96,r1           ; +0x60, was a literal

.org 0602A124
    mov    #110,r0          ; +0x6E, was a literal

.org 0602A130
    mov.l  list_of_at,r0    ; the list to draw (was the record's, from +36)
    jsr    @r0
    nop
    tst    r3,r3
    bt     0x0602A1D6       ; none: 0602A118's return
    nop
    nop

.org 0602A1E0
list_of_at:
    .long  list_of

.org 06043C20
list_at:
    .long  0                ; src/attract.c's list, while DUSA's demo plays
course_draw:
    mov.l  attract_at,r0
    mov.b  @r0,r0
    tst    r0,r0
    mov.l  list_ptr_at,r1
    bf     in_attract
    mov    #0,r0
    mov.l  r0,@r1           ; no list outside the attract
in_attract:
    mov.l  @r1,r0
    tst    r0,r0
    bf     own_draw
    mov.l  cce_draw_at,r0
    jmp    @r0
    nop
own_draw:                   ; 06029D8C's steps, with the list for the run
    sts.l  pr,@-r15
    mov.l  r4,@-r15
    mov.l  flags_at,r1
    mov.l  clear_at,r0      ; the blocks' drawn flags cleared
    jsr    @r0
    nop
    mov.l  cam_at,r13       ; the camera's sector (as 06029D98-06029DA6)
    mov.l  @r13,r0
    add    #32,r0
    mov    r0,r14
    mov.l  @r13,r13
    mov.l  lookup_at,r0     ; through the view build's own pointer to it
    mov.l  @r0,r0
    jsr    @r0
    nop
    mov.l  cam_at,r10       ; the way it looks (06029DA8)
    mov.l  @r10,r10
    mov.l  facing_at,r0
    jsr    @r0
    nop
    mov.l  k_14000,r4
    mov.l  context_at,r0
    jsr    @r0
    nop
    mov.l  @r15+,r4
    mov.l  draw_list_at,r0  ; the list, shared with the slave
    jsr    @r0
    nop
    mov.l  slave_wait_at,r0
    jsr    @r0
    nop
    mov.l  k_8000,r4
    mov.l  context_at,r0
    jsr    @r0
    nop
    lds.l  @r15+,pr
    rts
    nop
.align 4
list_ptr_at:
    .long  0x26043C20       ; list_at, cache-through
attract_at:
    .long  0x2601335C       ; the attract's demo number, 0 in a race
cce_draw_at:
    .long  0x06029D8C
flags_at:
    .long  0x0605173C
clear_at:
    .long  0x0602AA84
cam_at:
    .long  0x06052094
lookup_at:
    .long  0x06029F18       ; the view build's pointer to the sector lookup
facing_at:
    .long  0x0602A958
k_14000:
    .long  0x00014000
context_at:
    .long  0x060456C8
draw_list_at:
    .long  0x0602A118
slave_wait_at:
    .long  0x0600751C
k_8000:
    .long  0x00008000

.org 0603E3E8
list_of:                    ; r2: the camera's record (+4 x its list); r3: the list to draw, or 0
    mov.l  list_of_ptr,r0
    mov.l  @r0,r3
    tst    r3,r3
    bt     record_list
    mov.w  @r3,r0           ; an empty one draws nothing (0602A118 counts down from its count)
    tst    r0,r0
    bf     list_done
    rts
    mov    #0,r3
record_list:
    mov.l  @(36,r2),r3
    tst    r3,r3
    bt     list_done
    mov.l  blk_at,r0
    mov.l  @r0,r0
    add    r0,r3
list_done:
    rts
    nop
.align 4
list_of_ptr:
    .long  0x26043C20       ; list_at, cache-through
blk_at:
    .long  0x06054934       ; the course's sector map
