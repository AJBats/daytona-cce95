; Sound driver side of DUSA's tyre sounds on CCE95 (docs/tyre_sound.md).
; Assembled into patches/tyre_sound_drv.patch by tools/mkpatch.py.
;
; The 1P engine keeps DUSA's six layers on slots 24-29 (the engine count in
; 6FFE was 7, eight layers), so slots 30-31 are free for the slip and brake
; channels; slots 22-23 are reserved from the sequencer, as 24-31 already
; were, for the two peel-out voices. After the player-1 engine the module
; calls the code in tone bank 0 (patches/tyre_sound_bank0.s) when bank 0
; carries its tag, which only the 1P race files do.
.target DAYTONA/SDDRVS.TSK 00000000 m68k

.org 1900
    bsr.w   tyre_hook           ; was bsr.w $1924, the player-1 engine

.org 1B1A
tyre_hook:                      ; free: the rest of the old CC18/CC20 rpm table
    bsr.w   $1924
    cmpi.l  #$44555341,$b1a0.l  ; 'DUSA'
    bne.s   no_tyres
    jmp     $b1a4.l
no_tyres:
    rts

.org 1BC6
    moveq   #5,d1               ; 1P engine: six layers (was 7)

.org 1C80
    move.w  #5,$6ffe.w          ; default, as 1P (was 7)

.org 1CB4
    lea     $580(a3),a3         ; reserve slots 22-31 (was $600: 24-31)
    moveq   #9,d7               ; was 7
