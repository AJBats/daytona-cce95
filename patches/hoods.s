; The in-car view's hood of a car on DUSA's body is ours, in its '95
; livery or DUSA's own, in the paint of the gearbox it races with
; (docs/hoods.md). Assembled into patches/hoods.patch by tools/mkpatch.py.
;
; The race load (06028DD6) loads the hood picture by car (060540B6 + 6 x
; player, from 0): with one player through 06033B62 (r4 = car; the player
; racing is 002FC21C), with two through 06033BD6 for each (r4 = player,
; r5 = car). Both were switches over CCE's nine names, HORNET.BIN ...
; OLD_DAYT.BIN and HORNET2P.BIN ... OLD_DAY2.BIN, into the file loads: one
; player's 06007D94 (the file to 0x220000, then each part to its address),
; two players' 06033CBE (the same into each player's half of VRAM and the
; colours, 128 added to player 2's). They are now one routine at the same
; entries. A car on DUSA's body (patches/car_choice.s's is_dusa) whose
; entry in OURS is its digit loads HOOD<digit><A|M><1|2>P.BIN
; (tools/hoods.py), by the gearbox (060540B8 + 6 x player, 0 automatic)
; and the player count; any other car loads CCE's file, named from the
; tables of the names' places after 0604F588. No car past the secret car
; loads one, as before.
;
; The switches' code, 06033B62-06033C2F, and their name literals after the
; pool the functions before them share, 06033C5C-06033C93, hold it; the
; name is written in place in NAME, in work RAM like the rest of RACE.BIN.

.org 06033B62
hood_1p:                    ; r4 = the car
    mov.l  racer_at,r5
    mov    r4,r7
    mov.b  @r5,r5           ; the player racing
    mov    #0,r6
hood:                       ; r5 = player, r6 = 1 with two players, r7 = car
    extu.b r7,r7
    mov    #8,r0
    cmp/hi r0,r7
    bt     hood_none        ; past the secret car: none, as CCE
    sts.l  pr,@-r15
    mov.l  r8,@-r15
    mov.l  r9,@-r15
    mov.l  r10,@-r15
    mov    r5,r8            ; the player
    mov    r6,r9            ; two players
    mov    r7,r10           ; the car
    mov.l  is_dusa_at,r0
    jsr    @r0
    mov    r5,r1
    bf     hood_cce
    mova   ours,r0
    mov.b  @(r0,r10),r0
    tst    r0,r0
    bt     hood_cce
    mov.l  name_at,r4
    mov.b  r0,@(4,r4)       ; the car's digit
    mov    r8,r0
    shll   r0
    add    r8,r0
    shll   r0               ; player x 6
    mov.l  gears_at,r1
    mov.b  @(r0,r1),r0
    tst    r0,r0
    mov    #0x41,r0         ; 'A'
    bt     hood_gear
    mov    #0x4D,r0         ; 'M'
hood_gear:
    mov.b  r0,@(5,r4)
    mov    r9,r0
    add    #0x31,r0         ; '1' or '2' players
    bra    hood_load
    mov.b  r0,@(6,r4)
hood_cce:                   ; CCE's name: its place, one player's nine then two players'
    mov    r9,r0
    shll2  r0
    shll   r0
    add    r9,r0
    add    r10,r0
    mov    r0,r1
    mova   names,r0
    mov.b  @(r0,r1),r4
    extu.b r4,r4
    mov.l  names_at,r1
    bra    hood_load
    add    r1,r4

.org 06033BD6
hood_2p:                    ; r4 = player, r5 = the car
    mov    r5,r7
    mov    r4,r5
    bra    hood
    mov    #1,r6
hood_load:                  ; r4 = the name
    mov.l  buffer_at,r5
    mov    r9,r0
    shll2  r0
    mov    r0,r1
    mova   loads,r0
    mov.l  @(r0,r1),r0
    jsr    @r0
    mov    r8,r6            ; the player, for two players' load
    mov.l  @r15+,r10
    mov.l  @r15+,r9
    mov.l  @r15+,r8
    lds.l  @r15+,pr
hood_none:
    rts
    nop

.align 4
racer_at:
    .long  0x002FC21C       ; the player racing, one player
is_dusa_at:
    .long  0x060334FC       ; patches/car_choice.s: T = player r1's car on DUSA's body
gears_at:
    .long  0x060540B8       ; each player's gearbox, 6 bytes apart: 0 automatic
name_at:
    .long  name
names_at:
    .long  0x0604F588       ; CCE's first hood name, BALANCE.BIN
buffer_at:
    .long  0x00220000       ; where both loads read the file
loads:
    .long  0x06007D94       ; one player's
    .long  0x06033CBE       ; two players'
ours:                       ; a byte a car from 0: the digit of our hood, or none
    .word  0x0000           ; Hornet, Gallop
    .word  0x0034           ; Max, Phoenix
    .word  0x0000           ; Oriole, Magic
    .word  0x0000           ; Wolf, Balance
    .word  0x0000           ; the secret car

.org 06033C5C
name:                       ; HOOD<digit><A|M><1|2>P.BIN
    .long  0x484F4F44       ; HOOD
    .long  0x34413150       ; 4A1P
    .long  0x2E42494E       ; .BIN
    .long  0x00000000
names:                      ; CCE's names' places after 0604F588, by car from 0
    .word  0x180C           ; one player: HORNET, GALLOP
    .word  0x5448           ; MAX, PHENIX
    .word  0x3C30           ; ORIOLE, MAGIC
    .word  0x2400           ; WOLF, BALANCE
    .word  0x5C8C           ; OLD_DAYT; two players: HORNET2P
    .word  0x7CD4           ; GALLOP2P, MAX2P
    .word  0xC4B4           ; PHENIX2P, ORIOLE2P
    .word  0xA89C           ; MAGIC2P, WOLF2P
    .word  0x6CE0           ; BALANC2P, OLD_DAY2
