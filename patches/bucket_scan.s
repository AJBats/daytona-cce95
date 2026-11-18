; The depth buckets are linked into the command list faster: through the
; cache, two to a loop. Assembled into patches/bucket_scan.patch by
; tools/mkpatch.py.
;
; After both CPUs have drawn, each links half of the depth buckets into
; VDP1's command list (06047748, a one-player race's: 2560 buckets at
; 06060000-060627FF for the master, 06062800-06064FFF for the slave, a
; word head and a word tail each, scanned from the top). Nearly all are
; empty, and CCE read each cache-through, one bus read and a taken branch
; a bucket: 2.6 ms on each CPU every tick in the Three Seven attract
; (calibrated Mednafen). Both CPUs purge their caches right before the scan
; (06047810, 06047868), and the drawing writes the buckets cache-through,
; so read through the cache they are fresh and come four to a line; the
; scan's clearing writes go through to memory as every write does, and the
; next drawing uses the buckets cache-through again. The loop (scan, in
; patches/car_job.s's cave) takes two buckets a turn and branches out only
; on a full one. The two-player scan (06047770) keeps its own literals and
; loop.

.org 060478A8
    .long  0x060627FC       ; was 260627FC: the master's buckets, from the top
.org 060478B4
    .long  0x06064FFC       ; was 26064FFC: the slave's

; 06047748, called from both halves: r4 the list's last command so far, r5
; the top bucket, r6 the count (2560, even). Gives the last command in r4
; and r8.
.org 06047748
    mov.l  scan_at,r0
    jmp    @r0
    nop
.align 4
scan_at:
    .long  scan

.org 0603E6D8
scan:
    sts.l  pr,@-r15
    mov.l  cmds_at,r7       ; the command table
    mov    #0,r2
    shlr   r6               ; pairs
    add    #-4,r5           ; r5: the lower of the pair
scan_pair:
    mov.w  @(4,r5),r0
    tst    r0,r0
    bf     scan_hi
scan_lo:
    mov.w  @r5,r0
    tst    r0,r0
    bf     scan_lo_hit
scan_next:
    dt     r6
    bf/s   scan_pair
    add    #-8,r5
    lds.l  @r15+,pr
    rts
    mov    r4,r8
scan_hi:
    mov    r5,r3
    bsr    scan_link
    add    #4,r3
    bra    scan_lo
    nop
scan_lo_hit:
    bsr    scan_link
    mov    r5,r3
    bra    scan_next
    nop
scan_link:                  ; r0 the bucket's head, r3 the bucket: CCE's linking
    mov    r4,r1
    shll2  r1
    shll   r1
    add    r7,r1
    mov.w  r0,@(2,r1)       ; the last command links on to the head
    mov.w  r2,@r3           ; the bucket emptied
    mov.w  @(2,r3),r0
    rts
    mov    r0,r4            ; its tail the last command
.align 4
cmds_at:
    .long  0x0601B000
