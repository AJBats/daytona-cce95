; The slave CPU starts on its share of the other cars before the master
; draws the player car. Assembled into patches/car_job.patch by
; tools/mkpatch.py.
;
; CCE's view (06029A78) draws the player car (06040634, once more for the
; second car in a two-player race), then the other cars (0603E488): it
; starts the slave's job (0603E60C, through patches/attract.s's
; slave_draw), draws its own (0603E4A4) and waits for the slave
; (0600751C) before the course, which reads the cars' counts by detail
; (06052A10, from the per-car draw 06040B8C on both CPUs). The master
; draws the cars with +0xC1 clear, the slave the others, every other car
; in the list. The slave sat idle through the player car, and the master
; then waited for it: in the Three Seven attract's grandstand shot
; (calibrated Mednafen) 1.7-2 ms a tick, the slave idle for the tick's
; first 5 ms.
;
; Now the view starts the slave's job before the player car (car_start),
; and after it draws the master's share and waits (car_share). Both CPUs
; walk the list with one routine (0603E4A4; its context, 0605410C for the
; master, 0605450C for the slave, comes from the caller, and so does r8,
; the +0xC1 the CPU draws: 0 the master, 1 the slave), so each CPU keeps
; CCE's cars. That matters: polygons in one depth bucket go the slave's
; first, then the master's (06057800's and 06057C00's buckets interleave),
; so the CPU that draws a car decides how it ties with the road and the
; other cars. A share by first come (TAS claims) was 0.8 ms better in the
; worst tick but moved cars between CPUs every few ticks, which could
; flicker the ties; a fixed quarter for the master was 2 ms worse. The
; player car's drawing shares nothing with the other cars' but the model
; draw routines, which both CPUs already ran side by side, each with its
; own context in GBR; the counts at 06052A10 are still read after the
; wait. The wait is unconditional: with no cars (0605160A clear) the slave
; is idle or finishing a job the course would wait for.
;
; The slave's copy of the routine (0603E60C-0603E773) becomes its entry
; and a cave: this file has 0603E60C-0603E653, patches/reflection.s
; 0603E684-0603E6BF, patches/ai_split.s 0603E6C0-0603E6D7,
; patches/bucket_scan.s 0603E6D8-0603E723; 0603E654-0603E683 and
; 0603E724-0603E773 are free.

; The routine both CPUs run: the context and the CPU's +0xC1 from the caller.
.org 0603E4A4
cars_body:
    sts.l  pr,@-r15         ; unchanged

.org 0603E4AE
    nop                     ; was mov.l 0605410C,r4: the caller's context

.org 0603E4CA
    .word  0x3180           ; cmp/eq r8,r1: the car's +0xC1 this CPU's (was tst r1,r1)
    ; bf next: the other CPU's

; The slave's job, from slave_draw.
.org 0603E60C
slave_cars:
    mov.l  ctx_slave,r4
    bra    cars_body
    mov    #1,r8            ; the slave's cars: +0xC1 set

; From the view, before the player car: start the slave's job.
car_start:
    mov.l  cars_on_at,r0
    mov.b  @r0,r0
    tst    r0,r0
    bt     start_out
    mov.l  slave_job_at,r4
    mov.l  job_start_at,r0
    jmp    @r0              ; 06007500 returns to the view
    nop
start_out:
    rts
    nop

; From the view, after the player car: the master's share and the wait.
car_share:
    sts.l  pr,@-r15
    mov.l  cars_on_at,r0
    mov.b  @r0,r0
    tst    r0,r0
    bt     share_wait
    mov.l  ctx_master,r4
    bsr    cars_body
    mov    #0,r8            ; the master's: +0xC1 clear
share_wait:
    mov.l  slave_wait_at,r0
    jmp    @r0              ; returns to the view
    lds.l  @r15+,pr

.align 4
ctx_slave:
    .long  0x0605450C
ctx_master:
    .long  0x0605410C
cars_on_at:
    .long  0x0605160A
slave_job_at:
    .long  0x0603CDB0       ; patches/attract.s's slave_draw, which purges the cache, then slave_cars
job_start_at:
    .long  0x06007500
slave_wait_at:
    .long  0x0600751C

; The view: the slave's job, the player car, then the master's share and
; the wait.
.org 06029B32
    mov.l  car_start_at,r0
    jsr    @r0
    mov    r4,r10           ; the view's r4 (the matrix stack) kept over the calls
    mov    r10,r4
    mov.l  mode_at,r0
    mov.b  @r0,r0
    mov    #3,r1
    cmp/ge r1,r0
    bf     player1
    mov.l  car2_at,r5
    mov.l  @r5,r5
    mov    #2,r6
    mov.l  draw_at,r0
    jsr    @r0
    nop
player1:
    mov.l  car1_at,r5
    mov.l  @r5,r5
    mov    #44,r0
    mov.l  camera_at,r1
    mov.l  @r1,r1
    mov.b  @(r0,r1),r0
    tst    r0,r0
    bt/s   view1
    mov    #0,r6
    mov    #1,r6
view1:
    mov    #49,r0
    mov.b  @(r0,r1),r0
    tst    r0,r0
    bt     view2
    mov    #2,r6
view2:
    mov.l  draw_at,r0
    jsr    @r0
    nop
    mov.l  car_start_at,r0
    add    #20,r0           ; car_share
    jsr    @r0
    mov    r4,r10
    mov    r10,r4
    nop
    nop
    nop

; The view's own literals, rewritten unchanged so the code above can name
; them, and its call of 0603E488 pointed at car_start.
.org 06029C2C
camera_at:
    .long  0x06052094
.org 06029C60
mode_at:
    .long  0x002FC233
car2_at:
    .long  0x06052244
draw_at:
    .long  0x06040634
car1_at:
    .long  0x06052098
.org 06029C74
car_start_at:
    .long  car_start
