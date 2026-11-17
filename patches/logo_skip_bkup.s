; Any button hurries the logos before the backup check (patches/logo_skip.s):
; BKUP.BIN's side. Assembled into patches/logo_skip_bkup.patch by
; tools/mkpatch.py.
;
; The frame routine's check that the state is inside its switch's table
; becomes the jump to logo_skip, which makes the same check. The fade routine
; no longer sets its step to 3 each frame; logo_skip sets it before.
.target DAYTONA/BKUP.BIN 06028000 sh2

.org 060280CA
    mov.l  bkup_logo_skip,r1    ; was the state check
    jmp    @r1
    nop
.align 4
bkup_logo_skip:
    .long  0x06007E0E           ; logo_skip

.org 0602CE22
    nop                         ; was mov.w r3,@r12, the step of 3
