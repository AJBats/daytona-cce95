; Options > KEY CONFIG > STEERING : AUTO / WHEEL / STICK (patches/steering_choice.s).
; Assembled into patches/steering_menu.patch by tools/mkpatch.py.
;
; The page's code (SLCT.BIN 06031AE8) jumps to tools/options_keys.py's,
; which OPT.DAT carries to 002B1000 while Options is up:
; - 06032378, the draw of a player's TYPE boxes, ends there instead of its
;   epilogue, to draw the player's STEERING row as well (on the page's first
;   draw, when a controller changes and when the type steps);
; - the page's input calls there before its loop over the players, for left
;   and right. The call takes the loop's first two steps' place: their
;   literal (002FD72B) points at the routine instead, which sets what they
;   set, and the loop's own first step runs in the call's delay slot.

.target DAYTONA/SLCT.BIN 06028000 sh2

.org 06031C2E
    jsr    @r12             ; was mov r8,r14
.org 06031CA8
    .long  0x002B1004       ; kc_sides, was 002FD72B (for mov.l at 06031C2C)

.org 06032410
    mov.l  tail_at,r0       ; was the epilogue
    jmp    @r0
    mov    r10,r4           ; the player
    nop
tail_at:
    .long  0x002B1000       ; kc_tail
