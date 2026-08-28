DOOM_SRC := ../../software/doomgeneric/doomgeneric
BUILD ?= build

# Override CROSS_PREFIX (including the trailing dash) when needed. The helper
# also resolves the pinned cache from linked replay worktrees via Git common-dir.
CROSS_PREFIX ?= $(shell ../../tools/riscv-prefix 2>/dev/null)

CC := $(CROSS_PREFIX)gcc
OBJCOPY := $(CROSS_PREFIX)objcopy
OBJDUMP := $(CROSS_PREFIX)objdump
READELF := $(CROSS_PREFIX)readelf
NM := $(CROSS_PREFIX)nm
SIZE := $(CROSS_PREFIX)size

ARCH ?= rv32im
ARCH_FLAGS := -march=$(ARCH) -mabi=ilp32 -mcmodel=medany -mstrict-align
OPTIMIZATION ?= -O3
LTO_FLAGS ?=
DEBUG_PREFIX_FLAGS := '-fdebug-prefix-map=$(CURDIR)=workspace/firmware/doom'
CPPFLAGS := -I. -I$(DOOM_SRC) -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200
CFLAGS := $(ARCH_FLAGS) -std=gnu11 $(OPTIMIZATION) $(LTO_FLAGS) -g3 -ffreestanding \
	$(DEBUG_PREFIX_FLAGS) \
	-ffunction-sections -fdata-sections -fno-strict-aliasing -fwrapv \
	-fno-unwind-tables -fno-asynchronous-unwind-tables \
	-MMD -MP
PORT_WARNINGS := -Wall -Wextra -Werror -Wno-unused-parameter
DOOM_WARNINGS := -Wall -Wextra -Wno-unused-parameter -Wno-unused-function \
	-Wno-sign-compare -Wno-missing-field-initializers \
	-Wno-implicit-fallthrough -Wno-unused-variable \
	-Wno-unused-const-variable -Wno-unused-but-set-variable \
	-Wno-unused-but-set-parameter -Wno-enum-conversion \
	-Wno-type-limits -Wno-format -Wno-dangling-pointer
ASFLAGS := $(ARCH_FLAGS) -g3 $(DEBUG_PREFIX_FLAGS) -MMD -MP
LDFLAGS := $(ARCH_FLAGS) $(LTO_FLAGS) $(DEBUG_PREFIX_FLAGS) -nostartfiles -static \
	-Wl,--gc-sections -Wl,--build-id=none -Wl,-Map,$(BUILD)/doom.map \
	-T linker.ld
LDLIBS := -lm -lc -lgcc

DOOM_SOURCES := \
	dummy.c am_map.c doomdef.c doomstat.c dstrings.c d_event.c d_items.c \
	d_iwad.c d_loop.c d_main.c d_mode.c d_net.c f_finale.c f_wipe.c \
	g_game.c hu_lib.c hu_stuff.c info.c i_cdmus.c i_endoom.c i_joystick.c \
	i_scale.c i_sound.c i_timer.c memio.c m_argv.c m_bbox.c m_cheat.c \
	m_config.c m_controls.c m_fixed.c m_menu.c m_misc.c m_random.c \
	p_ceilng.c p_doors.c p_enemy.c p_floor.c p_inter.c p_lights.c p_map.c \
	p_maputl.c p_mobj.c p_plats.c p_pspr.c p_saveg.c p_setup.c p_sight.c \
	p_spec.c p_switch.c p_telept.c p_tick.c p_user.c r_bsp.c r_data.c \
	r_draw.c r_main.c r_plane.c r_segs.c r_sky.c r_things.c sha1.c \
	sounds.c statdump.c st_lib.c st_stuff.c s_sound.c tables.c v_video.c \
	wi_stuff.c w_checksum.c w_file.c w_main.c w_wad.c z_zone.c i_input.c \
	i_video.c
PORT_SOURCES := doomgeneric_baremetal.c i_system_baremetal.c \
	w_file_mmap.c syscalls.c

DOOM_OBJECTS := $(patsubst %.c,$(BUILD)/doom/%.o,$(DOOM_SOURCES))
PORT_OBJECTS := $(patsubst %.c,$(BUILD)/port/%.o,$(PORT_SOURCES))
OBJECTS := $(BUILD)/port/crt0.o $(PORT_OBJECTS) $(DOOM_OBJECTS)
DEPS := $(OBJECTS:.o=.d)

.PHONY: all clean verify toolchain

all: verify $(BUILD)/SHA256SUMS

toolchain:
	@test -n "$(CROSS_PREFIX)" || { \
		echo "error: riscv-none-elf toolchain not found; set CROSS_PREFIX" >&2; \
		exit 1; \
	}
	@command -v "$(CC)" >/dev/null 2>&1 || test -x "$(CC)" || { \
		echo "error: $(CC) is not executable" >&2; exit 1; \
	}

$(BUILD)/doom.elf: toolchain $(OBJECTS) linker.ld
	"$(CC)" $(LDFLAGS) $(OBJECTS) $(LDLIBS) -o $@
	LC_ALL=C sed -E \
		-e 's#/[^[:space:]]*/cc[[:alnum:]]+(\.ltrans[0-9]+\.ltrans\.o)#<gcc-lto-temp>\1#g' \
		-e 's#/[^[:space:]]*/cc[[:alnum:]]+\.debug\.temp\.o#<gcc-debug-temp.o>#g' \
		$(BUILD)/doom.map > $(BUILD)/doom.map.normalized
	mv $(BUILD)/doom.map.normalized $(BUILD)/doom.map

$(BUILD)/doom.bin: $(BUILD)/doom.elf
	"$(OBJCOPY)" -O binary $< $@

# The linker emits the map as a side effect of the ELF link.  Give parallel
# make an explicit dependency edge so a fresh configurable build directory is
# race-free.
$(BUILD)/doom.map: $(BUILD)/doom.elf
	@test -s $@

$(BUILD)/doom.dis: $(BUILD)/doom.elf
	"$(OBJDUMP)" -d -S -w $< > $@

$(BUILD)/doom.sections: $(BUILD)/doom.elf
	"$(READELF)" -W -h -l -S $< > $@
	"$(NM)" -n $< >> $@

verify: $(BUILD)/doom.bin $(BUILD)/doom.dis $(BUILD)/doom.sections
	@undefined="$$('$(NM)' -u $(BUILD)/doom.elf)"; \
		test -z "$$undefined" || { \
			echo "error: unresolved symbols:" >&2; \
			echo "$$undefined" >&2; \
			exit 1; \
		}
	@"$(READELF)" -W -h $(BUILD)/doom.elf | grep -q 'Machine:.*RISC-V'
	@"$(READELF)" -W -h $(BUILD)/doom.elf | grep -q 'Entry point address:.*0x0'
	@grep -q 'ASSERT ((__image_end <= __heap_end)' $(BUILD)/doom.map
	@grep -q 'ASSERT ((__stack_top < 0x2000000)' $(BUILD)/doom.map
	@"$(SIZE)" $(BUILD)/doom.elf

$(BUILD)/SHA256SUMS: $(BUILD)/doom.elf $(BUILD)/doom.bin \
		$(BUILD)/doom.map $(BUILD)/doom.dis $(BUILD)/doom.sections
	cd $(BUILD) && shasum -a 256 doom.elf doom.bin doom.map doom.dis doom.sections > SHA256SUMS

$(BUILD)/doom/%.o: $(DOOM_SRC)/%.c Makefile
	@mkdir -p $(@D)
	"$(CC)" $(CPPFLAGS) $(CFLAGS) $(DOOM_WARNINGS) -c $< -o $@

$(BUILD)/port/%.o: %.c Makefile
	@mkdir -p $(@D)
	"$(CC)" $(CPPFLAGS) $(CFLAGS) $(PORT_WARNINGS) -c $< -o $@

$(BUILD)/port/crt0.o: crt0.S Makefile
	@mkdir -p $(@D)
	"$(CC)" $(CPPFLAGS) $(ASFLAGS) -c $< -o $@

clean:
	$(RM) -r $(BUILD)

-include $(DEPS)
