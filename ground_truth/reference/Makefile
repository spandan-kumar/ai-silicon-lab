ROOT := $(abspath $(CURDIR)/../..)
VENDOR := $(CURDIR)/vendor/doomgeneric
BUILD_DIR ?= $(ROOT)/.aisl/reference-build/obj
OUTPUT ?= $(ROOT)/.aisl/reference-build/doomgeneric-headless

CC ?= cc
CPPFLAGS += -I$(VENDOR) -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200
CFLAGS ?= -O2 -g -DNORMALUNIX -DLINUX -DSNDSERV -D_DEFAULT_SOURCE
LDLIBS ?= -lm

# This is the upstream engine plus the small deterministic laboratory port.
# doomgeneric.c is intentionally omitted because the port supplies the
# lifecycle entry point and framebuffer symbol.
SOURCES := \
    dummy.c am_map.c doomdef.c doomstat.c dstrings.c d_event.c d_items.c \
    d_iwad.c d_loop.c d_main.c d_mode.c d_net.c f_finale.c f_wipe.c \
    g_game.c hu_lib.c hu_stuff.c info.c i_cdmus.c i_endoom.c i_joystick.c \
    i_scale.c i_sound.c i_system.c i_timer.c memio.c m_argv.c m_bbox.c \
    m_cheat.c m_config.c m_controls.c m_fixed.c m_menu.c m_misc.c \
    m_random.c p_ceilng.c p_doors.c p_enemy.c p_floor.c p_inter.c \
    p_lights.c p_map.c p_maputl.c p_mobj.c p_plats.c p_pspr.c p_saveg.c \
    p_setup.c p_sight.c p_spec.c p_switch.c p_telept.c p_tick.c p_user.c \
    r_bsp.c r_data.c r_draw.c r_main.c r_plane.c r_segs.c r_sky.c \
    r_things.c sha1.c sounds.c statdump.c st_lib.c st_stuff.c s_sound.c \
    tables.c v_video.c wi_stuff.c w_checksum.c w_file.c w_main.c w_wad.c \
    z_zone.c w_file_stdc.c i_input.c i_video.c doomgeneric_headless.c
OBJECTS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SOURCES))

.PHONY: all clean

all: $(OUTPUT)

$(OUTPUT): $(OBJECTS)
	@mkdir -p $(dir $@)
	$(CC) $(LDFLAGS) $(OBJECTS) $(LDLIBS) -o $@

$(BUILD_DIR)/%.o: $(VENDOR)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

clean:
	$(RM) -r $(BUILD_DIR) $(OUTPUT)
