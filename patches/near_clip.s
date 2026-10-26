; Model polygons close to the camera DUSA's way. Assembled into
; patches/near_clip.patch by tools/mkpatch.py.
;
; CCE's model vertex transform (060463E4, used by the model draw 060457DC
; for the cars) marks a vertex nearer than the render context's near
; distance (+0, 0.5 units) and the polygon submit (06045A2C) drops any
; polygon with a marked vertex. DUSA drops a polygon only when a vertex
; reaches the camera (z <= 0, 06031DF4). So when DUSA's attract camera
; sits beside a car's rear wheel, CCE dropped the body panels running past
; the camera and left holes. Here a vertex between 1/128 unit and the near
; distance is projected as any other, its screen position held to VDP1's
; -1023..1023 so it can't wrap; nearer than 1/128 unit (the divide's k / z
; would overflow), or behind, it is marked as before. Further than the near
; distance nothing changes. The transform with a screen offset (06046478)
; is left as it is.
;
; 060463E4 jumps to its copy in the cave with the near case added. Cave:
; 0603344E-0603353B, a function nothing branches to or points at, dead in
; DaytonaCCEReverse's sweeps and never run in the attract, a 1P race or a
; 2P race here.

.org 060463E4
    mov.l  transform_at,r0
    jmp    @r0
    nop
.align 4
transform_at:
    .long  transform

.org 0603344E
transform:
    mov.l  @(4,r1),r13
    add    r1,r13
    mov.w  @(0,r1),r0
    mov    r0,r11
    mov.l  @(28,r14),r10
    mov.l  @(0,r14),r9
    mov.w  @(140,gbr),r0
    mov    r0,r7
    add    #-8,r15
    mov    r15,r5
    mov.w  k_ff00,r6
    mov.l  k_220,r4
    add    r14,r4
loop:
    mov.w  @r13+,r12
    mov.w  @r13+,r1
    mov.w  @r13+,r2
    mov.l  r1,@(0,r5)
    mov.l  r2,@(4,r5)
    mov.l  @r4+,r1
    dmuls.l r1,r12
    mov.l  r7,@(16,r6)
    mov    #0,r1
    mac.l  @r4+,@r5+
    mac.l  @r4+,@r5+
    add    #-8,r5
    mov.l  @r4+,r8
    sts    mach,r0
    sts    macl,r3
    add    #-48,r4
    xtrct  r0,r3
    add    r8,r3
    mov.l  @r4+,r0
    dmuls.l r0,r12
    mov.l  r3,@(0,r6)
    mov.l  r1,@(20,r6)
    mac.l  @r4+,@r5+
    and    r6,r3
    mov.l  r3,@(4,r10)
    mac.l  @r4+,@r5+
    add    #-8,r5
    mov.l  @r4+,r8
    sts    mach,r0
    sts    macl,r1
    mov.l  @r4+,r2
    dmuls.l r2,r12
    xtrct  r0,r1
    add    r8,r1
    mac.l  @r4+,@r5+
    mac.l  @r4+,@r5+
    add    #-8,r5
    mov.l  @r4+,r8
    sts    mach,r0
    sts    macl,r2
    xtrct  r0,r2
    add    r8,r2
    cmp/gt r3,r9
    bt     near
    mov.l  @(28,r6),r3
    dmuls.l r3,r1
    neg    r2,r2
    sts    mach,r0
    dmuls.l r3,r2
    mov.w  r0,@(0,r10)
    sts    mach,r0
    mov.w  r0,@(2,r10)
next:
    dt     r11
    bf/s   loop
    add    #16,r10
    rts
    add    #8,r15
near:                       ; nearer than the near distance
    mov.w  k_min,r0
    cmp/gt r3,r0
    bt     mark
    mov.l  @(28,r6),r3      ; k / z
    dmuls.l r3,r1
    neg    r2,r2
    sts    mach,r0          ; x
    dmuls.l r3,r2
    mov.w  k_1023,r8
    cmp/gt r8,r0
    bf     x_hi_ok
    mov    r8,r0
x_hi_ok:
    neg    r8,r8
    cmp/ge r8,r0
    bt     x_ok
    mov    r8,r0
x_ok:
    mov.w  r0,@(0,r10)
    sts    mach,r0          ; y
    neg    r8,r8
    cmp/gt r8,r0
    bf     y_hi_ok
    mov    r8,r0
y_hi_ok:
    neg    r8,r8
    cmp/ge r8,r0
    bt     y_ok
    mov    r8,r0
y_ok:
    bra    next
    mov.w  r0,@(2,r10)
mark:                       ; behind, or too near to divide: out, as in CCE
    add    #2,r3
    bra    next
    mov.l  r3,@(4,r10)
k_ff00:
    .word  0xFF00
k_min:
    .word  0x0200           ; 1/128 unit
k_1023:
    .word  1023
.align 4
k_220:
    .long  0x00000220
