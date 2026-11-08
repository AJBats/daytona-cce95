; Endurance races roll through the chosen song's version (docs/music.md).
; Assembled into patches/endurance.patch by tools/mkpatch.py.
;
; The race start ends with a tail call to 06030B7C, the race's song
; (06029524, through the literal at 06029584; the attract demo and the
; replay leave earlier with their own tracks). It comes here instead: the
; song in Endurance is src/race_block.s's (SCREEN.BIN's block, entry
; 06019706), which the race start has just loaded (0602927C); without the
; block's magic word, 06030B7C as before.
; Cave: the unreferenced function at 0603C994, after patches/bgm_tables.s.

.org 06029584
    .long  endurance_entry  ; was 06030B7C

.org 0603CB8C
endurance_entry:
    mov.l  ee_block_at,r1
    mov.w  @r1+,r2          ; the magic word
    mov.w  ee_magic,r3
    cmp/eq r3,r2
    bf     ee_plain
    add    #4,r1            ; past the reflection's entry
    jmp    @r1
    nop
ee_plain:
    mov.l  ee_song_at,r0
    jmp    @r0
    nop
ee_magic:
    .word  0x5232
.align 4
ee_block_at:
    .long  0x06019700
ee_song_at:
    .long  0x06030B7C
