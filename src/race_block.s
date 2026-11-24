; Race-time routines that don't fit RACE.BIN's caves, as a block of
; SCREEN.BIN (tools/race_block.py) at 06018700: a magic word, then an entry
; per routine. CCE's block loader copies SCREEN.BIN's blocks in at every
; race start (0602927C), not in the attract, so each entry is reached
; through a trampoline in RACE.BIN that checks the word first:
;   06018702  the two-player window reflection (patches/reflection.s,
;             0603CAD4)
;   06018706  the race's song in Endurance (patches/endurance.s), from the
;             race start's end, after the load
;   0601870A  the window uploads, from the race's list copy in VBlank-IN
;             (patches/vdp1x.s), which this one goes on to
; The list copy and patches/reflection.s check only the first byte, 0x52:
; before the first race these bytes are the main program's zeros, and once
; loaded the block stays, through the attract too.
.org 06018700
    .word  0x5232           ; 'R2', the magic the trampolines check
    bra    reflect_2p
    nop
    bra    endurance_song
    nop
    bra    win_upload
    nop
    .word  0

; The window slots, at 06018710: four of (source, window in VDP1 VRAM,
; bytes), DMA'd at the next list copy; a slot counts once its bytes are set,
; and win_upload clears them as it takes it. One player: slot 0
; (patches/reflection.s). Two players: slots 2 x player and the next.
win_slots:
    .long  0                ; slot 0: source
    .long  0                ;         window
    .long  0                ;         bytes
    .long  0                ; slot 1
    .long  0
    .long  0
    .long  0                ; slot 2
    .long  0
    .long  0
    .long  0                ; slot 3
    .long  0
    .long  0

; The window reflection's uploads, DUSA's way (DUSA 06006F3C: the window by
; SCU DMA in its VBlank-IN handler): VDP1 isn't drawing at the list copy,
; and a CPU touching its VRAM while it draws slows the drawing. Each slot
; with bytes goes by SCU level 0, direct, started by the CPU (CCE's list copy
; uses it next), one at a time: the status's D0MV (bit 4) clear before each
; start and after the last. One player takes slot 0 only: a two-player
; race's last slots may be left over when the block outlives it in the
; attract. Entered by a jump with PR the kernel's; r0-r7 free, as in the
; copy it goes on to.
win_upload:
    mov.l  wu_slots,r1
    mov.l  wu_scu,r3
    mov.l  wu_dsta,r4
    mov.l  wu_mode,r0
    mov.b  @r0,r0
    cmp/eq #2,r0
    bt/s   wu_count
    mov    #4,r5            ; two players: all four slots
    mov    #1,r5            ; one player: slot 0
wu_count:
    mov    #16,r6           ; DSTA's D0MV
    mov    #7,r7            ; D0MD: direct, started by the CPU
wu_slot:
    mov.l  @(8,r1),r2       ; bytes
    tst    r2,r2
    bt     wu_next
    mov    #0,r0
    mov.l  r0,@(8,r1)       ; taken
wu_wait:
    mov.l  @r4,r0
    tst    r6,r0
    bf     wu_wait
    mov.l  @r1,r0
    mov.l  r0,@(0,r3)       ; D0R: the source
    mov.l  @(4,r1),r0
    mov.l  r0,@(4,r3)       ; D0W: the window
    mov.l  r2,@(8,r3)       ; D0C
    mov.w  wu_add,r0
    mov.l  r0,@(12,r3)      ; D0AD: read +4, write +2
    mov.l  r7,@(20,r3)      ; D0MD
    mov.l  r0,@(16,r3)      ; D0EN: enable, start
wu_next:
    dt     r5
    bf/s   wu_slot
    add    #12,r1
wu_done:
    mov.l  @r4,r0
    tst    r6,r0
    bf     wu_done
    mov.l  wu_copy,r1
    jmp    @r1
    nop
wu_add:
    .word  0x0101
.align 4
wu_slots:
    .long  win_slots
wu_scu:
    .long  0x25FE0000
wu_dsta:
    .long  0x25FE007C
wu_mode:
    .long  0x002FC233       ; 2 in two-player races
wu_copy:
    .long  0x06047B90       ; CCE's list copy

; Two-player: DUSA has no split screen. Each player's PLCAR29 holds the
; 40-row image once, plus its first byte again, after the scroll state
; (tools/rebake.py; the strip twice over has no room there), so the window
; is the image from the start to its end, then from its beginning: two
; slots. With an odd start the extra byte keeps both pieces' lengths and the
; second's place in VRAM even (the B-bus writes 16 bits): from the start to
; the extra byte, then from byte 1. The state (V3, H3, previous heading) is
; at +0x8E0 in that player's PLCAR29.MDL in RAM, zero as loaded; the image
; at +0x8F0. Only for DUSA's cars, as in one-player. Every tick whatever
; the camera, from the two-player race loop's call to each player's car
; effects (patches/reflection.s, reflect_tick): r4 = player; uses r0-r7.
reflect_2p:
    mov.l  r9,@-r15
    mov.l  r12,@-r15
    sts.l  pr,@-r15
    extu.b r4,r9            ; the player
    mov.l  cars_2p,r12
    mov.w  car_size_2p,r0
    mulu.w r0,r9
    sts    macl,r0
    add    r0,r12           ; that player's car
    mov.l  is_dusa_2p,r0
    jsr    @r0
    extu.b r9,r1            ; DUSA's car only, as in one-player
    bt     dusa_2p
    bra    done_2p
    nop
dusa_2p:
    extu.b r9,r0
    shll2  r0
    shll2  r0
    shll   r0               ; player x 32
    mov.l  models_at,r1
    mov.l  @(r0,r1),r1      ; that player's undamaged model header
    mov.l  @(12,r1),r3      ; its offset back to the texture table
    add    r3,r1            ; PLCAR29.MDL as loaded
    mov.w  state_off,r5
    add    r1,r5            ; the state, the image 16 bytes on
    mov.w  srca_2p,r0
    mov.w  @(r0,r1),r7
    extu.w r7,r7
    shll2  r7
    shll   r7
    mov.l  vram_2p,r1
    add    r1,r7            ; the window texture
    mov.l  @(52,r12),r1     ; km/h
    shar   r1
    shar   r1
    shar   r1
    shar   r1
    shar   r1
    add    #1,r1
    add    r1,r1
    mov.l  @r5,r2
    add    r1,r2
    mov.w  v_wrap_2p,r3
    cmp/hi r3,r2
    bf     v_ok_2p
    sub    r3,r2
v_ok_2p:
    mov.l  r2,@r5           ; V3
    mov.l  @(60,r12),r1     ; heading
    mov.l  @(8,r5),r3
    mov.l  r1,@(8,r5)
    sub    r1,r3
    exts.w r3,r3            ; previous - heading
    mov.l  @(4,r5),r4
    cmp/pl r3
    bf     h_not_up_2p
    bra    h_wrap_2p
    add    #4,r4
h_not_up_2p:
    cmp/pz r3
    bt     h_wrap_2p
    add    #-4,r4
h_wrap_2p:
    mov.w  h_limit_2p,r1
    cmp/hi r1,r4
    bf     h_ok_2p
    mov    #0,r4
h_ok_2p:
    mov.l  r4,@(4,r5)       ; H3
    mov.w  twelfth_2p,r1
    muls.w r1,r2
    sts    macl,r2
    shlr16 r2               ; V3 / 12
    mov    r2,r1
    shll2  r2
    add    r1,r2
    shll2  r2
    shll2  r2               ; x 80
    mov.w  sixth_2p,r1
    muls.w r1,r4
    sts    macl,r4
    shlr16 r4
    add    r4,r2            ; start
    mov.w  size_2p,r1
    cmp/hs r1,r2
    bf     start_ok
    sub    r1,r2
start_ok:
    mov.l  slots_2p,r3
    extu.b r9,r0
    shll2  r0
    shll   r0
    add    r0,r3
    shll   r0
    add    r0,r3            ; this player's two slots (24 bytes on a player)
    mov    #0,r0
    mov.l  r0,@(8,r3)       ; neither counts while it changes
    mov.l  r0,@(20,r3)
    add    #16,r5           ; the image
    mov    r2,r0
    and    #1,r0            ; e: 1 with an odd start
    mov    r5,r4
    add    r2,r4
    mov.l  r4,@r3           ; first: from the start,
    mov.l  r7,@(4,r3)       ; to the window,
    mov    r1,r4
    sub    r2,r4
    add    r0,r4            ; 1600 - start + e bytes
    add    r0,r5
    mov.l  r5,@(12,r3)      ; second: from byte e,
    add    r4,r7
    mov.l  r7,@(16,r3)      ; to the window after the first,
    sub    r0,r2
    mov.l  r2,@(20,r3)      ; start - e bytes (none for a start of 0 or 1)
    mov.l  r4,@(8,r3)
done_2p:
    lds.l  @r15+,pr
    mov.l  @r15+,r12
    rts
    mov.l  @r15+,r9
car_size_2p:
    .word  0x01D8           ; car structs: P1 0605224C, P2 06052424
v_wrap_2p:
    .word  240
h_limit_2p:
    .word  480
twelfth_2p:
    .word  0x1556
sixth_2p:
    .word  0x2AAB
size_2p:
    .word  1600
state_off:
    .word  0x08E0           ; tools/rebake.py: the model ends below, the image follows
srca_2p:
    .word  0x018C           ; texture table +8 + 48 x 8, entry +4
.align 4
cars_2p:
    .long  0x0605224C
models_at:
    .long  0x06056578       ; per player, 8 model header pointers
is_dusa_2p:
    .long  0x060334FC       ; patches/car_choice.s: T = player r1's car is DUSA's
vram_2p:
    .long  0x25C00000
slots_2p:
    .long  win_slots

; Endurance (Options > ARCADE > GAME MODE, 002FC234 = 2, in an Arcade race,
; 002FC233 = 0): the race's song rolls on through the rest of its version's
; songs and loops them, as DUSA's longest races run on from the course's
; song through its four (DUSA 06018B28). CCE loops the one song in every
; mode. The race start's last step (patches/endurance.s, in place of its
; tail call to 06030B7C) comes here; anything else, or the music switched
; off (06013367 clear), goes on to 06030B7C as before.
; The run: Pounding Pavement '95 and the disc's King of Speed, Let's Go
; Away and Sky High, 22-25 ('95's, or CCE's arcade originals on a disc
; built with them), or CCE's own 2-7 (the remixes, Noisy Roars, the
; Medley). From the chosen song to 25 and round from 22 is DUSA's order.
; As CCE's start of a song (06007A74, 06030B7C) it notes the track asked
; for (06013364, looped: 06013365 = 15), queues a task (06013B78) and
; sets the music volume (06007C90). The task waits, as CCE's (06007B2E),
; for the drive to report 1, then seeks to the chosen song and plays the
; run from the first track to the last with the pickup left where the seek
; put it, repeated for ever (play mode 0x8F, as DUSA's), so the first pass
; starts at the chosen song and the loops take the whole run; then ends
; itself (06013BB4).
endurance_song:
    mov.l  es_type_at,r1
    mov.b  @r1,r0
    tst    r0,r0
    bf     es_plain         ; not Arcade
    mov.b  @(1,r1),r0
    cmp/eq #2,r0
    bf     es_plain         ; not Endurance
    mov.l  es_on_at,r1
    mov.b  @r1,r0
    tst    r0,r0
    bt     es_plain
    sts.l  pr,@-r15
    mov.l  es_course_at,r1
    mov.b  @r1,r0
    extu.b r0,r0
    mov.l  es_bgm_at,r1
    mov.b  @(r0,r1),r0
    extu.b r0,r0
    mov.l  es_songs_at,r1
    mov.b  @(r0,r1),r2      ; the chosen song's track
    extu.b r2,r2
    mov    #2,r3            ; CCE's own
    mov    #7,r4
    mov    #22,r0
    cmp/hs r0,r2
    bf     es_run_set
    mov    #22,r3           ; the disc's version of DUSA's four
    mov    #25,r4
es_run_set:
    mova   es_run,r0
    mov.b  r2,@r0
    add    #1,r0
    mov.b  r3,@r0
    add    #1,r0
    mov.b  r4,@r0
    mov.l  es_track_at,r1
    mov.b  r2,@r1           ; the track asked for
    mov    #15,r0
    mov.b  r0,@(1,r1)       ; looped
    mov    #0,r0
    mov.b  r0,@(4,r1)       ; 06013368, as 06007A74
    mov.l  es_task_at,r4
    mov.l  es_add_at,r0
    jsr    @r0
    nop
    mov.l  es_volume_at,r1
    mov.b  @r1,r4
    mov.l  es_set_volume_at,r0
    jsr    @r0
    nop
    mov.l  es_track_at,r1
    mov    #0,r0
    mov.b  r0,@(4,r1)       ; 06013368, as 06030B7C
    lds.l  @r15+,pr
    rts
    nop
es_plain:
    mov.l  es_song_at,r0
    jmp    @r0
    nop

; The task (r4 = itself), each frame until it plays.
es_task:
    sts.l  pr,@-r15
    add    #-36,r15
    mov.l  r4,@r15
    mov    r15,r4
    add    #4,r4
    mov.l  es_status_at,r0
    jsr    @r0
    nop
    mov    r15,r0
    add    #4,r0
    mov.b  @r0,r0
    cmp/eq #1,r0
    bf     es_wait
    mov    r15,r3           ; positions at +16: type 2 (track, index), track, index
    add    #16,r3
    mov    #2,r2
    mov.l  r2,@r3
    mova   es_run,r0
    mov.b  @r0,r0           ; the chosen song
    mov.b  r0,@(4,r3)
    mov    #1,r0
    mov.b  r0,@(5,r3)
    mov    r3,r4
    mov.l  es_seek_at,r0
    jsr    @r0
    nop
    mov    r15,r3
    add    #16,r3
    mov    #2,r2
    mov.l  r2,@r3
    mov.l  r2,@(8,r3)
    mova   es_run,r0
    mov.b  @(1,r0),r0       ; from the first
    mov.b  r0,@(4,r3)
    mov    #1,r0
    mov.b  r0,@(5,r3)
    mova   es_run,r0
    mov.b  @(2,r0),r0       ; to the last
    mov.b  r0,@(12,r3)
    mov    #99,r0
    mov.b  r0,@(13,r3)
    mov    r3,r1
    add    #16,r1
    mov.w  es_mode,r0
    mov.b  r0,@r1
    mov    r3,r4
    mov.l  es_play_at,r0
    jsr    @r0
    nop
    mov.l  @r15,r4
    mov.l  es_remove_at,r0
    jsr    @r0
    nop
es_wait:
    add    #36,r15
    lds.l  @r15+,pr
    rts
    nop
es_mode:
    .word  0x008F           ; the pickup where it is, repeat for ever
.align 4
es_run:                     ; the chosen song's track, the run's first and last
    .long  0
es_type_at:
    .long  0x002FC233
es_on_at:
    .long  0x06013367
es_course_at:
    .long  0x06054920
es_bgm_at:
    .long  0x002FC3A2
es_songs_at:
    .long  0x0603CB30       ; patches/bgm_tables.s, the songs by choice
es_track_at:
    .long  0x06013364
es_task_at:
    .long  es_task
es_add_at:
    .long  0x06013B78
es_volume_at:
    .long  0x002FC3A1
es_set_volume_at:
    .long  0x06007C90
es_song_at:
    .long  0x06030B7C
es_status_at:
    .long  0x06009BD8
es_seek_at:
    .long  0x06009FAE
es_play_at:
    .long  0x06009F10
es_remove_at:
    .long  0x06013BB4

; Camera 1's blend state (patches/camera.s, pick_chase / pick_script), at
; 060189DC: in Link Battle each Saturn runs both cameras and camera 1 is
; Player 2's. This copy at every race start resets it as the 1P setup
; resets camera 0's: no bias yet, and the chase counts as run (nonzero), so
; the race's first script takes the chase's lead out of y. The zeros before
; it hold it at the place patches/camera.s has.
.align 4
    .long  0
    .long  0
    .long  0
blend_cam1:
    .long  0                ; the bias a script's y carries
    .long  1                ; nonzero: the chase ran since a script last did
