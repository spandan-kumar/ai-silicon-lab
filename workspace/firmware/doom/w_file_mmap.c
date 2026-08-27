/* Read-only WAD class backed by the simulator's fixed memory mapping. */

#include "platform.h"
#include "w_file.h"

#include <stdint.h>
#include <string.h>

typedef struct
{
    wad_file_t wad;
} memory_wad_file_t;

static memory_wad_file_t memory_wad;

static wad_file_t *MemoryOpen(char *path);
static void MemoryClose(wad_file_t *wad);
static size_t MemoryRead(wad_file_t *wad, unsigned int offset,
                         void *buffer, size_t buffer_len);

/* w_file.c deliberately uses this upstream class symbol as its default. */
wad_file_class_t stdc_wad_file = {
    MemoryOpen,
    MemoryClose,
    MemoryRead,
};

static wad_file_t *MemoryOpen(char *path)
{
    uint32_t size = aisl_mmio_read(AISL_WAD_SIZE);

    (void)path;
    if (size < 12u || size > AISL_INPUT_BASE - AISL_WAD_BASE)
        return NULL;

    memory_wad.wad.file_class = &stdc_wad_file;
    memory_wad.wad.mapped = (byte *)(uintptr_t)AISL_WAD_BASE;
    memory_wad.wad.length = size;
    return &memory_wad.wad;
}

static void MemoryClose(wad_file_t *wad)
{
    (void)wad;
}

static size_t MemoryRead(wad_file_t *wad, unsigned int offset,
                         void *buffer, size_t buffer_len)
{
    size_t available;

    if (offset >= wad->length)
        return 0;
    available = wad->length - offset;
    if (buffer_len > available)
        buffer_len = available;
    memcpy(buffer, wad->mapped + offset, buffer_len);
    return buffer_len;
}
