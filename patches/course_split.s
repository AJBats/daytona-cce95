; The course blocks a sector lists are shared 7 to 9 between the master and
; the slave instead of 9 to 7. Assembled into patches/course_split.patch by
; tools/mkpatch.py.
;
; CCE shares the course's drawing between the CPUs by polygon count
; (06029E90 for the run of blocks ahead, 0602A2FC for the blocks a sector
; lists), the master taking blocks until it has 9/16 of the polygons. For
; the run that comes out even (the slave tests each of its blocks and
; skips or fast-draws whole ones; the master's are the near ones and can't
; be). For the listed blocks it doesn't: in the Three Seven attract's
; grandstand shot (calibrated Mednafen) the master drew 3.6 ms of them to
; the slave's 2.2, then the slave waited for it. The master now stops at
; 7/16 of the listed blocks' polygons.
.org 0602A328
    add    r5,r0            ; was sub r5,r0: r5 x 9 / 16 off the total, not x 7 / 16
