; The course drawing's sector for a camera off the road. Assembled into
; patches/sector_fallback.patch by tools/mkpatch.py.
;
; CCE draws the course from a visibility list per sector (CSn_BLK.BIN): the
; view build looks up the sector under the camera's eye (0602A6EC, from
; 06029DA2: the quads of the course's sector map, around the road) and
; keeps its record at +0x60 of the camera struct, and the course drawing
; (0602A118) draws the blocks its list names. A camera over no sector left
; +0x60 at 0, and the drawing read its list through a null record: random
; blocks from the BIOS's bytes, and too many of them. CCE's race cameras
; stay over the road; DUSA's attract cranes don't (Seaside Galaxy's
; opening hangs over the sea beside the bridge: no bridge, cars flickering,
; a few frames a second). Now, when no sector lies under the eye, the
; sector comes from the car the camera follows (*06052098).
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
    mov.l  follow_at,r14    ; none: the sector of the car the camera follows
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
