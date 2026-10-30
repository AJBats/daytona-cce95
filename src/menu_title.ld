/* src/menu_title.c's blob at LWRAM 00242300, after TITLED.BIN in the
   menu's buffer at 0x220000: the entries first, then code, constants and
   state, all in one piece */
SECTIONS
{
    . = 0x00242300;
    .blob : {
        *(.text.entry)
        *(.text .text.*)
        *(.rodata .rodata.*)
        *(.data .data.*)
        *(.bss .bss.* COMMON)
    }
    /DISCARD/ : { *(.comment) *(.note*) }
}
