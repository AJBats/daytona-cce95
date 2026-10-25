/* src/attract.c's blob at LWRAM 002E2780 (DEMOTTL.BIN): the entry first,
   then code, constants and state, all in one piece */
SECTIONS
{
    . = 0x002E2780;
    .blob : {
        *(.text.entry)
        *(.text .text.*)
        *(.rodata .rodata.*)
        *(.data .data.*)
        *(.bss .bss.* COMMON)
    }
    /DISCARD/ : { *(.comment) *(.note*) }
}
