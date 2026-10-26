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
; notice before it fades in with the same engine), a fade in (current offset
; below its target; fades out pass through) holds black
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

; The attract's tick (06031DFA, called through this literal) runs from
; src/attract.c's blob in work RAM (DEMOTTL.BIN, loaded with the attract):
; CCE's tick, then DUSA's camera.
.org 060285AC
    .long  0x002E2780       ; was 06031DFA

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
    mov.w  @(12,r2),r0      ; target
    mov    r0,r3
    mov.w  @r2,r0           ; current
    cmp/ge r3,r0
    bt     to_fade          ; not fading in (a fade out, or none)
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

; The demo's clock. CCE's race loop runs at 30 Hz only while a tick's work
; fits in two frames; on a Saturn the busier shots take three, and a clock
; counting ticks ran behind the song. So from the cut src/attract.c points
; the VBlank-IN vector here: count the frame, then the handler it replaced
; (title_start chains its own in front; title_leave, in the race's
; teardown, gives the vector back, patches/title.s). src/attract.c reads
; the count and the saved handler at these addresses.
.org 0603C970
demo_vbl:
    mov.l  r0,@-r15
    mov.l  r1,@-r15
    mova   vbl_count,r0
    mov.l  @r0,r1
    add    #1,r1
    mov.l  r1,@r0
    mov.l  @(4,r0),r0
    mov.l  @r15+,r1
    jmp    @r0
    mov.l  @r15+,r0
.align 4
vbl_count:
    .long  0                ; 0603C984
vbl_saved:
    .long  0                ; 0603C988

; CCE's AI update for its cars (a routine per detail level, +0x98, through
; the tables at 0603E388 on the master and 0603E3DC on the slave) runs after
; src/attract.c has placed them, and moved them on by CCE's own state: a step
; along CCE's path, and the pitch and roll of the road where CCE had the car.
; The routine also prepares the car for drawing, so it still runs, but every
; level now goes through ai_gate: while attract.c holds the cars (ai_hold, in
; the attract only) it puts the car's position and angles back as they were
; placed once the routine is done; otherwise it goes straight on to CCE's
; routine. Cave: 0603CD34-0603CDD7, a function nothing branches to or points
; at, dead in DaytonaCCEReverse's sweeps and never run (master CPU code log)
; in the attract, a 1P race or a 2P race.
.org 0603E388
    .word  0xE9C0           ; ai_gate - 0603E378 (the master's bsrf), levels 0-5
    .word  0xE9C0
    .word  0xE9C0
    .word  0xE9C0
    .word  0xE9C0
    .word  0xE9C0

.org 0603E3DC
    .word  0xE96C           ; ai_gate - 0603E3CC (the slave's bsrf), levels 0-5
    .word  0xE96C
    .word  0xE96C
    .word  0xE96C
    .word  0xE96C
    .word  0xE96C

.org 0603CD34
ai_hold:
    .long  0                ; 0603CD34: src/attract.c sets it while it places the cars
ai_gate:                    ; gbr = r14 = the car, r7 = twice its level
    mov.l  hold_at,r0
    mov.l  @r0,r0
    tst    r0,r0
    bt     ai_run
    mov.l  attract_at2,r0
    mov.b  @r0,r0
    tst    r0,r0
    bt     ai_run
    sts.l  pr,@-r15
    mov.l  @(0,gbr),r0      ; the placed position and angles
    mov.l  r0,@-r15
    mov.l  @(4,gbr),r0
    mov.l  r0,@-r15
    mov.l  @(8,gbr),r0
    mov.l  r0,@-r15
    mov.l  @(12,gbr),r0     ; pitch, yaw
    mov.l  r0,@-r15
    mov.w  @(16,gbr),r0     ; roll
    mov.l  r0,@-r15
    mova   ai_routines,r0
    add    r7,r0
    add    r7,r0
    mov.l  @r0,r0
    jsr    @r0
    nop
    mov.l  @r15+,r0
    mov.w  r0,@(16,gbr)
    mov.l  @r15+,r0
    mov.l  r0,@(12,gbr)
    mov.l  @r15+,r0
    mov.l  r0,@(8,gbr)
    mov.l  @r15+,r0
    mov.l  r0,@(4,gbr)
    mov.l  @r15+,r0
    mov.l  r0,@(0,gbr)
    lds.l  @r15+,pr
    rts
    nop
ai_run:
    mova   ai_routines,r0
    add    r7,r0
    add    r7,r0
    mov.l  @r0,r0
    jmp    @r0
    nop
.align 4
hold_at:
    .long  0x2603CD34       ; ai_hold, cache-through (the slave reads it)
attract_at2:
    .long  0x0601335C
ai_routines:                ; CCE's routine for detail levels 0-5
    .long  0x0603E7B0
    .long  0x0603E7B0
    .long  0x0603E9E2
    .long  0x0603EAAA
    .long  0x0603E952
    .long  0x0603E952
