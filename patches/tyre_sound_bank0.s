; DUSA's tyre sounds on CCE95's 1P engine voice (docs/tyre_sound.md). Not a
; disc patch: tools/engine_convert.py assembles this into tone bank 0 of the
; 1P race sound files (sound RAM B000), so it is only there in 1P races. The
; driver's engine module calls it after the player-1 engine when it finds
; the tag (patches/tyre_sound_drv.s).
;
; The car tick (patches/tyre_sound.s) writes, with DUSA's rules, into the
; player-1 mailbox: 6F10 |slip| >> 10, 6F11 the brake hold (on while not 0),
; 6F12 a peel-out count and 6F13 its kind (1 onset, 2 end).
;
; Each sound is a layer of the engine voice (records 6-9, table blocks 6-9
; at 7F300) on a slot of its own, played through the driver's layer routine
; 19AA: TL and pitch from the block at index v. Slip and brake key on when
; v leaves 0 and off when it returns (DUSA's channels 1 and 2); the
; peel-out restarts on two slots, panned left and right, at every count
; (DUSA's one-shot). With the engine off (rpm 0: pause, race over) slip and
; brake go off.

.org B1A0
    .long $44555341             ; 'DUSA': the driver hook's tag
tyres:
    tst.b   ready.l             ; first pass this race: forget the mailbox
    bne.s   started             ; an earlier race left
    st      ready.l
    clr.l   $6f10.w
    clr.b   $6f14.w
started:
    lea     shadow.l,a3         ; what 19AA reads: +2 index, +3 and +6 zero
    move.l  $6f98.w,$18(a3)     ; bank base, as the engine's
    moveq   #0,d6
    tst.w   $6f02.w             ; rpm
    beq.s   engine_off
    moveq   #-1,d6
engine_off:
    move.b  $6f10.w,d0          ; slip: DUSA's v = |slip| >> 10, at most 7
    cmpi.b  #7,d0
    bls.s   slip_v
    moveq   #7,d0
slip_v:
    and.b   d6,d0
    move.w  #$3c0,d4            ; slot 30
    movea.l #$7f300,a2          ; block 6
    lea     slip.l,a0
    bsr.s   chan
    tst.b   $6f11.w             ; brake: v 1 while the hold runs
    sne     d0
    andi.b  #1,d0
    and.b   d6,d0
    move.w  #$3e0,d4            ; slot 31
    movea.l #$7f380,a2          ; block 7
    lea     brake.l,a0
    bsr.s   chan
    tst.b   d6
    beq.s   done
    move.b  $6f12.w,d0          ; peel-out count
    cmp.b   count.l,d0
    beq.s   done
    move.b  d0,count.l
    move.w  #$2c0,d4            ; slot 22, left
    movea.l #$7f400,a2          ; block 8
    lea     peel_l.l,a0
    bsr.s   peel
    move.w  #$2e0,d4            ; slot 23, right
    movea.l #$7f480,a2          ; block 9
    lea     peel_r.l,a0
peel:
    bsr.s   release             ; restart: off (a slot still keyed won't key on
    clr.w   (a0)                ; again), then set up and key on afresh
    move.b  $6f13.w,d0          ; kind: table index
chan:                           ; d0 v, d4 slot, a2 block, a0 last v then keyed flag
    cmp.b   (a0)+,d0
    beq.s   done
    move.b  d0,-1(a0)
    tst.b   d0
    beq.s   key_off
    tst.b   (a0)
    bne.s   keyed
    clr.l   $c(a5,d4.w)         ; a sequence may have left TL bits or modulation here
keyed:
    move.b  d0,$2(a3)
    jmp     $19aa.l             ; update TL and pitch, or set up and key on
key_off:
    tst.b   (a0)
    beq.s   done
    sf      (a0)
release:
    move.b  (a5,d4.w),d0
    andi.b  #$7,d0
    ori.b   #$10,d0
    move.b  d0,(a5,d4.w)
done:
    rts

ready:
    .byte   0
count:
    .byte   0
slip:
    .byte   0
    .byte   0
brake:
    .byte   0
    .byte   0
peel_l:
    .byte   0
    .byte   0
peel_r:
    .byte   0
    .byte   0
shadow:
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
    .long   0
