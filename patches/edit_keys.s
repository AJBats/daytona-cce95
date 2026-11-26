; EDIT, the fifth type on Options > KEY CONFIG (tools/options_keys.py): TYPE
; E's layout with the player's own jobs for some buttons. Assembled into
; patches/edit_keys.patch by tools/mkpatch.py.
;
; A layout is kept per player and device (as the page counts them: 0 pad,
; 1 Arcade Racer or Mission Stick, 2 3D pad) at 002FE7C2 + 5 x (3 x player +
; device), in the save (patches/save_ext.s, docs/backup.md): a job code each
; for A, B, C, X, Y, Z, L, R, up and down (the Arcade Racer's paddles), 4
; bits, high nibble first, 0 for TYPE E's job. The codes: 1 NOT USED, 2
; ACCEL, 3 BRAKE, 4 SHIFT UP, 5 SHIFT DOWN, 6-9 GEAR 1-4, 10 UP VIEW, 11 DOWN
; VIEW, 12-15 VIEW 1-4.
;
; The race starts from TYPE E's tables, as for any type, then each button
; with a job of its own leaves the job it had and joins the new one:
; - the driving masks, which car setup's key fill (06034D90) copies into the
;   key config (+0x14 shift up, +0x16 shift down, +0x18 gas, +0x1A brake,
;   +0x1C-0x22 gears 1-4). For an analog pad the steering masks are cleared,
;   so EDIT steers with the stick (TYPE E alone steered the 3D pad with its
;   d-pad), and the pedal triggers follow the jobs: gas on R unless only L
;   has it, brake on L unless only R has it (the fill knows only CCE's own
;   two arrangements);
; - the camera keys, which 0602FB94 copies for the player (06051FAC + 116 x
;   player + 74: views 1-4, or 0, 0, up view, down view). Views 1-4 win if
;   any button has one; then view 1's word is never 0, as the camera takes
;   0 there for up and down.
;
; Cave: CCE's analog core step (patches/wheel.s), after the steering choice.

.cave 06036450 0603666F
.org 06036450
; Car setup, after the key fill (r4 = car): on to 06038A82 as before.
edit_fill:
    sts.l  pr,@-r15         ; setup's return, for 06038A82
    mov.l  r8,@-r15
    mov.l  r9,@-r15
    mov.l  r10,@-r15
    mov.l  r11,@-r15
    mov    #18,r0
    mov.b  @(r0,r4),r8      ; the player
    mov    r8,r0
    shll   r0
    add    r8,r0
    shll   r0
    mov.l  ef_cfg,r1        ; the player config (060540B5 + 6 x player)
    add    r0,r1
    mov.b  @r1,r0           ; the type
    cmp/eq #4,r0
    bf     ef_done
    mov.b  @(5,r1),r0       ; the port's SMPC ID
    bsr    layout_of
    extu.b r0,r0
    mov.w  ef_keys,r0
    mov.l  @(r0,r4),r10     ; the key config
    mov    #0,r11
ef_slot:
    bsr    code_of
    nop
    tst    r0,r0
    bt     ef_next
    mov    r0,r3
    mov.l  ef_masks,r1
    mov    r11,r0
    shll   r0
    mov.w  @(r0,r1),r2      ; the button's bit
    not    r2,r5
    mov    r10,r1
    add    #20,r1           ; off every job's mask
    mov    #8,r6
ef_clear:
    mov.w  @r1,r0
    and    r5,r0
    mov.w  r0,@r1
    dt     r6
    bf/s   ef_clear
    add    #2,r1
    mov.l  ef_offsets,r1    ; onto the new job's, if it's a driving job
    mov    r3,r0
    mov.b  @(r0,r1),r0
    tst    r0,r0
    bt     ef_next
    mov.w  @(r0,r10),r1
    or     r2,r1
    mov.w  r1,@(r0,r10)
ef_next:
    add    #1,r11
    mov    r11,r0
    cmp/eq #10,r0
    bf     ef_slot
    mov.w  ef_type,r0       ; an analog pad
    mov.w  @(r0,r4),r0
    cmp/eq #2,r0
    bf     ef_done
    mov    #0,r0
    mov.l  r0,@(36,r10)     ; +0x24, +0x26: no d-pad steering
    mov    #12,r1
    mulu.w r1,r8
    sts    macl,r1
    mov.l  ef_triggers,r0   ; 060540F4 + 12 x player + 10: R, then L
    add    r0,r1
    mov    r1,r2
    add    #1,r2
    mov.w  @(24,r10),r0     ; gas
    mov    r1,r3
    tst    #0x80,r0
    bf     ef_gas
    tst    #0x08,r0
    bt     ef_gas
    mov    r2,r3
ef_gas:
    mov.l  r3,@(12,r10)
    mov.w  @(26,r10),r0     ; brake
    mov    r2,r3
    tst    #0x08,r0
    bf     ef_brake
    tst    #0x80,r0
    bt     ef_brake
    mov    r1,r3
ef_brake:
    mov.l  r3,@(16,r10)
ef_done:
    mov.l  @r15+,r11
    mov.l  @r15+,r10
    mov.l  @r15+,r9
    mov.l  @r15+,r8
    lds.l  @r15+,pr
    mov.l  ef_next_at,r0
    jmp    @r0
    nop

; r0 = the SMPC ID, r8 the player -> r9 their layout for that device
layout_of:
    mov    #0,r1
    cmp/eq #2,r0
    bt     lo_dev
    mov    #1,r1
    cmp/eq #19,r0
    bt     lo_dev
    cmp/eq #21,r0
    bt     lo_dev
    mov    #2,r1
lo_dev:
    mov    r8,r0
    shll   r0
    add    r8,r0
    add    r1,r0
    mov    r0,r1
    shll2  r0
    add    r1,r0
    mov.l  ef_layouts,r9
    rts
    add    r0,r9

; r9 = the layout, r11 the slot -> r0 its code (0: TYPE E's job)
code_of:
    mov    r11,r0
    shlr   r0
    mov.b  @(r0,r9),r0
    mov    r11,r1
    shlr   r1
    bt     co_low
    shlr2  r0
    shlr2  r0
co_low:
    rts
    and    #15,r0

; 0602FB94, the camera keys for a player, ends here (r5 = the row of the
; device's table it copied; its stack as at 0602FC88, with the player's
; camera block, 116 x player, at +4).
edit_camera:
    mov.l  r8,@-r15
    mov.l  r9,@-r15
    mov.l  r10,@-r15
    mov.l  r11,@-r15
    mov.l  ec_tables,r0
    mov    r5,r1
    sub    r0,r1
    mov    #40,r2
ec_mod:
    cmp/hs r2,r1
    bf     ec_row
    bra    ec_mod
    sub    r2,r1
ec_row:
    mov    r1,r0
    cmp/eq #32,r0           ; TYPE E's row: EDIT
    bf     ec_done
    mov.l  @(20,r15),r10    ; the player's camera block (under our four)
    mov    #0,r8
    tst    r10,r10
    bt     ec_player
    mov    #1,r8
ec_player:
    mov.l  ec_smpc,r0
    mov.b  @(r0,r8),r0
    bsr    layout_of
    extu.b r0,r0
    mov.l  ec_cam,r0
    add    r0,r10           ; the four words
    mov    #0,r6            ; up view
    mov    #0,r7            ; down view
    mov.w  @r10,r0
    tst    r0,r0
    bf     ec_slots
    mov.w  @(4,r10),r0
    mov    r0,r6
    mov.w  @(6,r10),r0
    mov    r0,r7
    mov    #0,r0
    mov.w  r0,@(4,r10)
    mov.w  r0,@(6,r10)
ec_slots:
    mov    #0,r11
ec_slot:
    bsr    code_of
    nop
    tst    r0,r0
    bt     ec_next
    mov    r0,r3
    mov.l  ec_masks,r1
    mov    r11,r0
    shll   r0
    mov.w  @(r0,r1),r2
    not    r2,r5
    and    r5,r6
    and    r5,r7
    mov.w  @r10,r0
    and    r5,r0
    mov.w  r0,@r10
    mov.w  @(2,r10),r0
    and    r5,r0
    mov.w  r0,@(2,r10)
    mov.w  @(4,r10),r0
    and    r5,r0
    mov.w  r0,@(4,r10)
    mov.w  @(6,r10),r0
    and    r5,r0
    mov.w  r0,@(6,r10)
    mov    r3,r0
    cmp/eq #10,r0
    bf     ec_down
    bra    ec_next
    or     r2,r6
ec_down:
    cmp/eq #11,r0
    bf     ec_view
    bra    ec_next
    or     r2,r7
ec_view:
    add    #-12,r0
    cmp/pz r0
    bf     ec_next          ; not a camera job
    shll   r0
    mov.w  @(r0,r10),r1
    or     r2,r1
    mov.w  r1,@(r0,r10)
ec_next:
    add    #1,r11
    mov    r11,r0
    cmp/eq #10,r0
    bf     ec_slot
    mov.w  @r10,r0          ; any view 1-4?
    mov    r0,r1
    mov.w  @(2,r10),r0
    or     r0,r1
    mov.w  @(4,r10),r0
    or     r0,r1
    mov.w  @(6,r10),r0
    or     r0,r1
    tst    r1,r1
    bt     ec_cycle
    mov.w  @r10,r0
    tst    r0,r0
    bf     ec_done
    mov    #1,r0            ; a bit no button sets
    bra    ec_done
    mov.w  r0,@r10
ec_cycle:
    mov    r6,r0
    mov.w  r0,@(4,r10)
    mov    r7,r0
    mov.w  r0,@(6,r10)
ec_done:
    mov.l  @r15+,r11
    mov.l  @r15+,r10
    mov.l  @r15+,r9
    mov.l  @r15+,r8
    add    #8,r15
    lds.l  @r15+,macl
    lds.l  @r15+,pr
    mov.l  @r15+,r13
    rts
    mov.l  @r15+,r14
ef_keys:
    .word  0x015C
ef_type:
    .word  0x016A
.align 4
ef_cfg:
    .long  0x060540B5
ef_masks:
    .long  slot_masks
ef_offsets:
    .long  job_offsets
ef_triggers:
    .long  0x060540FE
ef_layouts:
    .long  0x002FE7C2
ef_next_at:
    .long  0x06038A82
ec_tables:
    .long  0x0604F028
ec_smpc:
    .long  0x060131C4
ec_cam:
    .long  0x06051FF6
ec_masks:
    .long  slot_masks
slot_masks:                 ; A, B, C, X, Y, Z, L, R, up, down
    .word  0x0400
    .word  0x0100
    .word  0x0200
    .word  0x0040
    .word  0x0020
    .word  0x0010
    .word  0x0008
    .word  0x0080
    .word  0x1000
    .word  0x2000
job_offsets:                ; by code: the key config's mask for a driving job
    .byte  0, 0, 0x18, 0x1A, 0x14, 0x16, 0x1C, 0x1E, 0x20, 0x22, 0, 0, 0, 0, 0, 0

.org 060351C4
    .long  edit_fill        ; car setup's call after the key fill, was 06038A82

.org 0602FC88
    mov.l  ec_at,r0         ; was the camera keys' epilogue, done there
    jmp    @r0
    nop
    nop
ec_at:
    .long  edit_camera
