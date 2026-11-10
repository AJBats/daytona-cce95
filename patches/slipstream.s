; The slipstream, DUSA's. Patch 31.
; Assembled into patches/slipstream.patch by tools/mkpatch.py.
;
; A car in another's slipstream gets less drag (CCE 0604DB10, DUSA
; 0602F5B6) while its tow timer runs; the timer starts when a car is
; within 30 units ahead inside a window either side of straight ahead
; (CCE 0604DE2C, DUSA 0602F4B4; the distance and the timer, 20 -> 30
; ticks, are already converted). CCE retuned both: the drag x0.60 for
; DUSA's x0.90 (a factor on the force, not per tick), and the window
; +-5 degrees (0x38E) for DUSA's +-10 (0x71C), so CCE's tow pulled harder
; and was half as easy to catch. Both are DUSA's now (driving_model.md
; rows 10 and 30).

.org 0604DCA6
    .word  0x7333               ; drag in the tow, 0.90 in 1.15; was 0x4CCC

.org 0604DF30
    .long  0x0000071C           ; the window, +-10 degrees; was 0x38E
