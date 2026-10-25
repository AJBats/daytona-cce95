; Road direction DUSA's way: from the ground polygon under the car's front
; corner. Assembled into patches/road_direction.patch by tools/mkpatch.py.
;
; The straightening pull (06035C98, patch 12) turns the car toward the road
; direction (+0x48) once its heading has stayed within 6 deg of it for 3
; ticks. Its only reader is 06035E56.
;   DUSA: +0x25C is the road direction kept in the ground polygon (+0x30
;         high word) under the front corner (0.92 right, 1.8 ahead; 06027CA4
;         with r5 = 0), unchanged where no polygon is found. Constant along
;         each section: exact on a straight.
;   CCE:  each of the four corner contacts (06036BB8) copied +0x194, a
;         direction from CCE's course line that jitters by up to 1 deg every
;         few units on a straight (Seaside: 9660-9898). With DUSA's pull the
;         heading followed it, and the car wobbled on the straights.
; Patched: the copy at the first corner contact of the tick goes through the
; cave, which keeps CCE's value and then looks up DUSA's under the front
; corner, carried in the polygon's flags (bit 1 set, bits 2-15 the
; direction; tools/col_convert.py). The other three no longer copy. Courses
; without DUSA's directions (the CCE-only ones) keep CCE's.
;
; Cave: the gaps left in the unreferenced 0603C304-0603C5CB (code at
; 0603C424, after patch 22's; literals at 0603C59C, after the reflection's).

; was mov.l =0x194,r0; mov.w @(r0,r5),r1; exts.w r1,r1; mov.w =0x48,r0;
; mov.l r1,@(r0,r5). r2, r4-r7 are still needed after; 06036BB8's epilogue
; restores r8-r14.
.org 06036C60
    mov.l  road_at,r0
    jsr    @r0
    nop
    nop
    nop
.org 06036CA4
road_at:
    .long  road                 ; was 0x194, read only by the copy above

.org 0603C424
road:
    tst    r7,r7                ; corner index x 4
    bf     skip                 ; once a tick, at the first corner
    sts.l  pr,@-r15
    mov.l  r2,@-r15
    mov.l  r4,@-r15
    mov.l  r5,@-r15
    mov.l  r6,@-r15
    mov.l  r7,@-r15
    mov    r5,r14               ; car
    mov.w  line,r0
    mov.w  @(r0,r14),r1
    exts.w r1,r1
    mov.w  dir,r0
    mov.l  r1,@(r0,r14)         ; CCE's, kept where no DUSA direction is found
    mov.w  @(14,r14),r0         ; heading
    mov.w  corner,r13
    add    r0,r13
    mov.l  sin,r0
    jsr    @r0
    mov    r13,r4
    mov.l  reach,r4
    mov.l  mul,r1
    jsr    @r1
    mov    r0,r5
    mov.l  @(8,r14),r12
    add    r0,r12               ; z
    mov.l  cos,r0
    jsr    @r0
    mov    r13,r4
    mov.l  reach,r4
    mov.l  mul,r1
    jsr    @r1
    mov    r0,r5
    mov.l  @r14,r4
    add    r0,r4                ; x
    shll2  r4
    shll2  r4
    mov    r12,r5
    shll2  r5
    shll2  r5
    mov.l  find,r1
    mov.w  grid,r0
    jsr    @r1                  ; r0 -1 and r6 = the polygon if one holds the point
    mov.l  @(r0,r14),r7         ; the car's grid
    tst    r0,r0
    bt     done
    mov.w  @(2,r6),r0           ; flags, low word
    tst    #2,r0
    bt     done
    mov    #-4,r1
    and    r1,r0
    exts.w r0,r1
    mov.w  dir,r0
    mov.l  r1,@(r0,r14)
done:
    mov.l  @r15+,r7
    mov.l  @r15+,r6
    mov.l  @r15+,r5
    mov.l  @r15+,r4
    mov.l  @r15+,r2
    lds.l  @r15+,pr
skip:
    rts
    nop

.org 0603C59C
line:
    .word  0x0194
dir:
    .word  0x0048
corner:
    .word  0x2CC0               ; atan(0.92 / 1.8) right of straight ahead (0x4000)
grid:
    .word  0x012C
.align 4
reach:
    .long  0x0002057D           ; 2.0214 = |(0.92, 1.8)|
sin:
    .long  0x06047D20
cos:
    .long  0x06047D3C
mul:
    .long  0x06048180
find:
    .long  0x060368D4           ; r4, r5 = x, z << 4, r7 = grid
