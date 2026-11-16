# ---------------------------------------------------------------------------
# The game: pret/pokeplatinum compiled with GCC against the sinjoh NitroSDK
# and NitroSystem compatibility layers.
#
#   make -f engine/game.mk TARGET=3ds lib       the game's object library
#   make -f engine/game.mk TARGET=3ds program   the whole program (see the
#                                               root Makefile)
#
# The layout follows pokeplatinum-3ds's game Makefile (GPL-3.0), retargeted
# onto kohjoh's runtime: its renderer and 3ds_port app are not used, only the
# game-side build rules and header generation.
#
# All generated headers live under build/, and the game's data archives are
# never built: the game reads the player's own data pack.
# ---------------------------------------------------------------------------

.DEFAULT_GOAL := lib
comma := ,

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))..)
include $(ROOT)/engine/compat/common.mk

GAME := $(ROOT)/build/upstream
OUT  := $(ROOT)/build/game/$(TARGET)
LIB  := $(OUT)/libplatinum_game.a
NNS_PORT := $(ROOT)/engine/compat/nitrosystem
LIBNITRO := $(NITRO)/build/$(TARGET)/libnitro.a
LIBNNS   := $(NNS_PORT)/build/$(TARGET)/libnitrosystem.a
TOOLS    := $(ROOT)/tools/game

ifeq ($(wildcard $(GAME)/include/pch/global_pch.h),)
$(error Game decompilation not found at $(GAME). Run: python tools/game/bootstrap.py)
endif

# Every original pokeplatinum C file, unmodified apart from patches/pokeplatinum.
GAME_BLOCKED :=
GAME_ALL_SRCS := $(shell python3 $(TOOLS)/game_sources.py $(GAME))
GAME_SRCS := $(filter-out $(GAME_BLOCKED),$(GAME_ALL_SRCS))
GAME_OBJS := $(GAME_SRCS:%.c=$(OUT)/src/%.o)

# The game's own libraries linked into the same program (libcrypto, libgds,
# libspl). The online libraries are stubbed.
GAME_LIBS := crypto gds spl
GAME_LIB_SRCS := $(sort $(foreach l,$(GAME_LIBS),$(wildcard $(GAME)/lib/$(l)/src/*.c)))
GAME_OBJS += $(GAME_LIB_SRCS:$(GAME)/%.c=$(OUT)/%.o)

# The trainer AI script: data written with assembler macros.
TRAINER_AI_O := $(OUT)/src/battle/trainer_ai/script.o
GAME_OBJS += $(TRAINER_AI_O)

# Game headers define functions with plain `inline`. Metrowerks kept one
# copy; GCC exports one from every including file, so mark the duplicates
# weak after compiling, as kohjoh does for NitroSystem's headers.
GAME_HEADER_DEFS := $(OUT)/gen/game_header_defs.syms
CENSUS_OBJS := $(GAME_OBJS)

# --- generated headers -----------------------------------------------------

CONSTANTS_DIR := $(ROOT)/build/game-constants
CONSTANTS_STAMP := $(CONSTANTS_DIR)/.game-headers-ready
GAME_MANIFESTS := $(wildcard $(GAME)/generated/*.txt)

$(CONSTANTS_STAMP): $(GAME)/generated/meson.build $(GAME)/subprojects/metang.wrap $(GAME_MANIFESTS) $(TOOLS)/prepare_game_constants.py
	@python3 $(TOOLS)/prepare_game_constants.py --upstream $(GAME) --output $(CONSTANTS_DIR)
	@touch $@

RESOURCE_DIR := $(ROOT)/build/game-resource-headers
RESOURCE_HEADER := $(RESOURCE_DIR)/res/pokemon/regional_pokedex_size.h
RESOURCE_MANIFEST := $(GAME)/res/pokemon/sinnoh_pokedex.json

$(RESOURCE_HEADER): $(RESOURCE_MANIFEST) $(TOOLS)/prepare_game_resource_headers.py
	@python3 $(TOOLS)/prepare_game_resource_headers.py --source="$<" --output="$@"

TEXT_BANK_JSON := $(wildcard $(GAME)/res/text/*.json)
TEXT_BANK_STAMP := $(RESOURCE_DIR)/.text-bank-ids-ready

$(TEXT_BANK_STAMP): $(TEXT_BANK_JSON) $(TOOLS)/prepare_game_text_bank_headers.py
	@python3 $(TOOLS)/prepare_game_text_bank_headers.py --upstream="$(GAME)" --output="$(RESOURCE_DIR)"
	@touch $@

MOVE_TEXT_DATA := $(wildcard $(GAME)/res/moves/*/data.json)
MOVE_TEXT_STAMP := $(RESOURCE_DIR)/.move-text-ids-ready

$(MOVE_TEXT_STAMP): $(GAME)/generated/moves.txt $(MOVE_TEXT_DATA) $(TOOLS)/prepare_game_move_text_headers.py
	@python3 $(TOOLS)/prepare_game_move_text_headers.py --upstream="$(GAME)" --output="$(RESOURCE_DIR)"
	@touch $@

SPECIES_TEXT_DATA := $(wildcard $(GAME)/res/pokemon/*/data.json)
SPECIES_TEXT_STAMP := $(RESOURCE_DIR)/.species-text-ids-ready

$(SPECIES_TEXT_STAMP): $(GAME)/generated/species.txt $(SPECIES_TEXT_DATA) $(TOOLS)/prepare_game_species_text_headers.py
	@python3 $(TOOLS)/prepare_game_species_text_headers.py --upstream="$(GAME)" --output="$(RESOURCE_DIR)"
	@touch $@

SOUND_MANIFEST := $(GAME)/res/sound/pl_sound_data.json
SOUND_HEADER := $(RESOURCE_DIR)/res/sound/pl_sound_data.naix

$(SOUND_HEADER): $(SOUND_MANIFEST) $(TOOLS)/prepare_game_sound_naix.py
	@python3 $(TOOLS)/prepare_game_sound_naix.py --upstream="$(GAME)" --output="$(RESOURCE_DIR)"

ARCHIVE_ORDERS := $(shell find $(GAME)/res -type f \( -name '*.order' -o -name meson.build \))
ARCHIVE_STAMP := $(RESOURCE_DIR)/.archive-naix-ready

$(ARCHIVE_STAMP): $(ARCHIVE_ORDERS) $(TOOLS)/prepare_game_graphics_naix.py
	@python3 $(TOOLS)/prepare_game_graphics_naix.py --upstream="$(GAME)" --output="$(RESOURCE_DIR)"
	@touch $@

ORDERGEN_STAMP := $(RESOURCE_DIR)/.ordergen-naix-ready

$(ORDERGEN_STAMP): $(wildcard $(GAME)/tools/ordergen/*.py) $(GAME)/generated/trainer_classes.txt \
                   $(GAME)/generated/species.txt $(TOOLS)/prepare_game_ordergen_naix.py \
                   $(TOOLS)/prepare_game_graphics_naix.py
	@python3 $(TOOLS)/prepare_game_ordergen_naix.py --upstream="$(GAME)" --output="$(RESOURCE_DIR)"
	@touch $@

DATAPROC_DIR := $(ROOT)/build/game-tools
DATAPROC_STAMP := $(RESOURCE_DIR)/.dataproc-ready
DATAPROC_INPUTS := $(shell find $(GAME)/tools/dataproc $(GAME)/tools/enumproc \
        $(GAME)/tools/nitroarc/lib -type f) \
    $(shell find $(GAME)/res/pokemon $(GAME)/res/items $(GAME)/res/trainers \
        $(GAME)/res/graphics/sprite_templates -name '*.json') \
    $(GAME)/res/fonts/arrow_cursor.png $(GAME)/res/graphics/battle/healthbox/healthbox_parts.png

$(DATAPROC_STAMP): $(DATAPROC_INPUTS) $(CONSTANTS_STAMP) $(ARCHIVE_STAMP) $(ORDERGEN_STAMP) \
                   $(TOOLS)/prepare_game_dataproc.py $(TOOLS)/png_embed.py
	@python3 $(TOOLS)/prepare_game_dataproc.py --upstream "$(GAME)" --constants "$(CONSTANTS_DIR)" \
	    --resources "$(RESOURCE_DIR)" --work "$(DATAPROC_DIR)"
	@touch $@

NETWORK_DIR := $(ROOT)/build/game-network-sdks
NETWORK_STAMP := $(NETWORK_DIR)/.headers-ready
NETWORK_WRAPS := $(GAME)/subprojects/NitroDWC.wrap $(GAME)/subprojects/NitroWiFi.wrap \
                 $(GAME)/subprojects/libvct.wrap

$(NETWORK_STAMP): $(NETWORK_WRAPS) $(TOOLS)/prepare_game_network_headers.py
	@python3 $(TOOLS)/prepare_game_network_headers.py --upstream="$(GAME)" --output="$(NETWORK_DIR)"
	@touch $@

GCC14_ERRORS := -Werror=implicit-function-declaration \
                -Wno-error=implicit-int -Wno-error=int-conversion \
                -Wno-error=incompatible-pointer-types

GENERATED_HEADER_DIRS := $(addprefix -I$(RESOURCE_DIR)/,$(sort $(patsubst $(GAME)/%/,%,$(dir \
    $(shell grep -rlE "\.(naix|h)'" --include=meson.build $(GAME)/res)))))

OVERLAY_IDS   := $(ROOT)/build/game-link/overlay_ids.ld
OVERLAY_IDS_H := $(ROOT)/build/game-link/overlay_ids.h

$(OVERLAY_IDS) $(OVERLAY_IDS_H) &: $(GAME)/platinum.us/main.lsf $(TOOLS)/prepare_game_overlay_ids.py
	@python3 $(TOOLS)/prepare_game_overlay_ids.py --lsf $< --output $(OVERLAY_IDS) --header $(OVERLAY_IDS_H)
	@touch $(OVERLAY_IDS) $(OVERLAY_IDS_H)

GAME_GENERATED := $(CONSTANTS_STAMP) $(RESOURCE_HEADER) $(TEXT_BANK_STAMP) $(MOVE_TEXT_STAMP) \
                  $(SPECIES_TEXT_STAMP) $(SOUND_HEADER) $(ARCHIVE_STAMP) $(ORDERGEN_STAMP) \
                  $(DATAPROC_STAMP) $(NETWORK_STAMP) $(OVERLAY_IDS_H)

GAME_CFLAGS := $(PORT_CFLAGS) $(SDK_INCLUDES) $(NNS_INCLUDES) \
               -I$(GAME)/include -I$(GAME)/asm -I$(GAME) -I$(CONSTANTS_DIR) \
               -I$(ROOT)/engine/compat/platinum/include \
               -I$(RESOURCE_DIR) -I$(GAME)/lib/spl/include \
               -I$(NETWORK_DIR)/NitroDWC/include \
               -I$(NETWORK_DIR)/NitroDWC/include/gs \
               -I$(NETWORK_DIR)/NitroDWC/include/base \
               -I$(NETWORK_DIR)/NitroWiFi/include \
               -I$(GAME)/lib/gds/include \
               -I$(GAME)/lib/ppwlobby/include -I$(GAME)/lib/crypto/include \
               -I$(NETWORK_DIR)/libvct/include \
               -I$(CONSTANTS_DIR)/generated $(GENERATED_HEADER_DIRS) \
               -DPOKEPLATINUM_REVISION=1 -DPOKEPLATINUM_GENERATED_ENUM \
               -D_MSL_RESTRICT= -DPM_KEEP_ASSERTS \
               -DGAME_VERSION=VERSION_PLATINUM \
               -DGAME_LANGUAGE=LANGUAGE_ENGLISH \
               -D_NITRO -DLINK_PPWLOBBY \
               -include $(GAME)/include/pch/global_pch.h -include $(OVERLAY_IDS_H) \
               -ffunction-sections -fdata-sections \
               $(GCC14_ERRORS)

.PHONY: all lib clean libnitro libnitrosystem

ifeq ($(IS_HOST),yes)
all: $(LIB)
else
all: lib
endif

lib: $(LIB)

libnitro:
	@$(MAKE) --no-print-directory -C $(NITRO) TARGET=$(TARGET) lib

libnitrosystem:
	@$(MAKE) --no-print-directory -C $(NNS_PORT) TARGET=$(TARGET) lib

$(LIBNITRO): libnitro
$(LIBNNS): libnitrosystem

$(NNS_INLINE_SYMS): | libnitrosystem
	@test -f $@

$(OUT)/src/%.o: $(GAME)/src/%.c $(NNS_INLINE_SYMS) $(GAME_GENERATED) | libnitrosystem
	@mkdir -p $(dir $@)
	@echo "  GAME CC $(notdir $<)"
	@$(CC) $(GAME_CFLAGS) -c $< -o $@
	@$(WEAKEN_NNS_INLINE)

$(OUT)/lib/%.o: $(GAME)/lib/%.c $(NNS_INLINE_SYMS) $(GAME_GENERATED) | libnitrosystem
	@mkdir -p $(dir $@)
	@echo "  GAME CC lib/$*.c"
	@$(CC) $(GAME_CFLAGS) -I$(dir $<) -c $< -o $@
	@$(WEAKEN_NNS_INLINE)

$(TRAINER_AI_O): $(GAME)/src/battle/trainer_ai/script.s $(GAME_GENERATED)
	@mkdir -p $(dir $@)
	@echo "  GAME AS battle/trainer_ai/script.s"
	@$(CC) $(filter -m%,$(PORT_CFLAGS)) $(if $(IS_HOST),-Wa$(comma)--noexecstack) \
	    -I$(GAME)/include -I$(GAME)/asm -I$(CONSTANTS_DIR) -x assembler-with-cpp -c $< -o $@

WIFI_STUBS_C := $(OUT)/gen/wifi_stubs.c
WIFI_STUBS_O := $(OUT)/gen/wifi_stubs.o

$(WIFI_STUBS_C): $(GAME_HEADER_DEFS) $(TOOLS)/make_game_wifi_stubs.py
	@python3 $(TOOLS)/make_game_wifi_stubs.py --nm $(NM) --output $@ \
	    --headers $(NETWORK_DIR) $(GAME)/lib/ppwlobby $(SDK)/include/nitro \
	    --sources $(NETWORK_DIR)/NitroDWC $(NETWORK_DIR)/NitroWiFi $(GAME)/lib/ppwlobby -- $(GAME_OBJS)
	@touch $@

$(WIFI_STUBS_O): $(WIFI_STUBS_C)
	@$(CC) $(PORT_CFLAGS) $(SDK_INCLUDES) -c $< -o $@

OVERLAY_TABLE_C := $(OUT)/gen/overlay_table.c

$(GAME_HEADER_DEFS): $(CENSUS_OBJS) $(GAME)/platinum.us/main.lsf $(TOOLS)/game_overlays.py
	@mkdir -p $(dir $@)
	@# Objects already made weak by an earlier run no longer show up as
	@# duplicates, so keep the names found before.
	$(file >$(OUT)/census_objs.rsp,$(CENSUS_OBJS))@{ cat $@ 2>/dev/null; xargs -a $(OUT)/census_objs.rsp -n 100 $(NM) -g --defined-only | awk 'NF == 3 && $$2 ~ /^[TDBR]$$/ { print $$3 }' | sort | uniq -d; } | sort -u > $@.new
	@mv $@.new $@
	@if [ -s $@ ]; then for o in $(CENSUS_OBJS); do $(OBJCOPY) --weaken-symbols=$@ $$o; done; fi
	@echo "  $$(wc -l < $@) game header functions defined in several objects, made weak"
	@python3 $(TOOLS)/game_overlays.py --lsf $(GAME)/platinum.us/main.lsf --upstream $(GAME) \
	    --objdir $(OUT) --objcopy $(OBJCOPY) --output $(OVERLAY_TABLE_C)
	@touch $@

$(OVERLAY_TABLE_C): $(GAME_HEADER_DEFS)
	@test -f $@

GAME_OBJS_RSP := $(OUT)/game_objs.rsp
# devkitARM's tools are native Windows programs: response-file contents are
# not path-converted by MSYS, so spell them as C:/... there.
native_rsp = sed -e 's|^/\([a-zA-Z]\)/|\U\1:/|' -e 's| /\([a-zA-Z]\)/| \U\1:/|g' $(1) > $(1).win
write_game_objs_rsp = $(file >$(GAME_OBJS_RSP),$(GAME_OBJS) $(WIFI_STUBS_O))

$(LIB): $(GAME_HEADER_DEFS) $(WIFI_STUBS_O)
	@rm -f $@
	$(write_game_objs_rsp)
	@$(call native_rsp,$(GAME_OBJS_RSP))
	@$(AR) rcs $@ @$(GAME_OBJS_RSP).win
	@echo "built $@ ($(words $(GAME_SRCS)) of $(words $(GAME_ALL_SRCS)) game C files)"

# --- the program -----------------------------------------------------------
#
# The DS side (kohjoh's runtime and compat, 4-byte enums) and the 3DS side
# (libctru/citro3d, short enums) are compiled separately and meet only at
# engine/runtime/kj_bridge.h.

ENGINE_DS_SRCS := $(sort $(wildcard $(ROOT)/engine/runtime/*.c)) \
                  $(sort $(wildcard $(ROOT)/engine/compat/stubs/*.c))
ENGINE_DS_OBJS := $(ENGINE_DS_SRCS:$(ROOT)/%.c=$(OUT)/ds/%.o)

ENGINE_CTR_DIRS := app graphics audio storage content diagnostics
ENGINE_CTR_SRCS := $(sort $(foreach d,$(ENGINE_CTR_DIRS),$(wildcard $(ROOT)/engine/$(d)/*.c)))
ENGINE_CTR_SRCS += $(sort $(foreach d,$(ENGINE_CTR_DIRS),$(wildcard $(ROOT)/engine/$(d)/*/*.c)))
ENGINE_CTR_OBJS := $(ENGINE_CTR_SRCS:$(ROOT)/%.c=$(OUT)/ctr/%.o)

SHADER_SRCS := $(sort $(wildcard $(ROOT)/engine/graphics/pica/shaders/*.v.pica))
SHADER_OBJS := $(foreach s,$(SHADER_SRCS),$(OUT)/shaders/$(notdir $(basename $(basename $(s))))_shbin.o)

DEVKITPRO ?= /opt/devkitpro
DEVKITARM ?= $(DEVKITPRO)/devkitARM
PICASSO := $(DEVKITPRO)/tools/bin/picasso
BIN2S   := $(DEVKITPRO)/tools/bin/bin2s
ARM_AS  := $(DEVKITARM)/bin/arm-none-eabi-as

ARM_FLAGS := -march=armv6k -mtune=mpcore -mfpu=vfp -mfloat-abi=hard -mtp=soft \
             -mword-relocations -D__3DS__

ENGINE_DS_CFLAGS := $(PORT_CFLAGS) $(SDK_INCLUDES) -I$(ROOT)/engine \
                    -I$(ROOT)/engine/runtime -I$(ROOT)/engine/compat/nitro/include \
                    -I$(ROOT)/engine/compat/pak/include
BUILD_ID_H := $(OUT)/gen/build_id.h
BUILD_SHA := $(shell git -C $(ROOT) rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
BUILD_DIRTY := $(shell test -n "$$(git -C $(ROOT) status --porcelain 2>/dev/null)" && echo 1 || echo 0)

$(BUILD_ID_H):
	@mkdir -p $(dir $@)
	@printf '/* Generated: the commit this program was built from. */\n#define HGSS_BUILD_ID "sinjoh-%s%s"\n#define HGSS_BUILD_SHA "%s"\n#define HGSS_BUILD_DIRTY %s\n' \
	    '$(BUILD_SHA)' '$(if $(filter 1,$(BUILD_DIRTY)),-dirty,)' '$(BUILD_SHA)' '$(BUILD_DIRTY)' > $@

ENGINE_CTR_CFLAGS := -std=gnu11 -O2 -g -Wall -Wno-unused-function \
                     -ffunction-sections -fdata-sections $(ARM_FLAGS) \
                     $(if $(filter 0,$(PROFILE)),-DHGSS_PROFILE_OFF) \
                     -I$(DEVKITPRO)/libctru/include -I$(ROOT)/engine \
                     -I$(ROOT)/engine/runtime -I$(OUT)/gen

$(OUT)/ds/%.o: $(ROOT)/%.c
	@mkdir -p $(dir $@)
	@echo "  DS  $(<:$(ROOT)/%=%)"
	@$(CC) $(ENGINE_DS_CFLAGS) -MMD -MP -c $< -o $@

$(OUT)/ctr/%.o: $(ROOT)/%.c | $(BUILD_ID_H)
	@mkdir -p $(dir $@)
	@echo "  CTR $(<:$(ROOT)/%=%)"
	@$(CC) $(ENGINE_CTR_CFLAGS) -MMD -MP -c $< -o $@

$(OUT)/shaders/%_shbin.o: $(ROOT)/engine/graphics/pica/shaders/%.v.pica
	@mkdir -p $(dir $@)
	@echo "  SH  $*.v.pica"
	@$(PICASSO) -o $(OUT)/shaders/$*.shbin $<
	@$(BIN2S) $(OUT)/shaders/$*.shbin > $(OUT)/shaders/$*_shbin.s
	@$(ARM_AS) -o $@ $(OUT)/shaders/$*_shbin.s

PROGRAM_ELF := $(OUT)/sinjoh.elf
PROGRAM := $(OUT)/sinjoh.3dsx

$(PROGRAM_ELF): $(ENGINE_DS_OBJS) $(ENGINE_CTR_OBJS) $(SHADER_OBJS) $(OVERLAY_TABLE_C:.c=.o) \
                $(GAME_HEADER_DEFS) $(WIFI_STUBS_O) $(LIBNITRO) $(LIBNNS)
	@mkdir -p $(dir $@)
	$(file >$(OUT)/link.rsp,$(ENGINE_DS_OBJS) $(ENGINE_CTR_OBJS) $(SHADER_OBJS) $(GAME_OBJS) $(WIFI_STUBS_O))
	@$(call native_rsp,$(OUT)/link.rsp)
	@echo "  LINK $@"
	@$(CC) $(ARM_FLAGS) -specs=3dsx.specs -L$(DEVKITPRO)/libctru/lib \
	    -L$(DEVKITPRO)/portlibs/3ds/lib \
	    -Wl,--undefined=kj_game_main -Wl,--undefined=NitroMain \
	    -Wl,--no-enum-size-warning -Wl,--gc-sections \
	    -Wl,--wrap=ErrorHandling_AssertFail \
	    @$(OUT)/link.rsp.win $(OUT)/gen/overlay_table.o \
	    -Wl,--start-group $(LIBNNS) $(LIBNITRO) -Wl,--end-group \
	    $(OVERLAY_IDS) -lcitro3d -lctru -lm -o $@

$(OUT)/gen/overlay_table.o: $(OVERLAY_TABLE_C) | libnitro
	@$(CC) $(PORT_CFLAGS) $(SDK_INCLUDES) -c $< -o $@

program: $(PROGRAM)

$(PROGRAM): $(PROGRAM_ELF)
	@$(DEVKITPRO)/tools/bin/3dsxtool $< $@

clean:
	rm -rf $(OUT)

-include $(ENGINE_DS_OBJS:.o=.d) $(ENGINE_CTR_OBJS:.o=.d)
