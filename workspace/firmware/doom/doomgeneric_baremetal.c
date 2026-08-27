/*
 * Deterministic AI Silicon Lab adapter for the unmodified doomgeneric engine.
 * Port code is GPL-2.0-or-later, matching the engine it links with.
 */

#include "doomgeneric.h"
#include "d_loop.h"
#include "m_argv.h"
#include "platform.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define FRAME_WIDTH 320u
#define FRAME_HEIGHT 200u
#define FRAME_PIXELS (FRAME_WIDTH * FRAME_HEIGHT)
#define MAX_EVENTS 4096u
#define MAX_FRAMES 10000u

typedef struct
{
    uint32_t tic;
    uint32_t key;
    uint32_t pressed;
} input_event_t;

_Static_assert(sizeof(input_event_t) == 12, "input event ABI changed");

static volatile const input_event_t *const input_events =
    (volatile const input_event_t *)(uintptr_t)AISL_INPUT_BASE;

static uint32_t input_event_count;
static uint32_t input_event_index;
static uint32_t input_tic;
static int input_poll_active;
static uint32_t frame_limit;
static uint32_t warmup_frames;
static uint32_t simulation_frame_count;
static uint32_t captured_frame_count;
static uint32_t fake_ticks_ms;
static int doom_started;

static char skill_arg[11];
static char episode_arg[11];
static char map_arg[11];

pixel_t *DG_ScreenBuffer;

extern boolean singletics;
extern int gametic;

static void fail(const char *message)
{
    fprintf(stderr, "AISL_FIRMWARE_ERROR: %s\n", message);
    fflush(stderr);
    exit(2);
}

static char *format_u32(char buffer[11], uint32_t value)
{
    char reverse[10];
    unsigned int count = 0;
    unsigned int out = 0;

    do
    {
        reverse[count++] = (char)('0' + value % 10u);
        value /= 10u;
    } while (value != 0u);

    while (count != 0u)
        buffer[out++] = reverse[--count];
    buffer[out] = '\0';
    return buffer;
}

void DG_Init(void)
{
    uint32_t wad_size = aisl_mmio_read(AISL_WAD_SIZE);

    frame_limit = aisl_mmio_read(AISL_FRAME_COUNT);
    warmup_frames = aisl_mmio_read(AISL_WARMUP);
    input_event_count = aisl_mmio_read(AISL_INPUT_COUNT);

    if (frame_limit == 0u || frame_limit > MAX_FRAMES)
        fail("frame_count must be between 1 and 10000");
    if (warmup_frames > MAX_FRAMES)
        fail("warmup must be at most 10000");
    if (input_event_count > MAX_EVENTS)
        fail("input_count exceeds 4096");
    if (wad_size < 12u || wad_size > AISL_INPUT_BASE - AISL_WAD_BASE)
        fail("wad_size is outside the read-only WAD window");

    aisl_mmio_write(AISL_FRAME_ADDRESS,
                    (uint32_t)(uintptr_t)DG_ScreenBuffer);
    aisl_mmio_write(AISL_CONTROL, AISL_CONTROL_BOOT);
    puts("AISL_BOOTED");
    fflush(stdout);
}

void DG_DrawFrame(void)
{
    if (!doom_started)
    {
        doom_started = 1;
        aisl_mmio_write(AISL_CONTROL, AISL_CONTROL_DOOM_STARTED);
        puts("AISL_DOOM_STARTED");
        fflush(stdout);
    }

    if (simulation_frame_count >= warmup_frames
        && captured_frame_count < frame_limit)
    {
        aisl_mmio_write(AISL_FRAME_ADDRESS,
                        (uint32_t)(uintptr_t)DG_ScreenBuffer);
        aisl_mmio_write(AISL_FRAME_INDEX, captured_frame_count);
        aisl_io_fence();
        aisl_mmio_write(AISL_CONTROL, AISL_CONTROL_CAPTURE);
        captured_frame_count++;
        aisl_mmio_write(AISL_CAPTURED, captured_frame_count);
    }

    simulation_frame_count++;
}

void DG_SleepMs(uint32_t ms)
{
    fake_ticks_ms += ms == 0u ? 29u : ms;
}

uint32_t DG_GetTicksMs(void)
{
    return fake_ticks_ms;
}

int DG_GetKey(int *pressed, unsigned char *key)
{
    if (!input_poll_active)
        input_poll_active = 1;

    while (input_event_index < input_event_count
           && input_events[input_event_index].tic < input_tic)
        input_event_index++;

    if (input_event_index < input_event_count
        && input_events[input_event_index].tic == input_tic)
    {
        uint32_t raw_pressed = input_events[input_event_index].pressed;
        uint32_t raw_key = input_events[input_event_index].key;

        if (raw_pressed > 1u || raw_key > 0xffu)
            fail("invalid parsed input event");
        *pressed = (int)raw_pressed;
        *key = (unsigned char)raw_key;
        input_event_index++;
        return 1;
    }

    input_poll_active = 0;
    input_tic++;
    return 0;
}

void DG_SetWindowTitle(const char *title)
{
    (void)title;
}

void doomgeneric_Create(int argc, char **argv)
{
    void M_FindResponseFile(void);
    void D_DoomMain(void);

    myargc = argc;
    myargv = argv;
    M_FindResponseFile();
    DG_ScreenBuffer = calloc(DOOMGENERIC_RESX * DOOMGENERIC_RESY,
                             sizeof(uint32_t));
    if (DG_ScreenBuffer == NULL)
        fail("cannot allocate framebuffer");

    DG_Init();
    singletics = true;
    D_DoomMain();
}

int main(void)
{
    char *argv[] = {
        "doomgeneric",
        "-iwad", "freedoom1.wad",
        "-skill", format_u32(skill_arg, aisl_mmio_read(AISL_SKILL)),
        "-warp", format_u32(episode_arg, aisl_mmio_read(AISL_EPISODE)),
        format_u32(map_arg, aisl_mmio_read(AISL_MAP)),
    };
    int argc = (int)(sizeof(argv) / sizeof(argv[0]));

    doomgeneric_Create(argc, argv);

    while (captured_frame_count < frame_limit)
        doomgeneric_Tick();

    if (!doom_started)
        fail("DOOM did not reach its first rendered frame");

    aisl_mmio_write(AISL_SIM_FRAMES, simulation_frame_count);
    aisl_mmio_write(AISL_GAME_TICS, (uint32_t)gametic);
    aisl_mmio_write(AISL_CAPTURED, captured_frame_count);
    fflush(NULL);
    return 0;
}
