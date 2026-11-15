; The records file's extension (patches/save_ext.s): NAME.BIN's helper for the
; three bytes of 002FC087-002FC08A, one each way, now hands its stream
; pointer to the main program's, which packs them as CCE did and then the
; 64 bytes of our settings. Assembled into patches/save_ext_name.patch by
; tools/mkpatch.py.
.target DAYTONA/NAME.BIN 06028000 sh2

.org 0602E814
    mov.l  name_wptr,r4
    mov.l  name_pack,r0
    jmp    @r0
    nop
.align 4
name_wptr:
    .long  0x0603C878
name_pack:
    .long  0x060059D4       ; ext_pack

.org 0602E862
    mov.l  name_rptr,r4
    mov.l  name_unpack,r0
    jmp    @r0
    nop
.align 4
name_rptr:
    .long  0x0603C87C
name_unpack:
    .long  0x06005A10       ; ext_unpack
