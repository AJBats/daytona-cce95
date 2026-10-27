; Options > Sound > ATTRACT: ORIGINAL (DUSA's attract, docs/attract.md) or
; CCE (CCE's own, as it shipped). Assembled into patches/attract_load.patch
; by tools/mkpatch.py; patches/attract_choice.s sends the attract's load
; here.
;
; DEMOTTL.BIN holds both (tools/title_convert.py): CCE's original file in
; its first 56 sectors, with blocks that put back what our attract changed
; in RACE.BIN, then ours from sector 56, with blocks that put ours back.
; Each is a block file as 06007D94 reads (a count, then (size, address)
; pairs, then the blocks). The race start read the whole file through
; 06007D94 (060058B4, then the copy); demo_load reads only the chosen half,
; so each attract loads as long as it did on its own, and copies it out as
; 06007D94 does, colour RAM in VBlank.
;
; The choice is 002FC3AB (0: ORIGINAL), a settings byte the boot clears and
; nothing else uses; patches/attract_save_*.s keep it in the backup.
;
; Cave: GFS_Load (0600A8B2), the SBL library's, which the game never calls
; (no calls, branches or pointers to it; never run in the attract, 1P or 2P
; races). It reads a file from a sector offset (GFS_Open 0600A582, GFS_Seek
; 0600A64A, GFS_Fread 0600A95C, GFS_Close 0600A62C), as demo_load does.
; Its neighbour at 0600A8A4 keeps its literal at 0600A950.
.target DAYTONA/0 06005200 sh2

.org 0600A8B2
demo_load:                  ; r5: the buffer
    sts.l  pr,@-r15
    mov.l  r14,@-r15
    mov.l  r13,@-r15
    mov    r5,r13
    mov.l  busy_at,r1
    mov    #0,r0
    mov.b  r0,@r1           ; loading, as 060058B4
    mov.l  name_at,r4
    bsr    0x0600A3E4       ; GFS_NameToId
    nop
    bsr    0x0600A582       ; GFS_Open
    mov    r0,r4
    mov    r0,r14           ; the file
    mov.l  choice_at,r0
    mov.b  @r0,r0
    tst    r0,r0
    bf/s   read             ; CCE: its half, the file's first 56 sectors
    mov    #56,r5
    mov    r14,r4           ; ORIGINAL: ours, from sector 56 to the end
    bsr    0x0600A64A       ; GFS_Seek
    mov    #0,r6
    mov.w  k_to_end,r5
read:
    mov    r14,r4
    mov    r13,r6
    mov    #14,r7
    bsr    0x0600A95C       ; GFS_Fread
    shll16 r7               ; at most 0xE0000 bytes, as 060058B4
    bsr    0x0600A62C       ; GFS_Close
    mov    r14,r4
    mov.l  busy_at,r1
    mov    #1,r0
    mov.b  r0,@r1
    mov.l  @r13+,r1         ; the blocks
    mov    r1,r7
    shll2  r7
    shll   r7
    add    r13,r7           ; their data, after the (size, address) pairs
blocks:
    mov.l  @r13+,r6
    mov.l  @r13+,r5
    mov    r5,r0
    shlr16 r0
    mov.w  k_cram,r2
    cmp/eq r2,r0
    bf/s   words
    shlr2  r6
    mov.l  wait_at,r0       ; colour RAM in VBlank, as 06007D94
    jsr    @r0
    nop
words:
    mov.l  @r7+,r0
    dt     r6
    mov.l  r0,@r5
    bf/s   words
    add    #4,r5
    dt     r1
    bf     blocks
    mov.l  @r15+,r13
    mov.l  @r15+,r14
    lds.l  @r15+,pr
    mov.l  back_at,r0       ; the race start, after its load
    jmp    @r0
    nop
k_to_end:
    .word  0x01C0           ; sectors, as 060058B4
k_cram:
    .word  0x25F0
.align 4
busy_at:
    .long  0x06011FB8
name_at:
    .long  0x0604ECFC       ; "DEMOTTL.BIN"
choice_at:
    .long  0x002FC3AB
wait_at:
    .long  0x060056F8
back_at:
    .long  0x06029280
