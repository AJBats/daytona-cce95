; Any button hurries the logos BKUP.BIN shows before the backup check: the
; SEGA SPORTS logo and the trademark notice fading in (and, after the attract
; times out, the logos it shows again). Assembled into patches/logo_skip.patch
; by tools/mkpatch.py; BKUP.BIN's side is patches/logo_skip_bkup.s.
;
; BKUP.BIN's frame routine (06028000) steps a state (06036F28) through the
; logos on frame counts (0603E2DE): states 1-3 a picture fading in (to exactly
; 85), holding (past 120) and fading out (past 85), 4-6 the SEGA SPORTS logo
; the same way (fading in past 85), 7 the trademark fading in (past 85). Its
; fades (0602CE0C) step the brightness by 3 a frame, 85 frames from black.
; Nothing else happens in those states; the backup check comes after (states
; 11 and 12) and is not touched.
;
; Each frame the routine comes here before its switch, with the state in r0.
; A button pressed in states 1-7 (060072C6, pressed this frame) starts the
; hurry: from then on the frame counts go 5 a frame and the fades step 15, so
; each wait and fade takes a fifth as long and the logos still show. State 0,
; BKUP's first frame, clears it. Outside states 1-7 the fades step CCE's 3
; (logo_skip_bkup.s takes the step's store out of the fade routine).
;
; Cave: CCE's exception message routine (06007E0E-06007EA3). Only CCE's
; exception stubs (0600737C-060073A7) call it, and the crash screen's vectors
; (patches/crash.s, installed after CCE's) replace those for good.
.target DAYTONA/0 06005200 sh2

.org 06007E0E
logo_skip:                  ; r0: the state; r13: its address; r14: the frame count's
    mov    #15,r1
    cmp/hs r1,r0
    bt     ls_past          ; outside the switch's table, as CCE
    mov.l  ls_flag,r2
    tst    r0,r0
    bf     ls_state
    mov    #0,r1
    mov.b  r1,@r2           ; state 0, BKUP's first frame: no hurry yet
ls_state:
    mov    #3,r1            ; the fade's step, CCE's
    add    #-1,r0
    tst    #0xF8,r0         ; states 1-8 (8 never comes): the logos
    bf/s   ls_step
    add    #1,r0
    mov.b  @r2,r1
    tst    r1,r1
    bf     ls_fast
    mov.l  ls_pad,r1
    mov.w  @r1,r1           ; buttons pressed this frame
    tst    r1,r1
    bt/s   ls_step
    mov    #3,r1
    mov    #1,r1
    mov.b  r1,@r2           ; any button: hurry from here on
ls_fast:
    mov.w  @r14,r1          ; the frame count goes 5 a frame (the state adds 1)
    add    #4,r1
    cmp/eq #1,r0            ; state 1 waits for exactly 85
    bf     ls_count
    mov    #84,r2
    cmp/gt r2,r1
    bf     ls_count
    mov    r2,r1
ls_count:
    mov.w  r1,@r14
    mov    #15,r1           ; and the fades step 15
ls_step:
    mov.l  ls_fade,r2
    mov.w  r1,@r2
    mov.l  ls_resume,r1
    jmp    @r1
    nop
ls_past:
    mov.l  ls_out,r1
    jmp    @r1
    nop
.align 4
ls_flag:
    .long  ls_hurry
ls_pad:
    .long  0x060072C6
ls_fade:
    .long  0x0603E2EC       ; the fade's step
ls_resume:
    .long  0x060280D4       ; the switch
ls_out:
    .long  0x060282E4       ; past it
ls_hurry:
    .byte  0
