/* src/crash.c and src/crash_entry.s as one piece at CRASH_AT (tools/crash.py
   passes it as crash_at): the header first, then code, constants and state,
   zeros included, as patches/crash.s copies it from DAYTONA/CRASH.BIN. */
SECTIONS
{
    . = crash_at;
    .blob : {
        *(.text.entry)
        *(.text .text.*)
        *(.rodata .rodata.*)
        *(.data .data.* .sdata .sdata.*)
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(4);
    }
    /DISCARD/ : { *(.comment) *(.note*) }
}
