; Ground contact: pitch, roll and ride height DUSA's way (CCE 060386D8,
; DUSA 06005ECC). Assembled into patches/ground_pitch.patch by tools/mkpatch.py.
;
; Both games sample the same terrain (teleport test, docs/conformance.md), but
; derive the car's attitude from different points:
;   DUSA: ground under the wheels, (+-0.55, +-1.4) in car space, and under a
;         point 12 ahead. Height = mean of the wheels. Pitch = atan((ahead -
;         rear wheels) / 13.4) when the ahead point is on ground and not level
;         with the car, else atan((front - rear wheels) / 2.8). Roll =
;         atan(side difference / 1.1).
;   CCE:  probes at (+-1.84, +3.6) and (+-1.64, -3.6), mean of those and the 4
;         body-corner contacts for height, atan(front - rear / 7.2) for pitch,
;         side difference / 3.28 for roll. On turn 3's bank this gave up to
;         2.4x DUSA's pitch (the slope force term).
; Patched: probe radius and angles moved to DUSA's wheels; height = mean of
; the 4 probes; baselines 2.8 and 1.1; the pitch call goes through a cave
; routine that adds the ahead probe. Pitch has no per-tick filter in either
; game, so nothing to convert to 30 Hz.
; Not transplanted: DUSA keeps the wheel form on course 1 from progress 220
; (0607EAD8 == 1, car +0x1EC >= 0xDC); the CCE course and progress fields
; for that place are not mapped yet.
;
; The ahead point may lie in the other half of the course's collision grid,
; so it goes through 06036B60, which picks the grid by z, not the car's grid
; (+0x12C) that the wheel probes use.
;
; Cave: the unreferenced function at 0603C304 (no calls, branches or
; pointers into 0603C2F8-0603C5CB; never executed in the race CDL).

; probes: radius 1.504 = |(0.55, 1.4)|, angle 0x0F40 = atan(0.55 / 1.4)
; either side of straight ahead (0x4000) and straight back (0xC000)
.org 0603885C
    .word  0x30C0           ; front, was 0x2CBF
.org 06038860
    .word  0xCF40           ; rear, was 0xD16B
    .word  0xB0C0           ; rear, was 0xAE95
.org 06038868
    .long  0x00018110       ; front radius, was 0x40B02 (4.04)
.org 06038884
    .long  0x00004F40       ; front, was 0xFFFF5341
.org 0603888C
    .long  0x00018110       ; rear radius, was 0x3F4BC (3.96)

; ride height: mean of the 4 probes (the corner contacts left out)
.org 0603896C
    mov    #0,r5
    nop
.org 06038976
    nop
.org 0603897C
    nop
.org 06038A1A
    .word  0x4000           ; x 1/4, was 0x2000 (x 1/8)

; pitch: r4 = rear - front as before, baseline and ahead form in the cave
.org 06038A48
    sub    r0,r2
    mov.l  r2,@r15          ; roll: side difference
    mov.l  @(4,r15),r4      ; rear - front
    mov.l  pitch_at,r3
    jsr    @r3
    nop
    nop
.org 06038B64
pitch_at:
    .long  pitch            ; was 0x73330 (7.2), the pitch baseline
.org 06038B6C
    .long  0x00011998       ; roll baseline 1.1, was 0x347AC (3.28)

; In: r4 = rear - front wheels, r8/r9 = rear probe records (height at +12),
; r14 = car, car +0x04 = new ride height. Tail-calls the atan (06047E0C)
; with r4 = drop and r5 = baseline, as the original call did.
.org 0603C304
pitch:
    sts.l  pr,@-r15
    mov.l  r4,@-r15
    mov.w  @(14,r14),r0     ; heading
    mov.w  forward,r4
    add    r0,r4
    mov.l  r4,@-r15
    mov.l  sin,r0
    jsr    @r0
    nop
    mov.l  reach,r4
    mov.l  mul,r1
    jsr    @r1
    mov    r0,r5
    mov.l  @(8,r14),r5
    add    r0,r5            ; z ahead
    mov.l  @r15,r4
    mov.l  r5,@r15
    mov.l  cos,r0
    jsr    @r0
    nop
    mov.l  reach,r4
    mov.l  mul,r1
    jsr    @r1
    mov    r0,r5
    mov.l  @r14,r4
    add    r0,r4            ; x ahead
    mov.l  @r15+,r5
    mov    r5,r6
    mov.l  rec_at,r7
    mov    #0,r0
    mov.w  r0,@(16,r7)      ; surface type 0: no ground found
    mov.l  ground,r1
    jsr    @r1
    nop
    mov.l  @r15+,r4
    mov.l  rec_at,r6
    mov.w  @(16,r6),r0
    tst    r0,r0
    bt     wheels
    mov.l  @(12,r6),r1      ; ground ahead
    mov.l  @(4,r14),r2
    cmp/eq r1,r2
    bt     wheels           ; level with the car
    mov.l  @(12,r8),r2
    mov.l  @(12,r9),r3
    add    r3,r2
    shar   r2               ; rear wheels
    sub    r1,r2
    mov    r2,r4            ; rear - ahead
    mov.l  long_base,r5
    bra    atan
    nop
wheels:
    mov.l  short_base,r5
atan:
    lds.l  @r15+,pr
    mov.l  atan2,r0
    jmp    @r0
    nop
forward:
    .word  0x4000
.align 4
reach:
    .long  0x000C0000       ; 12
long_base:
    .long  0x000D6666       ; 13.4: rear wheels to the ahead point
short_base:
    .long  0x0002CCCC       ; 2.8: wheelbase
sin:
    .long  0x06047D20
cos:
    .long  0x06047D3C
mul:
    .long  0x06048180
ground:
    .long  0x06036B60       ; ground at (r4, r6): picks the course grid half by z (r5)
atan2:
    .long  0x06047E0C
rec_at:
    .long  rec
rec:
    .long  0
    .long  0
    .long  0
    .long  0
    .long  0
