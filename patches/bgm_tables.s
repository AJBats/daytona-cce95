; The race's music by BGM choice, 13 choices (docs/music.md). Assembled into
; patches/bgm_tables.patch by tools/mkpatch.py.
;
; The BGM choice (Options > Sound, a byte per course at 002FC3A2) indexes
; five tables of RACE.BIN: the song (06030B7C, from 0604F3BC), the goal
; jingle (06030BA4, 0604F3C5) and the ending (06030C24, 0604F3CE), CD track
; numbers, a 0 taking the course's own entry (the Medley's); a word each for
; the goal (060318B4, 0604F49C) and for the ending scene's length in ticks
; (06032278, 0604F4B6). They held CCE's 9 choices, packed tight. Now 13, in
; the cave after patches/camera.s's replay selectors:
;   0-5   CCE's: the three remixes, The Noisy Roars of Wilderness, Pounding
;         Pavement (remix), the Medley (as before, so a beta save's CCE
;         choices stay theirs)
;   6-8   The King of Speed, Let's Go Away, Sky High '95 (DUSA's, tracks
;         34-36, goals 38-40, endings 41-43): the defaults on DUSA's three
;         courses, where 6-8 were CCE's originals, so beta saves get them
;   9-11  CCE's originals (tracks 23-25, 26-28, 29-31)
;   12    Pounding Pavement '95 (37, goal 19, ending 22)
; The goal word for the '95 choices is the originals' 150. The ending scene
; runs about 30 ticks a second of its song (CCE's 990 for its originals'
; 33 s endings); DUSA's run 33.4, 37.1, 36.3 and 36.3 s.
; Cave: the unreferenced function at 0603C994, after the replay selectors.

.org 0603CB30
bgm_songs:
    .byte  2, 3, 4, 5, 6, 7
    .byte  34, 35, 36
    .byte  23, 24, 25
    .byte  37
bgm_goals:
    .byte  8, 9, 10, 11, 12, 0
    .byte  38, 39, 40
    .byte  26, 27, 28
    .byte  19
bgm_endings:
    .byte  13, 14, 15, 16, 17, 0
    .byte  41, 42, 43
    .byte  29, 30, 31
    .byte  22
.align 2
bgm_goal_words:
    .word  120
    .word  150
    .word  120
    .word  210
    .word  180
    .word  120
    .word  150
    .word  150
    .word  150
    .word  150
    .word  150
    .word  150
    .word  150
bgm_ending_ticks:
    .word  1140
    .word  990
    .word  990
    .word  1020
    .word  960
    .word  1200
    .word  1000             ; Rolling Start
    .word  1110             ; The Dream of Daytona
    .word  1090             ; Can You Fly?
    .word  990
    .word  990
    .word  990
    .word  1090             ; Pounding Pavement (reprise)

.org 06030C04
    .long  bgm_songs        ; was 0604F3BC
.org 06030C1C
    .long  bgm_goals        ; was 0604F3C5
.org 06030E5C
    .long  bgm_endings      ; was 0604F3CE
.org 06031970
    .long  bgm_goal_words   ; was 0604F49C
.org 06032334
    .long  bgm_ending_ticks ; was 0604F4B6
