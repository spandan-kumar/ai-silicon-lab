/* Minimal system layer retaining doomgeneric's deterministic engine semantics. */

#include "config.h"
#include "doomtype.h"
#include "i_system.h"
#include "m_argv.h"
#include "m_misc.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define DEFAULT_RAM 6
#define MIN_RAM 6
#define DOS_MEM_DUMP_SIZE 10

typedef struct exit_entry_s exit_entry_t;

struct exit_entry_s
{
    atexit_func_t function;
    boolean run_on_error;
    exit_entry_t *next;
};

static exit_entry_t *exit_functions;
static boolean already_quitting;

static const unsigned char mem_dump_dos622[DOS_MEM_DUMP_SIZE] = {
    0x57, 0x92, 0x19, 0x00, 0xf4, 0x06, 0x70, 0x00, 0x16, 0x00,
};
static const unsigned char mem_dump_win98[DOS_MEM_DUMP_SIZE] = {
    0x9e, 0x0f, 0xc9, 0x00, 0x65, 0x04, 0x70, 0x00, 0x16, 0x00,
};
static const unsigned char mem_dump_dosbox[DOS_MEM_DUMP_SIZE] = {
    0x00, 0x00, 0x00, 0xf1, 0x00, 0x00, 0x00, 0x00, 0x07, 0x00,
};
static unsigned char mem_dump_custom[DOS_MEM_DUMP_SIZE];
static const unsigned char *dos_mem_dump = mem_dump_dos622;

void I_AtExit(atexit_func_t function, boolean run_on_error)
{
    exit_entry_t *entry = malloc(sizeof(*entry));

    if (entry == NULL)
        I_Error("I_AtExit: allocation failed");
    entry->function = function;
    entry->run_on_error = run_on_error;
    entry->next = exit_functions;
    exit_functions = entry;
}

void I_Tactile(int on, int off, int total)
{
    (void)on;
    (void)off;
    (void)total;
}

byte *I_ZoneBase(int *size)
{
    int default_ram = DEFAULT_RAM;
    int min_ram = MIN_RAM;
    int parameter = M_CheckParmWithArgs("-mb", 1);
    byte *zone = NULL;

    if (parameter > 0)
    {
        default_ram = atoi(myargv[parameter + 1]);
        min_ram = default_ram;
    }

    while (zone == NULL)
    {
        if (default_ram < min_ram)
            I_Error("Unable to allocate %i MiB of RAM for zone", default_ram);
        *size = default_ram * 1024 * 1024;
        zone = malloc((size_t)*size);
        if (zone == NULL)
            default_ram--;
    }

    printf("zone memory: %p, %x allocated for zone\n", zone, *size);
    return zone;
}

void I_PrintBanner(char *message)
{
    int spaces = 35 - (int)(strlen(message) / 2u);
    int i;

    for (i = 0; i < spaces; ++i)
        putchar(' ');
    puts(message);
}

void I_PrintDivider(void)
{
    int i;

    for (i = 0; i < 75; ++i)
        putchar('=');
    putchar('\n');
}

void I_PrintStartupBanner(char *game_description)
{
    I_PrintDivider();
    I_PrintBanner(game_description);
    I_PrintDivider();
    printf(" " PACKAGE_NAME " is free software, covered by the GNU General Public\n"
           " License.  There is NO warranty; not even for MERCHANTABILITY or FITNESS\n"
           " FOR A PARTICULAR PURPOSE. You are welcome to change and distribute\n"
           " copies under certain conditions. See the source for more information.\n");
    I_PrintDivider();
}

boolean I_ConsoleStdout(void)
{
    return false;
}

void I_Quit(void)
{
    exit_entry_t *entry;

    for (entry = exit_functions; entry != NULL; entry = entry->next)
        entry->function();
}

void I_Error(char *error, ...)
{
    va_list args;
    exit_entry_t *entry;

    if (already_quitting)
        fprintf(stderr, "Warning: recursive call to I_Error detected.\n");
    already_quitting = true;

    va_start(args, error);
    vfprintf(stderr, error, args);
    va_end(args);
    fprintf(stderr, "\n\n");

    for (entry = exit_functions; entry != NULL; entry = entry->next)
        if (entry->run_on_error)
            entry->function();

    fflush(NULL);
    exit(2);
}

boolean I_GetMemoryValue(unsigned int offset, void *value, int size)
{
    static boolean first_time = true;

    if (first_time)
    {
        int parameter;
        int i = 0;
        int parsed;

        first_time = false;
        parameter = M_CheckParmWithArgs("-setmem", 1);
        if (parameter > 0)
        {
            if (!strcasecmp(myargv[parameter + 1], "dos622"))
                dos_mem_dump = mem_dump_dos622;
            if (!strcasecmp(myargv[parameter + 1], "dos71"))
                dos_mem_dump = mem_dump_win98;
            else if (!strcasecmp(myargv[parameter + 1], "dosbox"))
                dos_mem_dump = mem_dump_dosbox;
            else
            {
                for (i = 0; i < DOS_MEM_DUMP_SIZE; ++i)
                {
                    parameter++;
                    if (parameter >= myargc || myargv[parameter][0] == '-')
                        break;
                    M_StrToInt(myargv[parameter], &parsed);
                    mem_dump_custom[i++] = (unsigned char)parsed;
                }
                dos_mem_dump = mem_dump_custom;
            }
        }
    }

    if (offset >= DOS_MEM_DUMP_SIZE
        || size < 1
        || offset + (unsigned int)size > DOS_MEM_DUMP_SIZE)
        return false;

    switch (size)
    {
        case 1:
            *(unsigned char *)value = dos_mem_dump[offset];
            return true;
        case 2:
            *(unsigned short *)value = (unsigned short)(
                dos_mem_dump[offset] | (dos_mem_dump[offset + 1] << 8));
            return true;
        case 4:
            *(unsigned int *)value =
                dos_mem_dump[offset]
                | (dos_mem_dump[offset + 1] << 8)
                | (dos_mem_dump[offset + 2] << 16)
                | (dos_mem_dump[offset + 3] << 24);
            return true;
        default:
            return false;
    }
}
