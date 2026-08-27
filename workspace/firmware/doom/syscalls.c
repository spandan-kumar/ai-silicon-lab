/* Minimal newlib system-call boundary for the simulated RV32 machine. */

#include "platform.h"

#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/times.h>
#include <sys/types.h>

extern char __heap_start[];
extern char __heap_end[];

typedef struct
{
    int in_use;
    uint32_t offset;
} wad_descriptor_t;

static wad_descriptor_t wad_descriptor;
static uintptr_t heap_break = (uintptr_t)__heap_start;

static int is_wad_path(const char *path)
{
    static const char name[] = "freedoom1.wad";
    size_t path_length;

    if (path == NULL)
        return 0;
    path_length = strlen(path);
    return path_length >= sizeof(name) - 1u
        && strcmp(path + path_length - (sizeof(name) - 1u), name) == 0;
}

int _write(int file, const void *buffer, size_t length)
{
    const unsigned char *bytes = buffer;
    size_t i;

    if (file != 1 && file != 2)
    {
        errno = EBADF;
        return -1;
    }
    for (i = 0; i < length; ++i)
        *(volatile uint8_t *)(uintptr_t)AISL_UART = bytes[i];
    return (int)length;
}

int _read(int file, void *buffer, size_t length)
{
    uint32_t wad_size;
    size_t available;

    if (file != 3 || !wad_descriptor.in_use)
    {
        errno = EBADF;
        return -1;
    }

    wad_size = aisl_mmio_read(AISL_WAD_SIZE);
    if (wad_descriptor.offset >= wad_size)
        return 0;
    available = wad_size - wad_descriptor.offset;
    if (length > available)
        length = available;
    memcpy(buffer,
           (const void *)(uintptr_t)(AISL_WAD_BASE + wad_descriptor.offset),
           length);
    wad_descriptor.offset += (uint32_t)length;
    return (int)length;
}

int _open(const char *path, int flags, ...)
{
    if (!is_wad_path(path))
    {
        errno = ENOENT;
        return -1;
    }
    if ((flags & O_ACCMODE) != O_RDONLY)
    {
        errno = EROFS;
        return -1;
    }
    if (wad_descriptor.in_use)
    {
        errno = EMFILE;
        return -1;
    }

    wad_descriptor.in_use = 1;
    wad_descriptor.offset = 0;
    return 3;
}

int _close(int file)
{
    if (file != 3 || !wad_descriptor.in_use)
    {
        errno = EBADF;
        return -1;
    }
    wad_descriptor.in_use = 0;
    wad_descriptor.offset = 0;
    return 0;
}

off_t _lseek(int file, off_t offset, int whence)
{
    int64_t base;
    int64_t next;
    uint32_t wad_size = aisl_mmio_read(AISL_WAD_SIZE);

    if (file != 3 || !wad_descriptor.in_use)
    {
        errno = EBADF;
        return (off_t)-1;
    }

    switch (whence)
    {
        case SEEK_SET: base = 0; break;
        case SEEK_CUR: base = wad_descriptor.offset; break;
        case SEEK_END: base = wad_size; break;
        default:
            errno = EINVAL;
            return (off_t)-1;
    }
    next = base + offset;
    if (next < 0 || next > wad_size)
    {
        errno = EINVAL;
        return (off_t)-1;
    }
    wad_descriptor.offset = (uint32_t)next;
    return (off_t)next;
}

int _fstat(int file, struct stat *status)
{
    memset(status, 0, sizeof(*status));
    if (file == 1 || file == 2)
    {
        status->st_mode = S_IFCHR;
        return 0;
    }
    if (file == 3 && wad_descriptor.in_use)
    {
        status->st_mode = S_IFREG | S_IRUSR;
        status->st_size = (off_t)aisl_mmio_read(AISL_WAD_SIZE);
        return 0;
    }
    errno = EBADF;
    return -1;
}

int _stat(const char *path, struct stat *status)
{
    if (!is_wad_path(path))
    {
        errno = ENOENT;
        return -1;
    }
    memset(status, 0, sizeof(*status));
    status->st_mode = S_IFREG | S_IRUSR;
    status->st_size = (off_t)aisl_mmio_read(AISL_WAD_SIZE);
    return 0;
}

int _isatty(int file)
{
    if (file == 1 || file == 2)
        return 1;
    errno = ENOTTY;
    return 0;
}

void *_sbrk(ptrdiff_t increment)
{
    uintptr_t previous = heap_break;
    uintptr_t lower = (uintptr_t)__heap_start;
    uintptr_t upper = (uintptr_t)__heap_end;
    uintptr_t next;

    if (increment >= 0)
    {
        if ((uintptr_t)increment > upper - heap_break)
        {
            errno = ENOMEM;
            return (void *)-1;
        }
        next = heap_break + (uintptr_t)increment;
    }
    else
    {
        uintptr_t decrease = (uintptr_t)(-(increment + 1)) + 1u;
        if (decrease > heap_break - lower)
        {
            errno = ENOMEM;
            return (void *)-1;
        }
        next = heap_break - decrease;
    }
    heap_break = next;
    return (void *)previous;
}

int _mkdir(const char *path, mode_t mode)
{
    (void)path;
    (void)mode;
    errno = EROFS;
    return -1;
}

int mkdir(const char *path, mode_t mode)
{
    return _mkdir(path, mode);
}

int _unlink(const char *path)
{
    (void)path;
    errno = EROFS;
    return -1;
}

int _link(const char *old_path, const char *new_path)
{
    (void)old_path;
    (void)new_path;
    errno = EROFS;
    return -1;
}

clock_t _times(struct tms *times)
{
    if (times != NULL)
        memset(times, 0, sizeof(*times));
    return 0;
}

int _getpid(void)
{
    return 1;
}

int _kill(int pid, int signal)
{
    (void)pid;
    (void)signal;
    errno = EINVAL;
    return -1;
}

__attribute__((noreturn)) void _exit(int status)
{
    aisl_mmio_write(AISL_EXIT_CODE, (uint32_t)status);
    aisl_io_fence();
    aisl_mmio_write(AISL_CONTROL,
                    status == 0 ? AISL_CONTROL_FINISH : AISL_CONTROL_FAIL);
    for (;;)
        __asm__ volatile ("j .");
}
