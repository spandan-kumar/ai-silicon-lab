OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    PROGRAM_RAM (rwx) : ORIGIN = 0x00000000, LENGTH = 0x02000000
}

PHDRS
{
    text PT_LOAD FLAGS(5);
    data PT_LOAD FLAGS(6);
}

SECTIONS
{
    . = ORIGIN(PROGRAM_RAM);

    .text : ALIGN(4)
    {
        KEEP(*(.text.init))
        *(.text .text.*)
    } > PROGRAM_RAM :text

    .rodata : ALIGN(4)
    {
        *(.srodata .srodata.*)
        *(.rodata .rodata.*)
        *(.eh_frame)
    } > PROGRAM_RAM :text

    .preinit_array : ALIGN(4)
    {
        PROVIDE_HIDDEN(__preinit_array_start = .);
        KEEP(*(.preinit_array))
        PROVIDE_HIDDEN(__preinit_array_end = .);
    } > PROGRAM_RAM :text

    .init_array : ALIGN(4)
    {
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT_BY_INIT_PRIORITY(.init_array.*)))
        KEEP(*(.init_array))
        PROVIDE_HIDDEN(__init_array_end = .);
    } > PROGRAM_RAM :text

    .fini_array : ALIGN(4)
    {
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT_BY_INIT_PRIORITY(.fini_array.*)))
        KEEP(*(.fini_array))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } > PROGRAM_RAM :text

    .data : ALIGN(4)
    {
        __data_start = .;
        *(.data .data.*)
        . = ALIGN(4);
        PROVIDE(__global_pointer$ = . + 0x800);
        *(.sdata .sdata.*)
        __data_end = .;
    } > PROGRAM_RAM :data

    .bss (NOLOAD) : ALIGN(16)
    {
        __bss_start = .;
        *(.sbss .sbss.*)
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(16);
        __bss_end = .;
    } > PROGRAM_RAM :data

    __image_end = .;
    __heap_start = ALIGN(., 16);
    end = __heap_start;
    _end = __heap_start;

    /* The WAD begins at 0x02000000. Keep one MiB for a descending stack. */
    __stack_top = 0x01fffff0;
    __stack_bottom = __stack_top - 0x00100000;
    __heap_end = __stack_bottom;

    ASSERT(__image_end <= __heap_end,
           "program/BSS collide with heap/stack reservation")
    ASSERT(__heap_start <= __heap_end, "empty firmware heap")
    ASSERT(__stack_top < 0x02000000, "stack reaches WAD mapping")

    /DISCARD/ :
    {
        *(.comment)
        *(.note .note.*)
    }
}
