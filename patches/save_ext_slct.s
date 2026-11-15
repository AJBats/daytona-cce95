; The records file's extension (patches/save_ext.s): SLCT.BIN's helper for the
; three bytes of 002FC087-002FC08A, one each way, now hands its stream
; pointer to the main program's, which packs them as CCE did and then the
; 64 bytes of our settings. Assembled into patches/save_ext_slct.patch by
; tools/mkpatch.py.
.target DAYTONA/SLCT.BIN 06028000 sh2

.org 06037A24
    mov.l  slct_wptr,r4
    mov.l  slct_pack,r0
    jmp    @r0
    nop
.align 4
slct_wptr:
    .long  0x060539CC
slct_pack:
    .long  0x060059D4       ; ext_pack

.org 06037A72
    mov.l  slct_rptr,r4
    mov.l  slct_unpack,r0
    jmp    @r0
    nop
.align 4
slct_rptr:
    .long  0x060539D0
slct_unpack:
    .long  0x06005A10       ; ext_unpack
