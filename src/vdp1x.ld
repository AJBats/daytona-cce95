/* src/vdp1x.c's block of SCREEN.BIN at work RAM 06015140, loaded at every
   race start: the entry (its magic word first), code, constants and state;
   then its work areas, not loaded. 06015140-06019A20 stays untouched through
   races (06019A21 is the race's). */
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
