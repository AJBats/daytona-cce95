; Spin-out and wheel rates, DUSA's at 30 Hz. Patch 30.
; Assembled into patches/spin_rates.patch by tools/mkpatch.py.
;
; Found by the per-tick audit of 2026-11-09 (docs/driving_model.md row 29);
; each value is DUSA's converted by the rules there:
; - Speed lost each tick of a spin-out (CCE 06039E16, DUSA 06008252):
;   DUSA 227 per 20 Hz tick; CCE kept 0x25E x 0x4000 / 65536 = 151 per
;   30 Hz tick, so a spin-out cost 50% more speed (18 km/h for DUSA's 12).
;   Speed is in per-tick units (CCE's are 2/3 of DUSA's), so this is an
;   acceleration: 227 x 4/9 = 101 = 0x25E x 0x2AAB / 65536.
; - Front wheels back to the centre during a spin-out or a flip (CCE
;   0604D804, DUSA 0602F144, the same routine): 0x71C per tick in both, so
;   full lock to centre in 0.6 s instead of 0.9 s. x 2/3: 0x4BD.
; - Wheel spin on screen (CCE 0604D708, DUSA 0602F41C): the step follows
;   speed, already per tick, but its caps 0xAAA (and 0x2AAA while the rear
;   spins, 0604D74C) were DUSA's per tick, so the wheels turned 1.5x as
;   fast. x 2/3: 0x71C, 0x1C71.

.org 06039EB2
    .word  0x2AAB               ; spin-out speed loss multiplier, was 0x4000

.org 0604D730
    .long  0x00001C71           ; wheel step cap, was 0x2AAA
.org 0604D7A0
    .word  0x1C71               ; rear wheels while spinning, was 0x2AAA
.org 0604D7B0
    .long  0x0000071C           ; wheel step cap, was 0xAAA

.org 0604D824
    .long  0x000004BD           ; wheels back to centre per tick, was 0x71C
