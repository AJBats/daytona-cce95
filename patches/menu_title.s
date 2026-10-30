; DUSA's title on the main menu's press-start page (docs/attract.md, "The
; menu's press-start page"). Assembled into patches/menu_title.patch by
; tools/mkpatch.py.
;
; The menu's title states (SLCT 06028000, state byte 060418A2): 0 goes to
; the press-start page (3), drawing its Press Start Button (06034CC2); 3
; waits for Start, 600 frames at most; 4 blinks the text, then goes on to
; the main menu (5, which sets it up with 0602A800, then 6 and 7) after
; Start, or fades out (8) and leaves (06005876, then 06005FC8) after the
; timeout. B on the main menu comes back to state 0. Each of these calls
; is the only use of its literal, so the three go to src/menu_title.c's
; entries, in TITLED.BIN's tail (tools/menu_title.py), which put DUSA's
; title up, take it down for the main menu, and give the VBlank handler
; back as the menu leaves; each then makes the call it replaced.
.target DAYTONA/SLCT.BIN 06028000 sh2

.org 060283BC
    .long  0x00242300       ; title_on, was 06034CC2 (state 0 to 3)
.org 060284E0
    .long  0x00242308       ; title_menu, was 0602A800 (state 5)
.org 06028578
    .long  0x00242310       ; title_leave, was 06005876 (state 8)
