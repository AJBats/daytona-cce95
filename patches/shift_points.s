; Automatic upshifts, DUSA's. Patch 32, with patches/kmh_cap.s.
; Assembled into patches/shift_points.patch by tools/mkpatch.py.
;
; The automatic gearbox (CCE 0604D83C, DUSA 0602F17C) shifts up at an rpm
; per gear from a table: DUSA 060477AC holds 7400, 7400, 7400, CCE's
; (CMVDATA.BIN, loaded at 002DC000, +0x1630) 7144, so CCE's automatic
; changed up earlier in every gear (driving_model.md row 7 listed it as a
; retuned rev limit). The downshift table (+0x1620) is DUSA's already.
.target DAYTONA/CMVDATA.BIN 002DC000 sh2

.org 002DD630
    .long  7400                 ; 1st -> 2nd, was 7144
    .long  7400                 ; 2nd -> 3rd, was 7144
    .long  7400                 ; 3rd -> 4th, was 7144
