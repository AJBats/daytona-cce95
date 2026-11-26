; The slave CPU updates three of every four AI cars, and the next tick
; waits for it before it starts. Assembled into patches/ai_split.patch by
; tools/mkpatch.py.
;
; After the race program the master starts the slave on its half of CCE's
; AI cars (0603E394) and updates its own (0603E340), every other car in
; the list by its +0xC1, then marks the list ready without waiting for the
; slave. In the Three Seven attract (calibrated Mednafen) that was the
; master's last 3.8 ms of the tick, against a deadline it missed by a
; fraction of that, while the slave sat idle for the last 6 ms. Now each
; loop takes its cars by their place from the list's end (r13): the master
; every fourth (r13 a multiple of 4), the slave the rest. +0xC1 still
; splits the cars' drawing (patches/car_job.s).
;
; The slave's longer share may run on past the list going out, as its
; half did when it had the dearer cars, but it must be done before the
; next tick moves or places any car (src/attract.c's placing, then the
; AI's own reads): the race program's first call, the timer zeroed
; (0600730A from 06028170), now first waits for the slave (0600751C),
; which is idle by then unless it is still on the AI.

.org 0603E35A
    mov    r13,r0           ; was mov.b @(193,gbr),r0
    .word  0xC803           ; tst #3,r0 (was tst r0,r0): every fourth car the master's

.org 0603E3AE
    mov    r13,r0           ; the slave's loop: the others (its bt skips the master's)
    .word  0xC803           ; tst #3,r0

.org 06028220
    .long  tick_start       ; was 0600730A

.cave 0603E6C0 0603E6D7
.org 0603E6C0
tick_start:
    sts.l  pr,@-r15
    mov.l  wait_at,r0
    jsr    @r0
    nop
    lds.l  @r15+,pr
    mov.l  frc_at,r0
    jmp    @r0
    nop
.align 4
wait_at:
    .long  0x0600751C
frc_at:
    .long  0x0600730A
