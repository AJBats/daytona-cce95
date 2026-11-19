; Each polygon partly in view drawn from its edge nearer the screen
; (docs/performance.md, "Line direction"). Assembled into
; patches/line_direction.patch by tools/mkpatch.py.
;
; VDP1 draws a distorted sprite or polygon as lines from its edge A-D to its
; edge B-C. A line stops once it leaves the clip window, but VDP1 steps
; every pixel of it before it enters (Mednafen's drawn_ac test,
; src/ss/vdp1_common.h). Drawn from B A D C with the horizontal flip
; toggled, the picture is the same and each line runs the other way.
;
; CCE's corner writer for a polygon partly in view (06047588, from the quad
; path at 060469E8 and the triangle path at 06046A6C) turned the command to
; start at a corner in view, or the corner nearest the centre, through the
; flips. It now starts from B-C when A and D lie further past CCE's view box
; than B and C do, and from A-D otherwise. A corner's distance past the box
; is the larger of its x and y overshoots. The box is @(24,gbr): half-width
; and half-height about the local origin, the box CCE's own in-view tests
; use. Only the edge the lines start from matters for VDP1's time, so CCE's
; other turns are dropped. A gouraud command keeps its corners: its colour
; table follows them.
;
; A polygon past the guard band (06046E0E) is cut to it in up to three
; commands. After the cut's last step (060472CC) each of them goes through
; the same choice, its corners read back from the list.

.org 06046E3E
    bsr    guard_last
    nop

; Cave: CCE's corner choice (06047588-0604761B), which this replaces; the
; writers after it (0604761C as given, 06047628 from B A D C, horizontal
; flip toggled) stay.
.org 06047588
pick:
    mov.b  @(5,r7),r0       ; the draw mode's low byte
    tst    #4,r0            ; gouraud: as given
    bf     0x0604761C
    sts.l  pr,@-r15
    mov.l  r8,@-r15
    mov.l  @(24,gbr),r0     ; the view box: half-width << 16 | half-height
    extu.w r0,r8
    shlr16 r0
    mov    r0,r9
    bsr    past_box
    mov    r1,r5            ; A
    mov    r5,r0
    bsr    past_box
    mov    r4,r5            ; D
    add    r5,r0
    tst    r0,r0
    bt     pick_go          ; A and D in the box: from A-D
    bsr    past_box
    mov    r2,r5            ; B
    sub    r5,r0
    bsr    past_box
    mov    r3,r5            ; C
    sub    r5,r0
pick_go:
    mov.l  @r15+,r8
    lds.l  @r15+,pr
    cmp/pl r0               ; A and D further past it than B and C: from B-C
    bt     0x06047628
    bra    0x0604761C
    nop

; r5 a corner (x << 16 | y): how far it lies past the box (half-width r9,
; half-height r8), the larger of x and y, 0 inside it. r6 used.
past_box:
    swap.w r5,r6
    exts.w r6,r6
    cmp/pz r6
    bt     past_x
    neg    r6,r6
past_x:
    exts.w r5,r5
    cmp/pz r5
    bt     past_y
    neg    r5,r5
past_y:
    sub    r9,r6
    sub    r8,r5
    cmp/gt r5,r6
    bf     past_max
    mov    r6,r5
past_max:
    cmp/pz r5
    bt     past_out
    mov    #0,r5
past_out:
    rts
    nop

; The guard band cut's last step, then each of its commands (at slot
; @(136,gbr), @(155,gbr) slots of them, in the list at 0601B000) through
; pick. r10 is the cut's own, restored by its epilogue after this returns.
guard_last:
    sts.l  pr,@-r15
    bsr    0x060472CC
    nop
    mov.w  @(136,gbr),r0
    mov.l  list_at,r7
    shll2  r0
    shll   r0
    add    r0,r7
    mov.b  @(155,gbr),r0
    shlr2  r0
    tst    r0,r0
    bt     guard_out
    mov    r0,r10
guard_cmd:
    mov.l  @(12,r7),r1
    mov.l  @(16,r7),r2
    mov.l  @(20,r7),r3
    bsr    pick
    mov.l  @(24,r7),r4
    dt     r10
    bf/s   guard_cmd
    add    #32,r7
guard_out:
    lds.l  @r15+,pr
    rts
    nop
.align 4
list_at:
    .long  0x0601B000
