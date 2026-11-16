/*
 * kj_boot.c: what the DS firmware and cartridge loader did before the
 * game's NitroMain, on the DS side of the bridge.
 *
 * Writes the cartridge header and firmware settings the SDK reads, hands the
 * compat layer the overlay table, registers the virtual ARM7 services and
 * runs the original NitroMain. Cartridge-header values and the fixed MAC
 * address follow pokeplatinum-3ds's game start (3ds_port/game/app/platinum.c,
 * GPL-3.0); the boot sequence is kohjoh's.
 */

#include "kj_bridge.h"

#include <nitro.h>
#include <nitro_port.h>
#include <nitro_port_fs.h>
#include <string.h>

extern const NitroPortOverlay gPlatinumOverlays[];   /* gen/overlay_table.c */
extern const u32 gPlatinumOverlayCount;

void NitroMain(void);

#define KJ_EDITION "platinum"
#define KJ_PAK_BUILD_ID "platinum-nitrofs-1"

/* The game stores the console's MAC address in the save and compares it on
 * load; one fixed address keeps every save "from this DS". 00:09:BF is one
 * of Nintendo's prefixes. */
static const u8 MAC_ADDRESS[6] = { 0x00, 0x09, 0xBF, 0x50, 0x33, 0xD5 };

const char *kj_ds_edition_name(void)
{
    return KJ_EDITION;
}

const char *kj_ds_pack_build_id(void)
{
    return KJ_PAK_BUILD_ID;
}

void kj_ds_set_save_path(const char *path)
{
    NitroPort_SetSavePath(path);
}

const char *kj_ds_open_pack(const char *pak_path, const char *manifest_path)
{
    switch (NitroPort_OpenPak(pak_path, manifest_path, KJ_PAK_BUILD_ID)) {
    case PAK_OK:
        return NULL;
    case PAK_ERR_IO:
        return "cannot read the data pack or its manifest";
    case PAK_ERR_FORMAT:
        return "the data pack or its manifest is damaged, or they do not belong together";
    case PAK_ERR_VERSION:
        return "the data pack was made by a different version of the pack builder";
    case PAK_ERR_BUILD_ID:
        return "the data pack is for the other edition (wrong build ID)";
    case PAK_ERR_ROM_SHA1:
        return "the data pack was made from a ROM this version does not support";
    case PAK_ERR_MEMORY:
        return "out of memory opening the data pack";
    default:
        return "cannot open the data pack";
    }
}

/* A failed GF_ASSERT in the game. The DS build ignores most of them; the
 * port logs where they come from (look the address up in the program's
 * .elf). The programs are linked with --wrap=ErrorHandling_AssertFail. */
void __real_ErrorHandling_AssertFail(void);

void __wrap_ErrorHandling_AssertFail(void)
{
    NitroPort_Log("[platinum] GF_ASSERT failed, called from %p", __builtin_return_address(0));
    __real_ErrorHandling_AssertFail();
}

void kj_game_main(const kj_game_settings *settings)
{
    CARDRomHeader header;
    NitroPortFirmware firmware;

    /* The cartridge header, as far as the game and the SDK read it: the
     * game checks the maker code at boot (boot.c). Files come from the data
     * pack, so the cartridge offsets mean nothing here. */
    memset(&header, 0, sizeof(header));
    memcpy(header.game_name, "POKEMON PL\0\0", 12);
    header.game_code = 'C' | ('P' << 8) | ('U' << 16) | ((u32)'E' << 24);
    header.maker_code = '0' | ('1' << 8);
    header.device_size = 10;   /* 128 MB */
    header.game_version = 1;

    memset(&firmware, 0, sizeof(firmware));
    firmware.romHeader = &header;
    firmware.romHeaderSize = sizeof(header);
    firmware.nickname = settings->nickname;
    firmware.language = settings->language;
    firmware.birthMonth = settings->birth_month;
    firmware.birthDay = settings->birth_day;
    firmware.favoriteColor = settings->favorite_color;
    memcpy(firmware.macAddress, MAC_ADDRESS, sizeof(MAC_ADDRESS));
    firmware.rtcOffset = 0;
    NitroPort_BootFirmware(&firmware);

    NitroPort_SetOverlays(gPlatinumOverlays, gPlatinumOverlayCount);

    /* The ARM7's services: the save chip, the clock, the touch screen and
     * power management (sound, microphone and wireless are handled by the
     * port's own virtual ARM7). */
    NitroPort_InitArm7Services();

    NitroPort_Log("[kj] starting %s", KJ_EDITION);
    NitroMain();
    NitroPort_Log("[kj] NitroMain returned");
    OS_Terminate();
    for (;;) {
    }
}
