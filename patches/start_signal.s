; The start signal (the lights and the countdown board) clear of the car,
; where DUSA's are. Assembled into patches/start_signal.patch by
; tools/mkpatch.py.
;
; At a standing start CCE hangs three lights in front of the camera and
; shows the count on a dot-matrix board under them. DUSA's camera (patches/
; camera.s: lens 160 for CCE's 224, the projection centre 23 lines lower)
; put both on the car's roof in 1P: the lights behind it, the board, on the
; HUD layer, over it. DUSA hangs its lights above the car and its board
; beside the road on the left. Two-player keeps CCE's camera and both.
;
; Lights: 060431C6 starts a player's lights at 060515F4's (0, 4, 17) in
; camera space (units), with the count at 225; 06043216 lowers them 0.05
; and brings them 1/6 closer a tick until 165, to (0, 1, 7), and 06043384
; draws them there. 1P now starts them 1.5 higher, so they stop at
; (0, 2.5, 7): 57 lines above the projection centre, where CCE (1 x 224 /
; 7 lines above its centre, 32 lines higher) and DUSA show them.
;
; Board: 0602EFE4 draws it, 5 x 5 cells of NBG2 (priority 6, above every
; sprite): 1P at the literal 0602F108 (cells 19-23, rows 12-16), 2P at row
; 6 + 14 x player from the literal 0602F10C (cell 19). Its task kept the
; row at +18 for the clear (0602F092: row x 128 + 0602F10C's base); it now
; keeps the byte offset from that base, so the clear needs no shifts and
; 1P's board can go elsewhere: cells 8-12, rows 8-12 (64-104 on screen,
; both ways), left of the lights, where DUSA's board shows on its grid.
;
; Cave: 06030DEE-06030E31, a function nothing branches to or points at,
; dead in DaytonaCCEReverse's sweeps and never run in the CDLs.

.org 060431D0               ; lights start: after the player's offset
    mov.l  lights_go,r3
    sts    macl,r4
    jmp    @r3
    exts.b r4,r4            ; r4: the player x 56, r2: 06054044

.org 060432BC
lights_go:
    .long  lights_start     ; was 060515F4, the start's only reference

.org 06030DEE
lights_start:
    add    r2,r4            ; the player's lights
    mov.l  start_at,r3
    mov.l  @r3+,r1
    mov.l  r1,@(4,r4)       ; x
    mov.l  @r3+,r1
    mov.l  two_p_at,r2
    mov.b  @r2,r2
    tst    r2,r2
    bf     lights_y
    mov    #3,r2            ; 1P: 1.5 higher
    shll16 r2
    shar   r2
    add    r2,r1
lights_y:
    mov.l  r1,@(8,r4)       ; y
    mov.l  @r3,r1
    mov.l  r1,@(12,r4)      ; z
    mov    #64,r1
    shll8  r1
    mov.l  r1,@(52,r4)      ; +52: 0, +54: 0x4000, as before
    mov    #-31,r2
    extu.b r2,r2
    mov.w  r2,@r4           ; the count: 225
    rts
    lds.l  @r15+,macl
    .align 4
start_at:
    .long  0x060515F4       ; CCE's start, (0, 4, 17)
two_p_at:
    .long  0x0605492A       ; two-player flag

.org 0602F042               ; first board task (1P, or 2P player 1)
    mov.w  board_1p,r0
    tst    r2,r2            ; r2: the two-player flag
    bt     board_set
    mov    #3,r0            ; 2P player 1: row 6 (6 x 128)
    shll8  r0
board_set:
    mov.w  r0,@(2,r5)

.org 0602F05E               ; second board task (2P player 2)
    mov    #16,r0
    mov    #40,r2
    mov.b  r2,@(r0,r4)      ; +16: the count, as before
    mov    #10,r0           ; row 20 (20 x 128)
    shll8  r0
    mov.w  r0,@(18,r4)
    bra    0x0602F072       ; on to the task's code
    mov.l  r3,@(12,r4)

.org 0602F09E               ; the clear: the base plus the task's offset
    nop
    nop
    nop
    nop

.org 0602F0BE
board_1p:
    .word  0x03EA           ; 1P: row 8, cell 8 (0x25E6A410 - 0x25E6A026)

.org 0602F108
    .long  0x25E6A410       ; 1P board: NBG2 map row 8, cell 8
