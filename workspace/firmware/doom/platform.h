#ifndef AISL_DOOM_PLATFORM_H
#define AISL_DOOM_PLATFORM_H

#include <stdint.h>

#define AISL_WAD_BASE       0x02000000u
#define AISL_INPUT_BASE     0x03c00000u
#define AISL_RAM_END        0x04000000u
#define AISL_MMIO_BASE      0x10000000u

#define AISL_UART           (AISL_MMIO_BASE + 0x00u)
#define AISL_CONTROL        (AISL_MMIO_BASE + 0x04u)
#define AISL_FRAME_ADDRESS  (AISL_MMIO_BASE + 0x08u)
#define AISL_FRAME_INDEX    (AISL_MMIO_BASE + 0x0cu)
#define AISL_FRAME_COUNT    (AISL_MMIO_BASE + 0x10u)
#define AISL_WARMUP         (AISL_MMIO_BASE + 0x14u)
#define AISL_INPUT_COUNT    (AISL_MMIO_BASE + 0x18u)
#define AISL_WAD_SIZE       (AISL_MMIO_BASE + 0x1cu)
#define AISL_SKILL          (AISL_MMIO_BASE + 0x20u)
#define AISL_EPISODE        (AISL_MMIO_BASE + 0x24u)
#define AISL_MAP            (AISL_MMIO_BASE + 0x28u)
#define AISL_SIM_FRAMES     (AISL_MMIO_BASE + 0x30u)
#define AISL_GAME_TICS      (AISL_MMIO_BASE + 0x34u)
#define AISL_CAPTURED       (AISL_MMIO_BASE + 0x38u)
#define AISL_EXIT_CODE      (AISL_MMIO_BASE + 0x3cu)

#define AISL_CONTROL_BOOT          0x00000001u
#define AISL_CONTROL_DOOM_STARTED  0x00000002u
#define AISL_CONTROL_CAPTURE       0x00000003u
#define AISL_CONTROL_FINISH        0x00000004u
#define AISL_CONTROL_FAIL          0x0000deadu

static inline uint32_t aisl_mmio_read(uint32_t address)
{
    return *(volatile const uint32_t *)(uintptr_t)address;
}

static inline void aisl_mmio_write(uint32_t address, uint32_t value)
{
    *(volatile uint32_t *)(uintptr_t)address = value;
}

static inline void aisl_io_fence(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

#endif
