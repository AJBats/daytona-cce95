; DUSA's engine and tyre sounds for both players in CCE95's 2P races
; (docs/two_player.md). Not a disc patch: tools/engine_convert.py assembles
; this into tone bank 0 of the 2P race sound files (sound RAM B000). When
; bank 0 carries the tag 'DUS2', the driver's engine module hands its whole
; tick to this code instead of running CCE's two 4-layer engines, and
; reserves slots 16-31 for it (patches/tyre_sound_drv.s).
;
; Slots: 16-17 the peel-out, shared by both players (each one starts on the
; other slot, so it rings on over the last as DUSA's do); 18-19 player 1's
; slip and brake, 20-21 player 2's; 22-26 player 1's engine, 27-31 player
; 2's. Each sound is set up and played by the driver's layer routine 19AA
; from its table block at 7F000 (blocks 0-5 DUSA's six engine layers, 6
; slip, 7 brake, 8 peel-out), then panned to its player's side with the pan
; words in block 15 (7F780 player 1, 7F782 player 2; centre in the mono
; files).
;
; DUSA's engine has six layers, at most five in range at once. Five slots
; play them: the top-end layer (3, in range from step 19) and one of the
; idle pair (4, up to step 17) share a slot, which switches blocks at step
; 18, where both tables are silent.
;
; The car tick (patches/tyre_sound.s) writes each player's tyre values
; after its engine values: player 1 at 6F10, player 2 at 6F30 (|slip| >>
; 10, the brake hold, a peel-out count and its kind).

.org B1A0
    .long $44555332             ; 'DUS2': the driver hook's tag
tick:
    tst.b   ready.l             ; first pass this race: forget the mailboxes
    bne.s   started             ; an earlier race left, and key our slots off:
    st      ready.l             ; a sequence may have left one keyed, and a
    clr.l   $6f10.w             ; slot still keyed won't key on again
    clr.b   $6f14.w
    clr.l   $6f30.w
    clr.b   $6f34.w
    move.w  #$200,d4            ; slot 16
first_off:
    bsr.w   release
    addi.w  #$20,d4
    cmpi.w  #$400,d4
    bne.s   first_off
started:
    lea     p1.l,a1
    bsr.s   player
    lea     p2.l,a1
player:                         ; a1 the player's record
    movea.w $2(a1),a3           ; engine shadow (6F80, 6FA0)
    move.l  $18(a3),d0          ; bank base: 0 until the mode command
    beq.w   done                ; set this player up
    movea.l #$7f000,a2
    move.w  $4(a1),d5
    move.w  $0(a2,d5.w),d5      ; this player's pan
    andi.w  #$1f00,d5
    move.l  a1,-(a7)
    movea.w (a1),a1             ; mailbox (6F00, 6F20)
    jsr     $1974.l             ; rpm -> step i and fraction f
    jsr     $1994.l             ; throttle level
    moveq   #0,d7               ; d7: 0 with the engine off (rpm 0: pause,
    tst.w   $2(a1)              ; race over), else -1
    beq.s   engine_off
    moveq   #-1,d7
engine_off:
    movea.l (a7)+,a1
    lea     $e(a1),a0           ; per slot: block, keyed flag
    move.w  $6(a1),d4           ; first engine slot
    moveq   #0,d6               ; plan entry
engine:
    tst.b   d7
    beq.s   engine_slot_off
    lea     plan.l,a4
    moveq   #0,d0
    move.b  $2(a3),d0           ; i
    move.b  $0(a4,d6.w),d1      ; block below the switch step
    cmp.b   $2(a4,d6.w),d0
    bcs.s   block_chosen
    move.b  $1(a4,d6.w),d1      ; block from it
block_chosen:
    tst.b   $1(a0)
    beq.s   block_set
    btst    #3,(a5,d4.w)        ; keyed off behind our back (the mode
    beq.s   lost                ; command keys slots 24-31 off)
    cmp.b   (a0),d1
    beq.s   block_set
    bsr.w   release             ; another layer for this slot: restart it
lost:
    sf      $1(a0)
block_set:
    move.b  d1,(a0)
    andi.w  #$ff,d1
    lsl.w   #7,d1
    movea.l #$7f000,a2
    lea     $0(a2,d1.w),a2
    move.l  a0,-(a7)
    addq.l  #1,a0               ; the keyed flag, for 19AA
    tst.b   (a0)
    bne.s   engine_update
    move.l  #$00ff0000,$c(a5,d4.w)
    bsr.w   setup
    bra.s   engine_done
engine_update:
    jsr     $19aa.l             ; TL and pitch at i, f
engine_done:
    movea.l (a7)+,a0
    bra.s   engine_next
engine_slot_off:
    tst.b   $1(a0)
    beq.s   engine_next
    sf      $1(a0)
    bsr.w   release
engine_next:
    addq.l  #2,a0
    addi.w  #$20,d4
    addq.w  #3,d6
    cmpi.w  #15,d6
    bne.w   engine

    lea     shadow.l,a3         ; the tyres' own shadow: +2 v, +3 and +6 zero
    move.l  $6f98.w,$18(a3)     ; bank base, as the engine's
    movea.w (a1),a0
    move.b  $10(a0),d0          ; slip: DUSA's v = |slip| >> 10, at most 7
    cmpi.b  #7,d0
    bls.s   slip_v
    moveq   #7,d0
slip_v:
    and.b   d7,d0
    move.w  $8(a1),d4
    movea.l #$7f300,a2          ; block 6
    lea     $18(a1),a0
    bsr.w   chan
    movea.w (a1),a0
    tst.b   $11(a0)             ; brake: v 1 while the hold runs
    sne     d0
    andi.b  #1,d0
    and.b   d7,d0
    move.w  $a(a1),d4
    movea.l #$7f380,a2          ; block 7
    lea     $1a(a1),a0
    bsr.w   chan
    tst.b   d7
    beq.w   done
    movea.w (a1),a0
    move.b  $12(a0),d0          ; peel-out count
    cmp.b   $c(a1),d0
    beq.w   done
    move.b  d0,$c(a1)
    not.b   pair.l
    beq.s   pair_b
    move.w  #$200,d4            ; slot 16
    lea     peel_a.l,a0
    bra.s   peel
pair_b:
    move.w  #$220,d4            ; slot 17
    lea     peel_b.l,a0
peel:
    bsr.s   release             ; restart: off (a slot still keyed won't key on
    clr.w   (a0)                ; again), then set up and key on afresh
    movea.w (a1),a2
    move.b  $13(a2),d0          ; kind: table index
    movea.l #$7f400,a2          ; block 8
chan:                           ; d0 v, d4 slot, a2 block, a0 last v then keyed flag
    cmp.b   (a0)+,d0
    beq.w   done
    move.b  d0,-1(a0)
    tst.b   d0
    beq.s   key_off
    move.b  d0,$2(a3)
    tst.b   (a0)
    beq.s   chan_new
    btst    #3,(a5,d4.w)
    beq.s   chan_lost
    jmp     $19aa.l             ; update TL and pitch
chan_lost:
    sf      (a0)
chan_new:
    move.l  #$00ff0000,$c(a5,d4.w)  ; silent, no modulation: a sequence may have
                                    ; left bits here, and a release still rings
setup:                          ; set up and key on through 19AA, then pan
    jsr     $19aa.l
    movea.l (a2),a4             ; the layer record
    move.w  $18(a4),d0          ; its direct send
    andi.w  #$e0ff,d0
    or.w    d5,d0
    move.w  d0,$16(a5,d4.w)
    rts
key_off:
    tst.b   (a0)
    beq.w   done
    sf      (a0)
release:
    move.b  (a5,d4.w),d0
    andi.b  #$7,d0
    ori.b   #$10,d0
    move.b  d0,(a5,d4.w)
done:
    rts

p1:                             ; mailbox, shadow, pan word in the table, first engine
    .word   $6f00               ; slot, slip slot, brake slot; +12 the last peel-out
    .word   $6f80               ; count; +14 engine slots (block, keyed) x 5; +24
    .word   $780                ; slip (last v, keyed); +26 brake
    .word   $2c0
    .word   $240
    .word   $260
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
p2:
    .word   $6f20
    .word   $6fa0
    .word   $782
    .word   $360
    .word   $280
    .word   $2a0
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
shadow:
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
peel_a:                         ; last v, keyed (cleared as a word)
    .byte   0
    .byte   0
peel_b:
    .byte   0
    .byte   0
ready:
    .byte   0
pair:
    .byte   0
plan:                           ; per engine slot: block below step, block from it, step
    .byte   0
    .byte   0
    .byte   $ff
    .byte   1
    .byte   1
    .byte   $ff
    .byte   2
    .byte   2
    .byte   $ff
    .byte   4
    .byte   3
    .byte   18
    .byte   5
    .byte   5
    .byte   $ff
