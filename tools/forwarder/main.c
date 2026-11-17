/*
 * main.c: HOME Menu forwarder for sdmc:/3ds/sinjoh-platinum.3dsx.
 *
 * The installed title contains no game code. It points Luma3DS's homebrew
 * loader at the SD-card program, asks it to launch that in this title's place,
 * and chains back into itself. The launched program receives the loader's
 * previous title ID so it can restore the shared configuration
 * (engine/app/main.c, restore_forwarder_loader).
 */
#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#define TARGET "/3ds/sinjoh-platinum.3dsx"
#define RESTORE_PREFIX "sinjoh-forwarder:restore="

/* Luma3DS shared configuration: current, selected loader title, enabled. */
typedef struct {
    u64 current;
    u64 selected;
    bool enabled;
} LumaConfig;

#define LUMA_CFG ((volatile LumaConfig *)(OS_SHAREDCFG_VADDR + 0x800))

static char path[0x400] __attribute__((aligned(4)));
static u32 args[0x100];

static Result forward(void)
{
    struct stat st;
    s64 version;
    u64 self;
    Handle port;
    Result r;

    /* Never change the loader state for a program that is not there. */
    if (stat("sdmc:" TARGET, &st) != 0 || !S_ISREG(st.st_mode)) {
        return -1;
    }
    if (R_FAILED(svcGetSystemInfo(&version, 0x10000, 0)) || !LUMA_CFG->enabled ||
        R_FAILED(APT_GetProgramID(&self))) {
        return -1;
    }

    r = svcConnectToPort(&port, "hb:ldr");
    if (R_FAILED(r)) {
        return r;
    }

    /* hb:ldr SetTarget: the SD path to load. */
    strcpy(path, TARGET);
    u32 *cmd = getThreadCommandBuffer();
    cmd[0] = IPC_MakeHeader(2, 0, 2);
    cmd[1] = IPC_Desc_StaticBuffer(strlen(path) + 1, 0);
    cmd[2] = (u32)path;
    r = svcSendSyncRequest(port);
    if (R_SUCCEEDED(r)) {
        r = (Result)cmd[1];
    }

    /* hb:ldr SetArgv: argv[0] plus the title ID to restore on exit. */
    if (R_SUCCEEDED(r)) {
        args[0] = 2;
        char *p = (char *)&args[1];
        p += sprintf(p, "sdmc:" TARGET) + 1;
        sprintf(p, RESTORE_PREFIX "%016llX", (unsigned long long)LUMA_CFG->selected);
        cmd[0] = IPC_MakeHeader(3, 0, 2);
        cmd[1] = IPC_Desc_StaticBuffer(sizeof(args), 1);
        cmd[2] = (u32)args;
        r = svcSendSyncRequest(port);
        if (R_SUCCEEDED(r)) {
            r = (Result)cmd[1];
        }
    }
    svcCloseHandle(port);

    if (R_SUCCEEDED(r)) {
        LUMA_CFG->selected = self;
        aptSetChainloader(self, MEDIATYPE_SD);
    }
    return r;
}

int main(void)
{
    Result r = forward();
    if (R_SUCCEEDED(r)) {
        return 0;
    }

    gfxInitDefault();
    consoleInit(GFX_TOP, NULL);
    printf("Could not launch sdmc:" TARGET "\n"
           "Luma3DS and the SD-card program are required.\n"
           "Error: %08lX\nPress START.\n", (unsigned long)r);
    while (aptMainLoop()) {
        hidScanInput();
        if (hidKeysDown() & KEY_START) {
            break;
        }
        gspWaitForVBlank();
    }
    gfxExit();
    return 0;
}
