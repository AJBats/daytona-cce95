/* src/vdp1x.c's block at work RAM 06015140 (a block of SCREEN.BIN, loaded at
   every race start; 16 KB there stay zero through races): VX_MAGIC and the
   entry first, then code, constants and state. The work areas follow,
   not loaded. */
SECTIONS
{
    . = 0x06015140;
    .blob : {
        *(.text.entry)
        *(.text .text.*)
        *(.rodata .rodata.*)
        *(.data .data.* .sdata .sdata.*)
        . = ALIGN(4);
    }
    .work (NOLOAD) : {
        *(.bss .bss.* .sbss .sbss.* COMMON)
    }
    /DISCARD/ : { *(.comment) *(.note*) }
}
