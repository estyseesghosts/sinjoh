# Sinjoh asset tools

These scripts turn **your own** Pokemon Platinum `.nds` dump into the data pack
the program reads from the SD card. They need Python 3.10+ and nothing else.
The ROM is only read, never modified, and nothing is uploaded.

## Windows

Drag your `.nds` onto `prepare.bat`. To write straight to the card instead,
run `prepare.bat --sd E:\` from a command prompt (replace `E:\` with your card).

## Linux and macOS

```sh
python3 prepare.py your-game.nds            # finds a .nds in the folder if omitted
python3 prepare.py your-game.nds --sd /media/you/SDCARD
```

## What it writes

- `3ds/sinjoh/data/platinum.pak` and `platinum.manifest.json` — your game's
  data, checked against the program's expected build id.
- `3ds/sinjoh-platinum.3dsx` and `3ds/sinjoh-platinum-dbg.3dsx` when they are
  beside the scripts, so a release zip is self-contained. A release download
  already has the programs; copy them to `sdmc:/3ds/` yourself in that case.

Copy the produced `3ds/` folder to the root of the SD card, then launch
**Sinjoh Platinum** from the Homebrew Launcher (or from the HOME Menu if you
installed the optional forwarder CIA).

## Files

| file | role |
| --- | --- |
| `prepare.py` | the entry point: verify, extract, pack, stage |
| `extract_rom.py` | reads the NARC files out of the `.nds` |
| `pack.py` | writes the indexed pack and manifest |
| `verify_rom.py` | the accepted dumps (SHA-1) |
| `prepare.bat` | the Windows drag-and-drop wrapper |

Never share the `.pak` files: they contain your game's data. Saves live on the
SD card, not in the pack.
