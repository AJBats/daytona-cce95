; Car select shows a car on DUSA's body, in the livery of the gearbox
; under the cursor: the Gallop for the Hornet (car 1) and the secret car 9,
; and a '95 car's own (docs/liveries.md); left/right on a car with a choice
; flips it between DUSA's body and CCE's car (docs/car_select.md).
; Assembled into patches/car_pictures.patch by tools/mkpatch.py.
;
; tools/car_pictures.py puts the Gallop's picture and the code in the
; car-select screen files (loaded at 0x250000), in the secret car's
; picture's place; the code's entries are 0x2BA000 (the picture), 0x2BA004
; (gearbox moves), 0x2BA008 and 0x2BA00C (players 1 and 2 on the car list).
; The picture routine (0602F83E) switches on the player's car (002FC230 +
; player, from 0) through the table at 0602F900; case 8 (0602FA06) now
; jumps to the code and cases 0-7 share it (the code goes on to each car's
; own case, as CCE had them, for CCE's pictures). 0602FAE6 draws a
; player's gearbox cursor after every move and when the cursor first
; shows. 0602EE2C and 0602F1D2 are each player's car list input, where it
; tests up.

.target DAYTONA/SLCT.BIN 06028000 sh2

.org 0602EE2C
    mov.l  input_1p_at,r0   ; was the up test, done there
    jmp    @r0
    nop
    nop
input_1p_at:
    .long  0x002BA008

.org 0602F1D2
    mov.l  input_2p_at,r0   ; was the up test, done there
    jmp    @r0
    nop
input_2p_at:
    .long  0x002BA00C

.org 0602FA06
    mov.l  picture_at,r0    ; was case 8's draw of Sega's picture
    jmp    @r0
    nop
picture_at:
    .long  0x002BA000

.org 0602FAE6
    mov.l  gear_at,r0       ; was its first five steps, done there
    jmp    @r0
    nop
gear_at:
    .long  0x002BA004

; Every car's picture case (0-7, as 8 already) goes to the code, which
; draws a car on DUSA's body or goes on to the car's own case.
.org 0602F900
    .word  0x011E           ; the Hornet, was 0x006A
    .word  0x011E           ; the Gallop, was 0x004C
    .word  0x011E           ; Max, was 0x00C4
    .word  0x011E           ; Phoenix, was 0x0100
    .word  0x011E           ; Oriole, was 0x00E2
    .word  0x011E           ; Magic, was 0x00A6
    .word  0x011E           ; Wolf, was 0x0088
    .word  0x011E           ; Balance, was 0x002E

; The '95 cars' pictures (PICS95.BIN, tools/car_pictures.py) load with
; each car-select screen file, into work RAM 060B0000-060ECFFF, which is
; free in the menus. The menu starts the screen's load through the kernel's
; queued loader (06005C10) at 0602A42A; it queues the pictures after it for
; the four car-select screens. The car-select program's start loads its
; screen with the loader that waits (060058B4) at 06028200; it loads the
; pictures after it. Both dispatches on the screen are rewritten shorter
; to make room. The file's name goes in the old secret car picture case's
; literals (0602FA84-0602FA8F), which nothing reads now.
.org 0602A3EA
    mov.b  @r13,r0          ; 10-15: ARC, TA, TWO_P, LINK, REC, OPT
    add    #-10,r0
    mov    #6,r1
    cmp/hs r1,r0
    bt     screen_none
    add    #2,r0            ; their names from 0602A450: REC, OPT, ARC, TA, TWO_P, LINK
    cmp/hs r1,r0
    bf     screen_name
    add    #-6,r0
screen_name:
    shll2  r0
    mov.l  names_at,r1
    mov.l  @(r0,r1),r4
    jsr    @r12
    mov    r14,r5
    mov.b  @r13,r0
    add    #-10,r0
    mov    #4,r1
    cmp/hs r1,r0
    bt     screen_none      ; Records and Options have no cars
    mov.l  pics_name_at,r4
    mov.l  pics_at,r5
    jsr    @r12
    nop
screen_none:
    bra    0x0602A4A0
    nop
.align 4
names_at:
    .long  0x0602A450
pics_name_at:
    .long  0x0602FA84
pics_at:
    .long  0x060B0000

.org 060281CA
    mov.b  @r10,r0          ; 0-4: ARC, TA, TWO_P, LINK, XBANDISE
    mov    #5,r1
    cmp/hs r1,r0
    bt     start_none
    shll2  r0
    mov.l  start_names,r1
    mov.l  @(r0,r1),r4
    jsr    @r13
    mov    r11,r5
    mov.l  start_pics_name,r4
    mov.l  start_pics_at,r5
    jsr    @r13
    nop
start_none:
    bra    0x0602821C
    nop
.align 4
start_names:
    .long  0x06028278
start_pics_name:
    .long  0x0602FA84
start_pics_at:
    .long  0x060B0000

.org 0602FA84
    .long  0x50494353       ; "PICS95.BIN"
    .long  0x39352E42
    .long  0x494E0000
