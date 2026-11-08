; Race-time routines that don't fit RACE.BIN's caves, as a block of
; SCREEN.BIN (tools/race_block.py) at 06019700: a magic word, then an entry
; per routine. CCE's block loader copies SCREEN.BIN's blocks in at every
; race start (0602927C), not in the attract, so each entry is reached
; through a trampoline in RACE.BIN that checks the word first:
;   06019702  the two-player window reflection (patches/reflection.s,
;             0603CAD4)
;   06019706  the race's song in Endurance (patches/endurance.s), from the
;             race start's end, after the load
.org 06019700
    .word  0x5232           ; 'R2', the magic the trampolines check
    bra    reflect_2p
    nop
    bra    endurance_song
    nop

; Two-player: PLCAR29 has no room for the strip, but its window texture
; holds the whole 40-row image as loaded (the strip is that image twice), so
; the same state picks the same start and the texture is rotated in place
; by the change of start, in passes of at most 256 bytes through a buffer.
; The state (V3, H3, previous heading, start) and the buffer live in the
; spare end of that player's PLCAR29.MDL in RAM, zero as
; loaded. Only for DUSA's cars, as in one-player. From the two-player chase
; (patches/camera.s): r9 = player, r12 = car; keeps r0, uses r1-r7.
reflect_2p:
    mov.l  r0,@-r15
    mov.l  r7,@-r15
    sts.l  pr,@-r15
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
    mov.w  spare_off,r5
    add    r1,r5            ; the state, then the buffer
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
    mov.l  @(12,r5),r3
    mov.l  r2,@(12,r5)
    sub    r3,r2            ; d = new start - old
    cmp/pz r2
    bt     d_ok
    add    r1,r2
d_ok:
    tst    r2,r2
    bt     done_2p
    add    #16,r5           ; the buffer
    mov.w  half_2p,r3
    cmp/hi r3,r2
    bt     right
    mov    r2,r6            ; rotate left by d
left_pass:
    mov    r6,r4
    mov.w  chunk_2p,r3
    cmp/hi r3,r4
    bf     left_k
    mov    r3,r4            ; k: at most 256
left_k:
    mov    r7,r1            ; buffer = W[0, k)
    mov    r5,r2
    bsr    copy_2p
    mov    r4,r3
    mov    r7,r1            ; W[0, 1600 - k) = W[k, 1600)
    add    r4,r1
    mov    r7,r2
    mov.w  size_2p,r3
    bsr    copy_2p
    sub    r4,r3
    mov    r5,r1            ; W[1600 - k, 1600) = buffer
    bsr    copy_2p
    mov    r4,r3
    sub    r4,r6
    tst    r6,r6
    bf     left_pass
    bra    done_2p
    nop
right:
    mov.w  size_2p,r6
    sub    r2,r6            ; rotate right by 1600 - d
right_pass:
    mov    r6,r4
    mov.w  chunk_2p,r3
    cmp/hi r3,r4
    bf     right_k
    mov    r3,r4
right_k:
    mov.w  size_2p,r1       ; buffer = W[1600 - k, 1600)
    sub    r4,r1
    add    r7,r1
    mov    r5,r2
    bsr    copy_2p
    mov    r4,r3
    mov.w  size_2p,r3       ; W[k, 1600) = W[0, 1600 - k), from the end down
    sub    r4,r3
    mov    r7,r1
    add    r3,r1
    mov.w  size_2p,r2
    add    r7,r2
down:
    add    #-1,r1
    mov.b  @r1,r0
    add    #-1,r2
    dt     r3
    bf/s   down
    mov.b  r0,@r2
    mov    r5,r1            ; W[0, k) = buffer
    mov    r7,r2
    bsr    copy_2p
    mov    r4,r3
    sub    r4,r6
    tst    r6,r6
    bf     right_pass
done_2p:
    lds.l  @r15+,pr
    mov.l  @r15+,r7
    rts
    mov.l  @r15+,r0
copy_2p:                    ; r3 bytes from r1 to r2 (at least 1)
    mov.b  @r1+,r0
    mov.b  r0,@r2
    dt     r3
    bf/s   copy_2p
    add    #1,r2
    rts
    nop
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
half_2p:
    .word  800
chunk_2p:
    .word  256
spare_off:
    .word  0x0BA0           ; after the body's 2956 bytes, before the trailer
srca_2p:
    .word  0x018C           ; texture table +8 + 48 x 8, entry +4
.align 4
models_at:
    .long  0x06056578       ; per player, 8 model header pointers
is_dusa_2p:
    .long  0x060334FC       ; patches/car_choice.s: T = player r1's car is DUSA's
vram_2p:
    .long  0x25C00000

; Endurance (Options > ARCADE > GAME MODE, 002FC234 = 2, in an Arcade race,
; 002FC233 = 0): the race's song rolls on through the rest of its version's
; songs and loops them, as DUSA's longest races run on from the course's
; song through its four (DUSA 06018B28). CCE loops the one song in every
; mode. The race start's last step (patches/endurance.s, in place of its
; tail call to 06030B7C) comes here; anything else, or the music switched
; off (06013367 clear), goes on to 06030B7C as before.
; The run: '95 songs 34-37, CCE's originals 23-25, CCE's own 2-7 (the
; remixes, Noisy Roars, the Medley). As CCE's start of a song (06007A74,
; 06030B7C) it notes the track asked for (06013364, looped: 06013365 = 15),
; queues a task (06013B78) and sets the music volume (06007C90). The task
; waits, as CCE's (06007B2E), for the drive to report 1, then seeks to the
; chosen song and plays the run from the first track to the last with the
; pickup left where the seek put it, repeated for ever (play mode 0x8F, as
; DUSA's), so the first pass starts at the chosen song and the loops take
; the whole run; then ends itself (06013BB4).
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
    mov    #23,r0
    cmp/hs r0,r2
    bf     es_run_set
    mov    #23,r3           ; the originals
    mov    #25,r4
    mov    #34,r0
    cmp/hs r0,r2
    bf     es_run_set
    mov    #34,r3           ; '95
    mov    #37,r4
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
