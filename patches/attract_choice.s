; The attract's load goes to patches/attract_load.s, which reads the half of
; DEMOTTL.BIN for Options > Sound > ATTRACT (ORIGINAL or CCE). Assembled
; into patches/attract_choice.patch by tools/mkpatch.py.
;
; The race start loads the attract's file with 06007D94 (r4 the name, r5
; the buffer, 0x220000 in r13), then goes on at 06029280. Its literal for
; the name now holds demo_load, which takes the name itself and comes back
; to 06029280.

.org 06029272
    mov.l  demo_load_at,r0  ; was the name, into r4
    jmp    @r0              ; was a branch to the load's call
    mov    r13,r5

.org 060293DC
demo_load_at:
    .long  0x0600A8B2       ; was 0604ECFC, "DEMOTTL.BIN"
