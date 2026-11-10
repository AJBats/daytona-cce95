; The km/h cap, DUSA's. Patch 32, with patches/shift_points.s.
; Assembled into patches/kmh_cap.patch by tools/mkpatch.py.
;
; km/h (CCE 0604D6BE, DUSA 0602F3F2) is speed x a scale, capped: 334 in
; CCE, 344 in DUSA. The scale is converted already (CCE 0x6C0000 = 1.5 x
; DUSA's 0x480000, for CCE's per-tick speed units).

.org 0604D6E8
    .long  0x00000158           ; 344 km/h, was 0x14E (334)
