; Options > Sound > ATTRACT kept in the backup: BKUP.BIN's copy of the settings
; pack and unpack. Assembled into patches/attract_save_bkup.patch by
; tools/mkpatch.py. BKUP.BIN, NAME.BIN and SLCT.BIN each carry the same two
; routines; patches/attract_save_bkup.s, _name.s and _slct.s are the same
; but for where they sit.
;
; The settings go to the backup packed into bytes. The second holds the
; time compare and section lap bits (002FC39B-002FC39E) in bits 7-4 and the
; ghost type (002FC39F, 0-6) in bits 3-0; unpacking keeps the ghost's
; bits 2-0. The attract's choice (002FC3AB, patches/attract_load.s) now
; rides in bit 3, so a backup from before it reads as ORIGINAL (0). Both
; byte sequences are rewritten shorter, bit by bit, to make the room.
.target DAYTONA/BKUP.BIN 06028000 sh2

.org 06028FAC
    mov.b  @r6,r2           ; arcade time compare (002FC39B)
    shll   r2
    mov.b  @(1,r6),r0       ; section lap
    or     r0,r2
    shll   r2
    mov.b  @r5,r0           ; time attack time compare (002FC39D)
    or     r0,r2
    shll   r2
    mov.b  @(1,r5),r0       ; section lap
    or     r0,r2
    shll   r2
    mov.l  pack_39f,r1
    mov.b  @(12,r1),r0      ; the attract (002FC3AB)
    or     r0,r2
    shll2  r2
    shll   r2
    mov.b  @r1,r0           ; ghost type
    or     r0,r2
    mov.l  pack_3a2,r5      ; the next byte's
    mov.b  r2,@r3
    nop
    nop
    nop
    nop

.org 06029090
pack_39f:
    .long  0x002FC39F
pack_3a2:
    .long  0x002FC3A2

.org 06029570
    mov.b  @r0,r1           ; the byte; r5: 002FC39B
    mov.l  unpack_39f,r3
    mov    r1,r0
    and    #7,r0
    mov.b  r0,@r3           ; ghost type
    mov    r1,r0
    shlr2  r0
    shlr   r0
    and    #1,r0
    mov.b  r0,@(12,r3)      ; the attract (002FC3AB)
    mov    r1,r0
    shlr2  r0
    shlr2  r0
    and    #1,r0
    mov.b  r0,@(3,r5)       ; time attack section lap
    mov    r1,r0
    shlr2  r0
    shlr2  r0
    shlr   r0
    and    #1,r0
    mov.b  r0,@(2,r5)       ; time attack time compare
    mov    r1,r0
    shlr2  r0
    shlr2  r0
    shlr2  r0
    and    #1,r0
    mov.b  r0,@(1,r5)       ; arcade section lap
    mov    r1,r0
    shlr2  r0
    shlr2  r0
    shlr2  r0
    shlr   r0
    and    #1,r0
    mov.b  r0,@r5           ; arcade time compare
    mov.l  unpack_3a2,r5    ; the next byte's
    nop
    nop
    nop

.org 060296A0
unpack_39f:
    .long  0x002FC39F
.org 060296AC
unpack_3a2:
    .long  0x002FC3A2
