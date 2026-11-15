; The records file's extension (patches/save_ext.s): BKUP.BIN's helper for the
; three bytes of 002FC087-002FC08A, one each way, now hands its stream
; pointer to the main program's, which packs them as CCE did and then the
; 64 bytes of our settings. Assembled into patches/save_ext_bkup.patch by
; tools/mkpatch.py.
.target DAYTONA/BKUP.BIN 06028000 sh2

.org 06034E80
    mov.l  bkup_wptr,r4
    mov.l  bkup_pack,r0
    jmp    @r0
    nop
.align 4
bkup_wptr:
    .long  0x06036F50
bkup_pack:
    .long  0x060059D4       ; ext_pack

.org 06034ECE
    mov.l  bkup_rptr,r4
    mov.l  bkup_unpack,r0
    jmp    @r0
    nop
.align 4
bkup_rptr:
    .long  0x06036F54
bkup_unpack:
    .long  0x06005A10       ; ext_unpack
