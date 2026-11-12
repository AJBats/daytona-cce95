! The crash screen's ways in (src/crash.c has the screen): the CPU exceptions
! on both CPUs, and the VBlank-IN interrupt's freeze watchdog. Built with
! src/crash.c into DAYTONA/CRASH.BIN by tools/crash.py.
!
! Every way in puts the interrupted code's registers on its stack under the
! CPU's exception frame (PC, SR), 21 words from the stack pointer up:
! MACH, MACL, GBR, R0-R13, PR, R14, PC, SR. R15 as it was is past them.

! The header patches/crash.s reads: a magic word, crash_init, and
! crash_max_still for tests (tools/crash.py prints their addresses).
    .section .text.entry
    .align 2
    .long   0x43525348          ! 'CRSH'
    .long   _crash_init
    .long   _crash_max_still

    .section .text
    .align 2

! An exception: R14 goes where the frame wants it, then carries the vector.
    .macro EXC name, vector, common
    .global \name
\name:
    mov.l   r14,@-r15
    bra     \common
    mov     #\vector,r14
    .endm

    EXC _crash_m4, 4, master
    EXC _crash_m6, 6, master
    EXC _crash_m9, 9, master
    EXC _crash_m10, 10, master
    EXC _crash_s4, 4, slave
    EXC _crash_s6, 6, slave
    EXC _crash_s9, 9, slave
    EXC _crash_s10, 10, slave

! The rest of the frame, R13 down; each way in saves PR first.
push:
    mov.l   r13,@-r15
    mov.l   r12,@-r15
    mov.l   r11,@-r15
    mov.l   r10,@-r15
    mov.l   r9,@-r15
    mov.l   r8,@-r15
    mov.l   r7,@-r15
    mov.l   r6,@-r15
    mov.l   r5,@-r15
    mov.l   r4,@-r15
    mov.l   r3,@-r15
    mov.l   r2,@-r15
    mov.l   r1,@-r15
    mov.l   r0,@-r15
    stc.l   gbr,@-r15
    sts.l   macl,@-r15
    rts
    sts.l   mach,@-r15

! The main CPU draws the screen there and then, on its own stack (the calls
! that led here stay above the frame).
master:
    sts.l   pr,@-r15
    bsr     push
    nop
    mov     #-16,r0
    extu.b  r0,r0               ! 0xF0: every interrupt masked
    ldc     r0,sr
    mov     r15,r4              ! the frame
    mov     r15,r5
    add     #84,r5              ! R15 as it was
    mov     r14,r6              ! the vector
    mov.l   report,r0
    jsr     @r0
    mov     #0,r7               ! kind 0: the main CPU

! The second CPU leaves its frame where it is and stops, its vector and
! then the frame's address in crash_slave (through the cache-through
! mirror): the main CPU's next VBlank draws it from there.
slave:
    sts.l   pr,@-r15
    bsr     push
    nop
    mov     #-16,r0
    extu.b  r0,r0
    ldc     r0,sr
    mov.l   slave_at,r1
    mov.l   r14,@(4,r1)
    mov.l   r15,@r1
1:  bra     1b
    nop

    .align 2
report:
    .long   _crash_report
slave_at:
    .long   _crash_slave + 0x20000000

! VBlank-IN, in front of CCE's handler (06005568), which the attract's and
! the title's handlers chain to in turn: the frame, then crash_vbl (C),
! which doesn't return when its watchdog or the second CPU's flag fires.
    .global _crash_vbl_entry
_crash_vbl_entry:
    mov.l   r14,@-r15
    sts.l   pr,@-r15
    bsr     push
    nop
    mov.l   crash_vbl,r0
    jsr     @r0
    mov     r15,r4
    lds.l   @r15+,mach
    lds.l   @r15+,macl
    ldc.l   @r15+,gbr
    mov.l   @r15+,r0
    mov.l   @r15+,r1
    mov.l   @r15+,r2
    mov.l   @r15+,r3
    mov.l   @r15+,r4
    mov.l   @r15+,r5
    mov.l   @r15+,r6
    mov.l   @r15+,r7
    mov.l   @r15+,r8
    mov.l   @r15+,r9
    mov.l   @r15+,r10
    mov.l   @r15+,r11
    mov.l   @r15+,r12
    mov.l   @r15+,r13
    lds.l   @r15+,pr
    mov.l   @r15+,r14
    mov.l   r0,@-r15            ! R0 again for the jump, as patches/attract.s's demo_vbl
    mov.l   cce_vbl,r0
    jmp     @r0
    mov.l   @r15+,r0

    .align 2
crash_vbl:
    .long   _crash_vbl
cce_vbl:
    .long   0x06005568
