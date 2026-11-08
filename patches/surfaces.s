; Surfaces DUSA's way: the corner surface flags carry DUSA's surface kinds
; (tools/col_convert.py writes them as their own types), the tyre step's
; surface grip takes DUSA's values, and the off-road drag is DUSA's.
; Assembled into patches/surfaces.patch by tools/mkpatch.py.
;
; Each corner contact (06036C52) maps its polygon's type through the table at
; 0604E1C4 into the car's flags +0x4C..+0x58. DUSA keeps its polygon's own
; flag byte per wheel (+0x120..+0x12C).
;
; Types and flags (DUSA kind -> type -> flags; under a roof -> type -> flags):
;   01 road           1 -> 0x01     2 -> 0x11
;   09, 41 road       12 -> 0x09    19 -> 0x19   DUSA's 08 and 40 bits add the
;                                                "other" term
;   02 apron          4 -> 0x02     16 -> 0x12   CCE's 0x03 counted the apron
;                                                as road too
;   04 grass          3 -> 0x04     17 -> 0x14
;   0C grass          13 -> 0x0C    20 -> 0x1C
;   10 road           14 -> 0x100   21 -> 0x110  Dinosaur Canyon's last hairpin
;   20 road           15 -> 0x200   22 -> 0x210  parts of Dinosaur Canyon and
;                                                Seaside
;   80 ground         8 -> 0x08     18 -> 0x18   outside the track edge where
;                                                no wall lies
; 0x10 is CCE's roof bit. CCE's ground under its roofs was all road (type 2,
; 0x11), and so were the roofed pieces tools/col_convert.py cut from DUSA's
; polygons, whatever DUSA's kind; now they keep it. The tunnel echo
; (06030D3A, a front corner) and the engine's tunnel sound (06040664, two
; corners or more) compared flags with 17 exactly; they now test the roof
; bit. DUSA's 10 and 20 can't keep their bits: 0x10 is the roof, CCE's own
; courses use 0x21 and 0x41 (types 9 and 10, compared exactly at 060314A8
; and 060315FA), and 0x80 is the wall strip (06037680, 06036C76). The flag
; readers (a read watch on +0x4C..+0x58) are those, the off-road drag and
; the tyre step. The table outgrew CCE's 16 entries (0604E1C4); it moves to
; the end of the old surface-grip code.
;
; Surface grip (CCE 06035624, DUSA 0602C7FC), per axle from the OR of its two
; corners' flags: the mean of one term per surface present, x 0x101.
;   DUSA: 01 0xEE, 04 0xB4, 02 0xD2, 10 0xF6, 20 0xFA, any other bit 0x96.
;   CCE: 01 0xEE, 04 0x80, 03 0xD2, 11/21/41 0xEE, other 0x96. Grass gripped
;   0.50 where DUSA's grips 0.71, and the kinds DUSA tells apart were road.
; Now DUSA's terms, with CCE's own marker bits 0x10/0x20/0x40 dropped first
; so roofs and CCE's two special types grip as the road they are.
;
; Off-road drag (CCE 0604DC40, DUSA 0602F71C), added to the speed-table drag:
;   DUSA: wheels on grass (04) among all four; none if any wheel is on its 10
;   ground (the hairpin) or by car number (4-5, 10 and up); cars 8-9 heavy
;   table x2; else 1-2 wheels heavy / 4, 3-4 wheels heavy / 2.
;   CCE: the two front corners only, none if either is on road (01), per-car
;   byte +0x1C6 (0 light table / 2, 1 heavy x2, 2 none), the light table
;   (002DCE20) 1.5x DUSA's (DUSA's light is exactly heavy / 2).
; Now DUSA's, with CCE's per-car byte in place of DUSA's car numbers (1 is
; DUSA's cars 8-9, 2 its cars 4-5), and CCE's mode byte 002FC21D kept. CCE's
; heavy table (002DC620) is DUSA's (0604679C) word for word.

; Corner flags by type, at the end of the old surface-grip code (below).
.org 06036CA0
    .long  surf_flags       ; was CCE's table at 0604E1C4

; Echo and engine tunnel sound: the roof bit, not flags == 17.
.org 06030D3A
    tst    #16,r0
    bf/s   0x06030D4A       ; front left corner roofed: echo
.org 06030D46
    tst    #16,r0
    bt     0x06030D50       ; front right corner not roofed: no echo
.org 06040664
    tst    #16,r0           ; T: not roofed; r1 counts the corners without a roof
.org 0604066A
    tst    #16,r0
.org 06040670
    tst    #16,r0
.org 06040676
    tst    #16,r0
.org 0604067A
    mov    #3,r0
.org 0604067E
    bt     0x06040682       ; two or more roofed corners: the tunnel sound

; Surface grip: r4 = the axle's flags, r8 = sum, r9 = count (both 0 here);
; 060356DA turns them into the mean.
.org 06035640
    mov    #0x70,r6
    not    r6,r6
    and    r6,r4            ; CCE's roof and special-type bits: road
    mov.w  m_road,r6
    tst    r6,r4
    not    r6,r7
    bt/s   s_grass
    and    r7,r4
    mov.w  g_road,r6
    add    r6,r8
    add    #1,r9
s_grass:
    mov.w  m_grass,r6
    tst    r6,r4
    not    r6,r7
    bt/s   s_apron
    and    r7,r4
    mov.w  g_grass,r6
    add    r6,r8
    add    #1,r9
s_apron:
    mov.w  m_apron,r6
    tst    r6,r4
    not    r6,r7
    bt/s   s_dusa10
    and    r7,r4
    mov.w  g_apron,r6
    add    r6,r8
    add    #1,r9
s_dusa10:
    mov.w  m_dusa10,r6
    tst    r6,r4
    not    r6,r7
    bt/s   s_dusa20
    and    r7,r4
    mov.w  g_dusa10,r6
    add    r6,r8
    add    #1,r9
s_dusa20:
    mov.w  m_dusa20,r6
    tst    r6,r4
    not    r6,r7
    bt/s   s_other
    and    r7,r4
    mov.w  g_dusa20,r6
    add    r6,r8
    add    #1,r9
s_other:
    tst    r4,r4
    bt     s_done
    mov.w  g_other,r6
    add    r6,r8
    add    #1,r9
s_done:
    bra    0x060356DA
    nop
surf_flags:
    .word  0x0080           ; 0 wall strip
    .word  0x0001           ; 1 road
    .word  0x0011           ; 2 road under a roof
    .word  0x0004           ; 3 grass
    .word  0x0002           ; 4 apron (CCE 0x0003)
    .word  0x0001           ; 5
    .word  0x0001           ; 6
    .word  0x0001           ; 7 road (CCE's own courses)
    .word  0x0008           ; 8 DUSA's 80 ground (CCE 0)
    .word  0x0021           ; 9 CCE's own courses
    .word  0x0041           ; 10 CCE's own courses
    .word  0xFFFF           ; 11
    .word  0x0009           ; 12 DUSA's 09 and 41 road
    .word  0x000C           ; 13 DUSA's 0C grass
    .word  0x0100           ; 14 DUSA's 10 road
    .word  0x0200           ; 15 DUSA's 20 road
    .word  0x0012           ; 16 apron under a roof
    .word  0x0014           ; 17 grass under a roof
    .word  0x0018           ; 18 DUSA's 80 ground under a roof
    .word  0x0019           ; 19 DUSA's 09 and 41 road under a roof
    .word  0x001C           ; 20 DUSA's 0C grass under a roof
    .word  0x0110           ; 21 DUSA's 10 road under a roof
    .word  0x0210           ; 22 DUSA's 20 road under a roof

.org 0603570C
m_road:
    .word  0x0001
g_road:
    .word  0x00EE
m_grass:
    .word  0x0004
g_grass:
    .word  0x00B4           ; CCE 0x80
m_apron:
    .word  0x0002
g_apron:
    .word  0x00D2
m_dusa10:
    .word  0x0100
g_dusa10:
    .word  0x00F6
m_dusa20:
    .word  0x0200
g_dusa20:
    .word  0x00FA
    .word  0x0000
g_other:
    .word  0x0096

; Off-road drag: r0 = car; returns r4; uses r1-r3, r7, r12 as CCE's did.
; Its own space around the literal pool CCE placed inside it (0604DC92-
; 0604DCD3, loaded by the code before it).
.org 0604DC40
    mov    #0,r7
    mov    #4,r3
    mov    r0,r1
    add    #76,r1           ; corners +0x4C..+0x58
    mov.l  @r1,r2
    tst    r3,r2
    mov    r2,r12
    bt     d_c1
    add    #1,r7
d_c1:
    mov.l  @(4,r1),r2
    tst    r3,r2
    or     r2,r12
    bt     d_c2
    add    #1,r7
d_c2:
    mov.l  @(8,r1),r2
    tst    r3,r2
    or     r2,r12
    bt     d_c3
    add    #1,r7
d_c3:
    mov.l  @(12,r1),r2
    tst    r3,r2
    or     r2,r12
    bt     d_c4
    add    #1,r7
d_c4:
    tst    r7,r7            ; r7 = wheels on grass
    bt     d_none
    mov.w  d_hairpin,r1
    tst    r1,r12
    bf     d_none           ; a wheel on DUSA's 10 ground
    mov.l  d_mode,r1
    mov.b  @r1,r1
    tst    r1,r1
    bf     d_none
    mov.l  @(52,r0),r2      ; km/h
    mov.l  d_heavy,r1
    shll2  r2
    add    r2,r1
    mov.l  @r1,r4
    mov.w  d_car,r1
    bra    d_by_car
    mov.b  @(r0,r1),r2

.org 0604DCAA
d_hairpin:
    .word  0x0100           ; was 0x0004, the old code's grass bit
    .word  0x004C
d_car:
    .word  0x01C6

.org 0604DCD4
d_mode:
    .long  0x002FC21D
d_heavy:
    .long  0x002DC620

.org 0604DCDC
d_by_car:
    tst    r2,r2
    bt     d_wheels
    mov    #1,r1
    cmp/eq r1,r2
    bf     d_none           ; 2: no off-road drag
    rts
    shll   r4               ; 1: heavy x 2
d_wheels:
    mov    #2,r1
    cmp/gt r1,r7
    bt     d_three
    shar   r4               ; 1-2 wheels: heavy / 4
d_three:
    rts
    shar   r4               ; 3-4 wheels: heavy / 2
d_none:
    rts
    mov    #0,r4
