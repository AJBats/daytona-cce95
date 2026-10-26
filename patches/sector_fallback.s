; The course drawing's sector for a camera off the road. Assembled into
; patches/sector_fallback.patch by tools/mkpatch.py.
;
; CCE draws the course by the sector under the camera's eye (CSn_BLK.BIN):
; the view build looks it up (0602A6EC, from 06029DA2: the quads of the
; course's sector map, around the road) and keeps its record at +0x60 of
; the camera struct; the course drawing (06029D8C) then draws a run of
; course blocks from the sector's own, as many as the record's count for
; the way the camera looks, and the blocks its record lists (0602A118). A
; camera over no sector left +0x60 at 0, and the drawing read the count and
; the list through a null record: random blocks from the BIOS's bytes, and
; too many of them. CCE's race cameras
; stay over the road; DUSA's attract cranes don't (Seaside Galaxy's
; opening hangs over the sea beside the bridge: no bridge, cars flickering,
; a few frames a second). Now, when no sector lies under the eye, the view
; build takes the sector nearest the eye (by the centre of its quad: the
; lookup is run again on that centre), and failing that the sector of the
; car the camera follows (*06052098).
;
; Cave: 0602C92A-0602CA13, a function nothing branches to or points at,
; dead in DaytonaCCEReverse's sweeps and never run (master CPU code log) in
; the attract, a 1P race or a 2P race.

.org 06029F18
    .long  sector_lookup    ; the view build's sector lookup, was 0602A6EC

.org 0602C92C
sector_lookup:              ; r13: the camera struct, r14: its eye (+0x20)
    sts.l  pr,@-r15
    mov.l  lookup_at,r0
    jsr    @r0
    nop
    mov    #96,r0           ; +0x60: the sector record under the eye
    mov.l  @(r0,r13),r0
    tst    r0,r0
    bf     sector_done
    mov.l  @(32,r13),r4     ; none: the eye's x and z
    mov.l  @(40,r13),r5
    mov.l  blk_at,r1
    mov.l  @r1,r1           ; the sector map
    mov.l  @r1,r2           ; +0: the records, 48 bytes each
    mov.l  @(4,r1),r3       ; +4: the grid, after the last record
    add    r1,r2
    add    r1,r3
    add    #-47,r3          ; past the last whole record
    mov.l  far_at,r6        ; the nearest yet (|dx| + |dz|)
    mov    #48,r12
nearest:
    mov.l  @(4,r2),r7       ; the quad's centre: halfway between corners 0 and 2
    mov.l  @(20,r2),r8
    add    r8,r7
    shar   r7
    mov.l  @(8,r2),r8
    mov.l  @(24,r2),r9
    add    r9,r8
    shar   r8
    mov    r7,r9
    sub    r4,r9
    cmp/pz r9
    bt     dx_abs
    neg    r9,r9
dx_abs:
    mov    r8,r10
    sub    r5,r10
    cmp/pz r10
    bt     dz_abs
    neg    r10,r10
dz_abs:
    add    r10,r9
    cmp/hs r6,r9
    bt     next_sector
    mov    r9,r6
    mov    r7,r11
    mov    r8,r1
next_sector:
    add    r12,r2
    cmp/hs r3,r2
    bf     nearest
    add    #-12,r15         ; look up again from that centre
    mov.l  r11,@r15
    mov.l  r1,@(8,r15)
    mov    r15,r14
    mov.l  lookup_at,r0
    jsr    @r0
    nop
    add    #12,r15
    mov    #96,r0
    mov.l  @(r0,r13),r0
    tst    r0,r0
    bf     sector_done
    mov.l  follow_at,r14    ; still none: the car the camera follows
    mov.l  @r14,r14
    mov.l  lookup_at,r0
    jsr    @r0
    nop
sector_done:
    lds.l  @r15+,pr
    rts
    nop
.align 4
lookup_at:
    .long  0x0602A6EC
follow_at:
    .long  0x06052098
blk_at:
    .long  0x06054934
far_at:
    .long  0x7FFFFFFF
