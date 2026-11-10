; Inputs during a crash, as DUSA reads them. Patch 29.
; Assembled into patches/crash_inputs.patch by tools/mkpatch.py.
;
; A spin-out (CCE +0xB0 = 72, DUSA +0xB8 = 48) and a flip (CCE +0xB4, DUSA
; +0x1BC, counts from the flip's table) each run a countdown in the car.
; Both games stop copying the pedals while either runs, so gas and brake
; hold their values through the crash (CCE 0604D7BE, DUSA 0602F0E8).
; CCE also zeroes the car's pad words while the flip count is 32 or more
; (06037EFE, the racing mode's first step: the buttons and, for the wheel
; and the 3D pad, the analog byte), so steering and the gear buttons go
; dead too. DUSA has no such step: its input step (060302C6) reads the
; gear buttons and the steering through the crash, so a player can pick
; the gear for the landing (Reddit, 2026-11-09). Checked by setting the
; count to 60 at speed with left held: the steering stayed 0 before, and
; now ramps as it does outside a crash; the gas pedal held at 255 in both.

.org 06037F06
    bra    0x06037F2A           ; was bf: skip the pad clear always (the delay
                                ; slot's load of r0 is redone at 06037F2A)
