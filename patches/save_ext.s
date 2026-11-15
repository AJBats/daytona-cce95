; The records file's extension: 64 bytes of our own settings in the save,
; kept in RAM at 002FE7C0 (docs/backup.md). Assembled into
; patches/save_ext.patch by tools/mkpatch.py.
;
; The records file (DAYULT_B2_0 since tools/save_name.py, CCE's DAYTONA96_0)
; is 4029 bytes of records and settings and a 4-byte sum. CCE packs 3871 of
; them, in BKUP.BIN, NAME.BIN and SLCT.BIN alike: the records, the settings
; bytes, three bytes from 002FC087-002FC08A (a helper of its own in each
; program), then the ghost and lap tables. Each program's helper now jumps
; here with its stream pointer in r4 (patches/save_ext_bkup.s, _name.s,
; _slct.s): the three bytes as CCE packed them, then the extension byte for
; byte, so everything after moves 64 bytes on and the file ends at 3935. The
; file's name is our own, so no CCE save is ever read with this layout.
;
; The extension (002FE7C0-002FE7FF) is the end of the stretch CCE's boot
; clears (002FC000-002FE7FF, 06005368), which nothing else reads or writes;
; it reads as zeros without a save. Zero is every setting's default.
;   +0  steering, player 1: 0 AUTO, 1 WHEEL, 2 STICK (patches/steering_choice.s)
;   +1  steering, player 2
;   the rest: not used yet
;
; Cave: after the crash screen's boot load (patches/crash.s), in the file
; load nothing calls (06005950-06005A62).
.target DAYTONA/0 06005200 sh2

.org 060059D4
ext_pack:                   ; r4: the write pointer's address
    mov.l  @r4,r6
    mov.l  ext_087,r5
    mov.b  @(1,r5),r0       ; 002FC088
    extu.b r0,r1
    shlr2  r1
    mov.b  @r5,r2           ; 002FC087
    shll2  r2
    shll   r2
    or     r1,r2
    mov.b  r2,@r6           ; 087 << 3 | 088 >> 2
    and    #3,r0
    shll2  r0
    shll2  r0
    shll   r0
    mov    r0,r2
    mov.b  @(2,r5),r0       ; 002FC089
    or     r2,r0
    mov.b  r0,@(1,r6)       ; (088 & 3) << 5 | 089
    mov.b  @(3,r5),r0
    mov.b  r0,@(2,r6)       ; 002FC08A
    add    #3,r6
    mov.l  ext_at,r5
    mov    #64,r2
pack_copy:
    mov.b  @r5+,r0
    mov.b  r0,@r6
    dt     r2
    bf/s   pack_copy
    add    #1,r6
    rts
    mov.l  r6,@r4

ext_unpack:                 ; r4: the read pointer's address
    mov.l  @r4,r6
    mov.l  ext_087,r5
    mov.b  @r6,r0
    extu.b r0,r0
    mov    r0,r1
    shlr2  r1
    shlr   r1
    mov.b  r1,@r5           ; 002FC087: byte 0 >> 3
    and    #7,r0
    shll2  r0
    mov    r0,r1
    mov.b  @(1,r6),r0
    extu.b r0,r0
    mov    r0,r2
    shlr2  r2
    shlr2  r2
    shlr   r2
    or     r2,r1
    and    #31,r0
    mov.b  r0,@(2,r5)       ; 002FC089: byte 1 & 31
    mov    r1,r0
    mov.b  r0,@(1,r5)       ; 002FC088: (byte 0 & 7) << 2 | byte 1 >> 5
    mov.b  @(2,r6),r0
    mov.b  r0,@(3,r5)       ; 002FC08A: byte 2
    add    #3,r6
    mov.l  ext_at,r5
    mov    #64,r2
unpack_copy:
    mov.b  @r6+,r0
    mov.b  r0,@r5
    dt     r2
    bf/s   unpack_copy
    add    #1,r5
    rts
    mov.l  r6,@r4
.align 4
ext_087:
    .long  0x002FC087
ext_at:
    .long  0x002FE7C0
