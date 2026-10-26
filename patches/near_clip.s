; Model polygons close to the camera DUSA's way. Assembled into
; patches/near_clip.patch by tools/mkpatch.py.
;
; CCE's model vertex transform (060463E4, used by the model draw 060457DC
; for the cars, their shadows, and course blocks wholly in view and 100
; units off) marks a vertex nearer than the render context's near distance
; (+0, 0.5 units), and the polygon submit (06045A2C) drops any polygon with
; a marked vertex. DUSA's polygon routine (06031DF4, cars and shadows)
; drops a polygon with a vertex at or behind the camera (z <= 0), or one
; projected off its screen by DUSA's bounds (060320E6: x outside
; -400..400, y outside -400..200, from the centre, y down).
;
; So when DUSA's attract camera sits beside a car's rear wheel, CCE dropped
; the body panels running past the camera and left holes. Here a vertex
; between 1/128 unit and the near distance is projected as any other, its
; screen position held to VDP1's -1023..1023 so it can't wrap; nearer than
; 1/128 unit (the divide's k / z would overflow), or behind, it is marked
; as before. Further than the near distance nothing changes. CCE's cars
; aren't DUSA's models, so DUSA's bounds wouldn't give DUSA's picture on
; them (in Three Seven's close-up beside a drone's wheel they drop its
; lower side panel).
;
; The shadow (the model at *060565E4) is DUSA's own, vertex for vertex
; (DUSA's at 060F8000), so it takes DUSA's rule whole: every vertex is
; projected and marked if it lands outside DUSA's bounds. In Seaside
; Galaxy's close pass beside car 0 the shadow's corner is 0.5 units off the
; camera: CCE drew the two quads running past the camera, 600,000 pixels'
; worth, and VDP1 ran out of time before the car's body in the commands
; after them, so no car at all; DUSA's bounds drop both quads.
;
; The transform with a screen offset (06046478) is left as it is.
;
; 060463E4 jumps to its copy in a cave; the near case goes to the old
; transform's body, unused after the jump. Cave: 0603344E-0603353B, a
; function nothing branches to or points at, dead in DaytonaCCEReverse's
; sweeps and never run in the attract, a 1P race or a 2P race here.

.org 060463E4
    mov.l  transform_at,r0
    jmp    @r0
    nop
.align 4
transform_at:
    .long  transform

near:                       ; r3: z, r1 and r2: x and y, r9: the near distance (the shadow: all)
    mov.w  k_min,r0
    cmp/gt r3,r0
    bt     mark
    mov.l  @(28,r6),r3      ; k / z
    dmuls.l r3,r1
    neg    r2,r2
    sts    mach,r0          ; x
    dmuls.l r3,r2
    mov.l  shadow_r9,r8
    cmp/eq r8,r9
    bf     held
    mov.w  r0,@(0,r10)      ; the shadow: off DUSA's screen, out
    mov.w  k_400,r8
    add    r8,r0
    mov.w  k_800,r1
    cmp/hi r1,r0            ; x outside -400..400
    bt     out
    sts    mach,r0          ; y
    mov.w  r0,@(2,r10)
    add    r8,r0
    mov.w  k_600,r1
    cmp/hi r1,r0            ; y outside -400..200
    bf     back
out:
    mov.l  @(4,r10),r3
mark:                       ; behind, or too near to divide: out, as in CCE
    add    #2,r3
    mov.l  r3,@(4,r10)
back:
    mov.l  next_at,r0
    jmp    @r0
    nop
held:                       ; any other model: held to -1023..1023
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
    bra    back
    mov.w  r0,@(2,r10)
k_min:
    .word  0x0200           ; 1/128 unit
k_400:
    .word  400
k_600:
    .word  600
k_800:
    .word  800
k_1023:
    .word  1023
.align 4
next_at:
    .long  next
shadow_r9:
    .long  0x7FFFFFFF       ; the shadow's (transform's k_all)

.org 0603344E
transform:
    mov.l  @(4,r1),r13
    add    r1,r13
    mov.w  @(0,r1),r0
    mov    r0,r11
    mov.l  @(28,r14),r10
    mov.l  @(0,r14),r9      ; the near distance
    mov.l  shadow_at,r0
    mov.l  @r0,r0
    cmp/eq r1,r0
    bf     rule_set
    mov.l  k_all,r9         ; the shadow: every vertex by DUSA's rule
rule_set:
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
    bt     to_near
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
to_near:                    ; nearer than the near distance
    mov.l  near_at,r0
    jmp    @r0
    nop
k_ff00:
    .word  0xFF00
.align 4
k_220:
    .long  0x00000220
near_at:
    .long  near
shadow_at:
    .long  0x060565E4       ; the car shadow model
k_all:
    .long  0x7FFFFFFF
