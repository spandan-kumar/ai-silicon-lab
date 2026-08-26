/*
 * AI Silicon Lab reference adapter for doomgeneric.
 *
 * The engine remains upstream code. This small adapter makes its 320x200
 * framebuffer and input loop deterministic for the laboratory oracle.
 */

#include "doomgeneric.h"
#include "doomkeys.h"
#include "d_loop.h"
#include "m_argv.h"

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FRAME_WIDTH 320
#define FRAME_HEIGHT 200
#define MAX_EVENTS 4096

typedef struct
{
    int tic;
    unsigned char key;
    int pressed;
} input_event_t;

static input_event_t input_events[MAX_EVENTS];
static size_t input_event_count;
static size_t input_event_index;
static int input_tic;
static int input_poll_active;
static int frame_limit = 120;
static int warmup_frames = 64;
static int simulation_frame_count;
static int captured_frame_count;
static int booted;
static int doom_started;
static uint32_t fake_ticks_ms;
static const char *frame_dir;
static const char *result_file;

pixel_t *DG_ScreenBuffer = NULL;

extern boolean singletics;
extern int gametic;

static void fail(const char *message)
{
    fprintf(stderr, "AISL_REFERENCE_ERROR: %s\n", message);
    exit(2);
}

static unsigned char parse_key(const char *token)
{
    if (strlen(token) == 1)
        return (unsigned char)token[0];
    if (strcmp(token, "left") == 0)
        return KEY_LEFTARROW;
    if (strcmp(token, "right") == 0)
        return KEY_RIGHTARROW;
    if (strcmp(token, "up") == 0)
        return KEY_UPARROW;
    if (strcmp(token, "down") == 0)
        return KEY_DOWNARROW;
    if (strcmp(token, "use") == 0)
        return KEY_USE;
    if (strcmp(token, "fire") == 0)
        return KEY_FIRE;
    if (strcmp(token, "shift") == 0)
        return KEY_RSHIFT;
    if (strcmp(token, "enter") == 0)
        return KEY_ENTER;
    if (strcmp(token, "escape") == 0)
        return KEY_ESCAPE;
    fail("unknown input key");
    return 0;
}

static void load_input(void)
{
    const char *input_file = getenv("AISL_INPUT_FILE");
    FILE *file;
    char line[256];

    if (input_file == NULL)
        fail("AISL_INPUT_FILE is not set");

    file = fopen(input_file, "r");
    if (file == NULL)
    {
        fprintf(stderr, "AISL_REFERENCE_ERROR: cannot open input: %s: %s\n",
                input_file, strerror(errno));
        exit(2);
    }

    while (fgets(line, sizeof(line), file) != NULL)
    {
        int tic;
        int pressed;
        char key[32];

        if (line[0] == '#' || line[0] == '\n')
            continue;
        if (sscanf(line, "%d %31s %d", &tic, key, &pressed) != 3)
            fail("malformed input event");
        if (input_event_count >= MAX_EVENTS || tic < 0 || pressed < 0 || pressed > 1)
            fail("invalid input event");
        input_events[input_event_count].tic = tic;
        input_events[input_event_count].key = parse_key(key);
        input_events[input_event_count].pressed = pressed;
        input_event_count++;
    }

    fclose(file);
}

static void write_frame(int frame_number)
{
    char path[1024];
    FILE *file;
    unsigned char rgb[FRAME_WIDTH * FRAME_HEIGHT * 3];
    int i;
    int pixels = FRAME_WIDTH * FRAME_HEIGHT;

    if (frame_dir == NULL)
        fail("AISL_FRAME_DIR is not set");
    if (snprintf(path, sizeof(path), "%s/frame-%06d.rgb", frame_dir, frame_number)
        >= (int)sizeof(path))
        fail("frame path is too long");

    for (i = 0; i < pixels; ++i)
    {
        uint32_t pixel = DG_ScreenBuffer[i];
        rgb[i * 3 + 0] = (unsigned char)((pixel >> 16) & 0xff);
        rgb[i * 3 + 1] = (unsigned char)((pixel >> 8) & 0xff);
        rgb[i * 3 + 2] = (unsigned char)(pixel & 0xff);
    }

    file = fopen(path, "wb");
    if (file == NULL)
    {
        fprintf(stderr, "AISL_REFERENCE_ERROR: cannot write frame: %s: %s\n",
                path, strerror(errno));
        exit(2);
    }
    if (fwrite(rgb, 1, sizeof(rgb), file) != sizeof(rgb))
        fail("short frame write");
    fclose(file);
    captured_frame_count++;
}

void DG_Init(void)
{
    const char *limit = getenv("AISL_FRAME_COUNT");

    frame_dir = getenv("AISL_FRAME_DIR");
    result_file = getenv("AISL_RESULT_FILE");
    if (limit != NULL)
        frame_limit = atoi(limit);
    limit = getenv("AISL_FRAME_WARMUP");
    if (limit != NULL)
        warmup_frames = atoi(limit);
    if (frame_limit < 1 || frame_limit > 10000)
        fail("AISL_FRAME_COUNT must be between 1 and 10000");
    if (warmup_frames < 0 || warmup_frames > 10000)
        fail("AISL_FRAME_WARMUP must be between 0 and 10000");

    load_input();
    booted = 1;
    puts("AISL_BOOTED");
    fflush(stdout);
}

void DG_DrawFrame(void)
{
    if (!doom_started)
    {
        doom_started = 1;
        puts("AISL_DOOM_STARTED");
        fflush(stdout);
    }
    if (simulation_frame_count >= warmup_frames
        && captured_frame_count < frame_limit)
        write_frame(captured_frame_count);
    simulation_frame_count++;
}

void DG_SleepMs(uint32_t ms)
{
    fake_ticks_ms += ms == 0 ? 29 : ms;
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
        *pressed = input_events[input_event_index].pressed;
        *key = input_events[input_event_index].key;
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
    DG_ScreenBuffer = calloc(DOOMGENERIC_RESX * DOOMGENERIC_RESY, sizeof(uint32_t));
    if (DG_ScreenBuffer == NULL)
        fail("cannot allocate framebuffer");

    DG_Init();
    /* The ordinary game loop is driven one deterministic tic at a time. */
    singletics = true;
    D_DoomMain();
}

int main(int argc, char **argv)
{
    doomgeneric_Create(argc, argv);

    while (captured_frame_count < frame_limit)
        doomgeneric_Tick();

    if (!booted || !doom_started)
        fail("reference did not boot DOOM");
    if (result_file != NULL)
    {
        FILE *file = fopen(result_file, "w");
        if (file == NULL)
            fail("cannot write result file");
        fprintf(file, "{\"booted\":true,\"doom_started\":true,\"frames\":%d,\"warmup_frames\":%d,\"simulation_frames\":%d,\"tics\":%d}\n",
                captured_frame_count, warmup_frames, simulation_frame_count, gametic);
        fclose(file);
    }
    return 0;
}
