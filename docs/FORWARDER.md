# HOME Menu forwarder (CIA)

The forwarder is a small installed title that starts the SD-card program
`sdmc:/3ds/sinjoh-platinum.3dsx` from the HOME Menu. It contains no game code:
it asks Luma3DS's homebrew loader to run the `.3dsx` in its place, then chains
back into itself. Updating the `.3dsx` updates what the icon runs; the CIA is
installed once.

This is the same mechanism kohjoh's forwarder uses (`hb:ldr` SetTarget and
SetArgv, the Luma shared configuration at `OS_SHAREDCFG_VADDR + 0x800`, and
`aptSetChainloader`). The launched program restores the previous loader title
from the `sinjoh-forwarder:restore=` argv entry in
`engine/app/main.c`.

## Install

1. Copy the two programs and their data as usual:
   `sdmc:/3ds/sinjoh-platinum.3dsx`, `sdmc:/3ds/sinjoh/...`.
2. Copy `sinjoh-platinum.cia` anywhere on the card, e.g. `sdmc:/cias/`.
3. Install it once with FBI. It appears as **Sinjoh Platinum**.
4. Launch it from the HOME Menu.

If the `.3dsx` is missing, the forwarder shows an error on the top screen and
leaves the loader configuration alone. That matters: changing the selected
title before checking the target can leave Luma pointing at a program that
does not exist.

## Build

Needs devkitARM + libctru from devkitPro, plus `makerom` and `bannertool`
(not part of devkitPro). Put them on `PATH`, pass them, or set
`SINJOH_CIA_TOOLS` to their folder:

```sh
pwsh tools/forwarder/build.ps1
pwsh tools/forwarder/build.ps1 -Makerom C:\tools\makerom.exe -Bannertool C:\tools\bannertool.exe
```

Output: `build/forwarder/sinjoh-platinum.cia`.

The packaging inputs are in `tools/forwarder/`:

| File | Role |
| --- | --- |
| `main.c` | the forwarder; target path and restore prefix |
| `forwarder.rsf` | makerom spec: title, product code, title ID, permissions |
| `icon.png`, `banner.png` | HOME Menu artwork; redraw with `make_assets.py` |
| `silence.wav` | silent banner audio |
| `build.ps1` | compile, make banner/SMDH, run makerom |

Identity: title **Sinjoh Platinum**, product code `CTR-H-SNJH`, unique ID
`0xD7103`. The ID is distinct from kohjoh's `0xD7101`/`0xD7102`. Changing it
requires updating `UniqueId` in `forwarder.rsf`; the code does not read it.

## Limits

- The forwarded program keeps its SD-card save and data layout; it does not get
  a native title save archive or RomFS.
- The mechanism depends on Luma3DS (`hb:ldr` and the shared configuration
  layout). It does not work on a stock console.
- Performance and rendering are unchanged; this is a shortcut, not a native
  build.
- A failed chainload can leave Luma's selected loader title pointing at this
  title until another homebrew launch or a reboot.
