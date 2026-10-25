; Attract mode like DUSA's (docs/attract.md). Assembled into
; patches/attract.patch by tools/mkpatch.py.
;
; Music: DUSA's attract song is its CD track 3, which isn't on CCE's disc;
; make disc appends it as track 32 (and the credits jingle, DUSA's track 2,
; as track 33). The race start (060291E0) plays track 18 when it starts the
; attract demo (byte 0601335C set), track 19 for a replay, else the course's
; song, through 06030C7C -> 06007AF8, which plays a track once.
;
; Opening: CCE fades the demo in from black (the colour offset engine
; 0602F8E8, state byte 06051F55 = 1, offsets 06051F58 rising by 8 a call
; toward their targets at +12, called from the race loop at 06028DA0).
; DUSA cuts to its first frame on the song's first beat. So once the attract
; has asked for the song (music track byte 06013364 = 32; the trademark
; notice before it fades in with the same engine), the fade-in holds black
; until the CD drive reports PLAY (CR1 status 3) in
; the audio area (CR3 low byte, FAD bits 23-16, not 0: past the data
; track), then the engine's state 2 sets the offsets to their targets at
; once (it writes VDP2 itself, from the shadow). It gives up after 120
; calls (4 s) if the song never comes.
; Cave: the unreferenced function at 0603C796, after patches/camera.s's
; chase routine.

.org 060294EA
    mov    #32,r4           ; attract demo: track 18 -> 32

.org 06028EA0
    .long  attract_fade     ; was 0602F8E8, the fade engine

.org 0603C8F8
attract_fade:
    mov.l  attract_at,r0
    mov.b  @r0,r0
    tst    r0,r0
    bt     to_fade
    mov.l  state_at,r1
    mov.b  @r1,r0
    cmp/eq #1,r0
    bf     to_fade
    mov.l  offsets_at,r2
    mov.w  @r2,r0
    cmp/pz r0
    bt     to_fade          ; not fading in from black
    mov.l  track_at,r0
    mov.b  @r0,r0
    cmp/eq #32,r0
    bf     to_fade          ; the trademark notice, before the song is asked for
    mov.l  cd_at,r3
    mov.w  @r3,r0           ; CR1: status in the high byte
    shlr8  r0
    and    #15,r0
    cmp/eq #3,r0
    bf     wait
    mov.w  @(8,r3),r0       ; CR3
    tst    #255,r0
    bf     show
wait:
    mova   count,r0
    mov.b  @r0,r3
    add    #1,r3
    mov.b  r3,@r0
    extu.b r3,r3
    mov    #120,r0
    cmp/hs r0,r3
    bf     done
show:
    mov    #2,r0
    bra    to_fade
    mov.b  r0,@r1           ; state 2: the engine sets the offsets to their
                            ; targets at once, writes VDP2, and goes idle
done:
    rts
    nop
to_fade:
    mova   count,r0
    mov    #0,r1
    mov.b  r1,@r0           ; the next attract waits afresh
    mov.l  fade_at,r0
    jmp    @r0
    nop
.align 4
attract_at:
    .long  0x0601335C
state_at:
    .long  0x06051F55
offsets_at:
    .long  0x06051F58
track_at:
    .long  0x06013364       ; the music track asked for
cd_at:
    .long  0x25890018
fade_at:
    .long  0x0602F8E8
count:
    .long  0
