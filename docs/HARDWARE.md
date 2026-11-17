# Real-hardware test run

This is the procedure for the first Original 3DS / 2DS run. Azahar is an
integration debugger; none of its timing is evidence for the hardware target
(`docs/STATUS.md`, `docs/planning/O3DS_TIER.md` section 7). The run is here to
find the hardware-only failures: cache and clock cost, service-core
contention, SD stalls, VRAM hazards, HOME/sleep, and the save chip.

## What goes on the SD card

```
sdmc:/3ds/sinjoh-platinum.3dsx          release (no probes)
sdmc:/3ds/sinjoh-platinum-dbg.3dsx      instrumented (perf lines)
sdmc:/3ds/sinjoh/data/platinum.pak
sdmc:/3ds/sinjoh/data/platinum.manifest.json
sdmc:/3ds/sinjoh/saves/platinum.sav     (optional: your own dumped save)
sdmc:/3ds/sinjoh/menu.txt               (optional: "off" for the classic lower screen)
sdmc:/3ds/sinjoh/script.txt             (leave out: it drives inputs)
```

Both programs read the same `data/`, `saves/` and `logs/` directory, so they can
sit side by side and share the pack and save. Run the release build for normal
play. Run `-dbg` only to collect `[perf]`/`[gpu]`/`[pace]`/`[snd*]` lines; it
logs to the same `logs/platinum.log` (the `[app]` line names the build and
`-dbg`).

Build the `.3dsx` files with `pwsh tools/build.ps1 -All`, or one at a time with
`pwsh tools/build.ps1` (release) and `pwsh tools/build.ps1 -Profile 1` (debug).
The two profiles have separate build trees, so switching never reuses objects
compiled under the other's flags. Then stage the card with the one packaging
script; it checks your dump, writes the pack, verifies it, and copies both
built programs beside it:

```
python builder/prepare.py path/to/platinum.nds --sd E:\
```

or without `--sd` it writes a `sinjoh-sd/` SD-card root to copy. On Windows,
`builder/prepare.bat` does the same by drag and drop. Nothing from the ROM, a
save or a capture may be committed, and the `.pak` must not be shared.

Launch it from the HOME Menu's homebrew launcher, or install
`build/forwarder/sinjoh-platinum.cia` once with FBI to start the same
`sdmc:/3ds/sinjoh-platinum.3dsx` from a HOME Menu icon (`docs/FORWARDER.md`).
The app logs to
`sdmc:/3ds/sinjoh/logs/platinum.log`; crashes write `logs/crash.txt`. Pull both
off the card after the run.

Before the run, confirm the emulator build has no `script.txt` staged, no
`dumps/` directory, and that `menu.txt` says what you want. `PROFILE=1` builds
print a `[perf]`/`[gpu]`/`[pace]` line every 600 pictures; a release build does
not, and is the one to play.

## First boot

| Check | Pass looks like |
| --- | --- |
| Cold boot | Copyright, Game Freak, title. No black screen, no fatal screen. |
| Both screens | Top 400x240, lower 320x240, no white bars. |
| Title gradient | The copyright screen has its blue-grey gradient and red side bands (melonds reference). |
| Load the save | `[menu] field lower screen on` in the log, the hotel-room field, the lower menu. |
| X | The start menu appears in the lower panel; BAG/TRAINER/SAVE/OPTIONS lit, the rest dimmed. |
| Tap BAG | The bag opens; B returns to the field and the menu. |
| Walk outside | Twinleaf Town, 3D field, wide view at the sides, no missing geometry. |
| Sound | Music and effects, no dropouts (the `snd*` lines are absent in a release build). |
| HOME and sleep | HOME opens the menu; return resumes the field; sleep/wake does not desync audio. |
| Save | Save in-game, quit, cold boot, continue: the same field and party. |

Record frame pacing by eye and by the log if the build has instrumentation.
The exit criterion for this pass is 30 Hz in the field and in a battle, with no
freezes, no crashes, and no visual difference from the Azahar captures except
the documented exclusions (no shadows, no edges, no stereo, no 60 fps, no
xBRZ, no sun shadows, no colour grade).

## What to report

For each failure: the screen (top/lower), the map and the action, the last
`[script]`/`[menu]`/`[wide art]`/error lines, and whether HOME/sleep was
involved. Attach `platinum.log` and `crash.txt`. Do not report an Azahar
difference as a hardware bug until it reproduces here.

## Known limits to expect

- 3D wide view and the start menu are verified in Azahar only, not in an
  outdoor 3D scene and not through every app.
- The lower menu's panel apps (Town Map, bag/party layouts, panel fades) are
  not implemented; opening those apps leaves the menu, as the classic display
  does.
- Fog is not drawn (counted as unsupported in a `PROFILE=1` build). Weather
  scenes will look clearer than the DS until it is.
- The colour grade, sun shadows, edge marking, stereo and 60 fps are
  deliberately excluded for O3DS.
