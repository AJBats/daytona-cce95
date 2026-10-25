; Sound driver side of DUSA's tyre sounds on CCE95 (docs/tyre_sound.md), and
; of DUSA's engine and tyre sounds in 2P races (docs/two_player.md).
; Assembled into patches/tyre_sound_drv.patch by tools/mkpatch.py.
;
; The 1P engine keeps DUSA's six layers on slots 24-29 (the engine count in
; 6FFE was 7, eight layers), so slots 30-31 are free for the slip and brake
; channels; slots 20-23 are reserved from the sequencer, as 24-31 already
; were, for two pairs of peel-out voices. After the player-1 engine the module
; calls the code in tone bank 0 (patches/tyre_sound_bank0.s) when bank 0
; carries its tag, which only the 1P race files do.
;
; The 2P race files tag bank 0 'DUS2' instead: their code
; (patches/sound_2p_bank0.s) runs both players' engines and tyres, so the
; module skips CCE's two engines, and slots 16-31 are reserved for it.
.target DAYTONA/SDDRVS.TSK 00000000 m68k

.org 1900
    bsr.w   tyre_hook           ; was bsr.w $1924, the player-1 engine

.org 1B1A
tyre_hook:                      ; free: the rest of the old CC18/CC20 rpm table
    cmpi.l  #$44555332,$b1a0.l  ; 'DUS2'
    beq.s   two_player
    bsr.w   $1924
    cmpi.l  #$44555341,$b1a0.l  ; 'DUSA'
    bne.s   no_tyres
    jmp     $b1a4.l
two_player:
    addq.l  #4,a7               ; not back to 1904, where CCE's player-2 engine runs
    jmp     $b1a4.l
no_tyres:
    rts

reserve:                        ; the engine module's slots: 20-31, 16-31 for 'DUS2'
    lea     $500(a3),a3
    moveq   #11,d7
    cmpi.l  #$44555332,$b1a0.l
    bne.s   reserved
    lea     -$100(a3),a3
    moveq   #15,d7
reserved:
    rts

monitor_skip:                   ; ne: skip the slot; eq with d0 = 0: check it
    move.w  $3a(a1),d0
    andi.w  #$c0,d0
    bne.s   monitor_done
    tst.b   (a1)                ; reserved (bit 7): its word keeps the mark
    bmi.s   monitor_reserved    ; the allocator reads
    tst.w   d0
    rts
monitor_reserved:
    moveq   #1,d0
monitor_done:
    rts

; The voice monitor (17EA) walks slots 0-23 and clears a slot's +0x3A word
; once its voice reads idle, and with it the reservation mark (bit 14) the
; allocator tests: reserved slots below 24 became free again. It now leaves
; reserved slots alone.
.org 17EA
    bsr.w   monitor_skip        ; was move.w $3a(a1),d0; andi.w #$c0,d0
    nop
    nop

.org 1BC6
    moveq   #5,d1               ; 1P engine: six layers (was 7)

.org 1C80
    move.w  #5,$6ffe.w          ; default, as 1P (was 7)

.org 1CB4
    bsr.w   reserve             ; was lea $600(a3),a3 (24-31), moveq #7,d7
    nop
