; Options > Sound > ATTRACT : ORIGINAL / CCE (docs/attract.md). Assembled
; into patches/attract_menu.patch by tools/mkpatch.py.
;
; The Sound page (SLCT.BIN) keeps the cursor's row in 06053954, 10 for
; SOUND MODE to 19 for EXIT; 060312D0 draws the page's text for a row and
; 0603182E takes the page's input. Both jump to tools/options_attract.py's
; code, which OPT.DAT carries to 0x2AD468 while Options is up: ATTRACT is
; row 20, between S.E. TEST and EXIT, which goes a row down to make room.

.target DAYTONA/SLCT.BIN 06028000 sh2

.org 060312D0
    mov.l  draw_at,r0       ; was the draw's first steps, done there
    jmp    @r0
    nop
    nop
draw_at:
    .long  0x002AD468

.org 0603182E
    mov.l  input_at,r0      ; was the input's first steps, done there
    jmp    @r0
    nop
input_at:
    .long  0x002AD46C

.org 0603FC76
    .word  0x0038           ; EXIT's row, was 0x34
