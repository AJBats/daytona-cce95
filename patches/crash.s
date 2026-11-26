; The crash screen (src/crash.c, tools/crash.py) loaded at boot. Assembled
; into patches/crash.patch by tools/mkpatch.py.
;
; CCE's kernel calls its init (06005308) once, from its entry (0600521A),
; with interrupts on. It comes here instead: the init as before, then
; DAYTONA/CRASH.BIN through the kernel's own file load (060058B4) into low
; work RAM at 00200000, which the init has just cleared and nothing uses
; until the first race (its replay buffer), and from there to CRASH_AT.
; The load reads whole sectors, and the file's room ends where the main
; program's code starts (060191A8), hence the stop on the way. Then the
; scratch is cleared again, the cache's lines for the blob are purged, and
; the blob's crash_init installs the exception vectors and the VBlank
; watchdog. A disc without the file gets no crash screen.
; Cave: 06005950-06005A62, a file load with error text that nothing calls
; (no calls, branches or pointers to it in any of CCE's programs).
.target DAYTONA/0 06005200 sh2

.org 0600521A
    bsr    crash_boot       ; was bsr 06005308, CCE's init

.cave 06005950 060059D1
.org 06005950
crash_boot:
    sts.l  pr,@-r15
    bsr    0x06005308       ; CCE's init
    nop
    mova   cb_name,r0
    mov    r0,r4
    mov.l  cb_scratch,r5
    mov.l  cb_load,r0
    jsr    @r0
    nop
    mov.l  cb_scratch_thru,r1
    mov.l  @r1,r2
    mov.l  cb_magic,r3
    cmp/eq r3,r2
    bf     cb_done
    mov.l  cb_crash_at,r2
    mov.w  cb_words,r3
cb_copy:
    mov.l  @r1,r0
    mov    #0,r4
    mov.l  r4,@r1           ; the scratch zero again behind the copy
    add    #4,r1
    mov.l  r0,@r2
    dt     r3
    bf/s   cb_copy
    add    #4,r2
    mov.w  cb_tail,r3       ; the rest of the sector the load may have written
cb_clear:
    mov.l  r4,@r1
    dt     r3
    bf/s   cb_clear
    add    #4,r1
    mov.l  cb_crash_at,r2
    mov.l  cb_purge,r1
    or     r1,r2
    mov.w  cb_lines,r3
cb_lines_loop:
    mov.l  r4,@r2           ; associative purge of the blob's lines
    dt     r3
    bf/s   cb_lines_loop
    add    #16,r2
    mov.l  cb_crash_at,r1
    mov.l  @(4,r1),r0       ; crash_init, from the blob's header
    jsr    @r0
    nop
cb_done:
    lds.l  @r15+,pr
    rts
    nop
cb_words:
    .word  490              ; CRASH_AT to 060191A8
cb_tail:
    .word  22               ; to the end of the sector at 00200800
cb_lines:
    .word  123              ; 16-byte lines, CRASH_AT to 060191A8 and beyond
.align 4
cb_scratch:
    .long  0x00200000
cb_scratch_thru:
    .long  0x20200000
cb_load:
    .long  0x060058B4
cb_magic:
    .long  0x43525348       ; 'CRSH'
cb_crash_at:
    .long  0x06018A00
cb_purge:
    .long  0x40000000
cb_name:
    .byte  0x43, 0x52, 0x41, 0x53, 0x48, 0x2E, 0x42, 0x49, 0x4E, 0x00      ; CRASH.BIN
