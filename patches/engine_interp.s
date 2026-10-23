; Engine pitch and level follow rpm smoothly between CCE's 256-rpm table
; steps, so DUSA's engine (128 steps of ~41 rpm, tools/engine_convert.py)
; doesn't jump a semitone at a time. Assembled into
; patches/engine_interp.patch by tools/mkpatch.py.
;
; SDDRVS engine module (docs/engine_sound.md): per layer, level[35] at +7
; and pitch[35] at +0x3A indexed by i = rpm >> 8. The rpm-change check kept
; only rpm & 0xFF00 in the shadow word (+2 of 6F80/6FA0); it now keeps the
; whole rpm (clamped to 0x2200, the last step), so +2 is still i and +3 is
; the fraction f. One routine replaces the pitch (1A5C) and level (1A2A)
; routines: value = t[i] + (t[i+1] - t[i]) x f / 256. At i = 34, f is 0.
; The space comes from the MIDI CC18/CC20 handler (engine rpm from a 7-bit
; value), whose 128-word table was n x 69 except entry 68 (= entry 69):
; it now multiplies, with the same entry-68 quirk.
.target DAYTONA/SDDRVS.TSK 00000000 m68k

.org 1974
rpm_changed:                    ; rpm word -> shadow +2, d6 set on change
    move.w  $2(a1),d0
    cmpi.w  #$2200,d0
    bls.s   rpm_clamped
    move.w  #$2200,d0
rpm_clamped:
    cmp.w   $2(a3),d0
    beq.s   rpm_same
    move.w  d0,$2(a3)
    st      d6
rpm_same:
    rts

.org 19AE
    bsr.w   engine_slot         ; was pitch (1A5C) then level (1A2A)
    nop
    nop

.org 1A0E
    bsr.w   engine_slot
    nop
    nop

.org 1A84
cc18_p1:                        ; MIDI CC18: player 1 engine rpm
    movea.w #$6f00,a1
    bra.s   cc_rpm
cc20_p2:                        ; MIDI CC20: player 2
    movea.w #$6f20,a1
cc_rpm:
    move.l  $18(a1),d0
    beq.s   cc_done
    andi.w  #$7f,d3
    cmpi.w  #68,d3
    bne.s   cc_scale
    addq.w  #1,d3
cc_scale:
    mulu.w  #69,d3
    move.w  d3,$2(a1)
cc_done:
    rts

engine_slot:                    ; a2 layer, a3 shadow, a5 SCSP, d4 slot
    moveq   #0,d0
    move.b  $2(a3),d0           ; i
    moveq   #0,d2
    move.b  $3(a3),d2           ; f
    move.w  d0,d1
    add.w   d1,d1
    move.w  $3a(a2,d1.w),d3     ; pitch[i]
    move.w  $3c(a2,d1.w),d1     ; pitch[i+1]
    sub.w   d3,d1
    muls.w  d2,d1
    asr.l   #8,d1
    add.w   d1,d3
    andi.w  #$3fff,d3
    subi.w  #$2000,d3           ; octave x 0x400 + FNS
    move.w  d3,d1
    andi.w  #$3ff,d1
    andi.w  #$3c00,d3
    add.w   d3,d3
    or.w    d1,d3
    move.w  d3,$10(a5,d4.w)     ; OCT/FNS
    moveq   #0,d1
    move.b  $7(a2,d0.w),d1      ; level[i]
    moveq   #0,d3
    move.b  $8(a2,d0.w),d3      ; level[i+1]
    sub.w   d1,d3
    muls.w  d2,d3
    asr.l   #8,d3
    add.w   d3,d1
    move.w  $6(a3),d2           ; throttle offset, as before
    move.b  $2a(a2,d2.w),d2
    ext.w   d2
    not.w   d2
    moveq   #0,d0
    add.w   d2,d1
    bmi.s   tl_store
    not.b   d0
    cmpi.w  #$100,d1
    bcc.s   tl_store
    move.b  d1,d0
tl_store:
    move.b  d0,$d(a5,d4.w)      ; TL
    rts
