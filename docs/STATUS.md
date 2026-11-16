# Status

Verified 2026-11-16. "Implemented", "built", "ran" and "verified" are separate
facts; this file keeps them apart.

## Implemented

- New repository layout: `engine/` (kohjoh's runtime and renderer),
  `tools/game/` (bootstrap, source inventory), `tools/lotus_mcp.py` (MCP
  client), `wideart/` (hand-drawn band sources).
- `tools/game/bootstrap.py`: fetches `pret/pokeplatinum` at `c248fb3` and the
  NitroSDK/NitroSystem decompilations at the revisions in its subproject wrap
  files; applies `patches/{pokeplatinum,NitroSDK,NitroSystem}` when present.
- `tools/game/platinum_sources.py`: reads the decomp's meson `files()` lists
  and `platinum.us/main.lsf`, and maps every linker object to a source.
- `tools/game/platinum_lsf.py`: rewrites the Meson-mangled linker spec into
  checkout paths, and `tools/game/game_overlays.py` (kohjoh's, adapted to
  ignore Platinum's per-overlay SDK archives) turns it into
  `overlay_ids.ld`, `overlay_ids.h` and `overlay_table.c`.
- Documentation: architecture, porting plan, LOTUS findings, this status.

## Built

- Nothing of sinjoh's own yet. The engine sources are imported, not compiled in
  this tree.

## Ran

- LOTUS v0.0.2 was driven over MCP in a windowed session (AZAHAR worker):
  session created, focused, loaded, 60 frames advanced, settings read and
  written, session stopped. The window displayed the focused session.
- The bootstrap and source inventory both ran successfully on this machine.

## Verified facts

- Bootstrap: 3 checkouts, 0 patches (the sinjoh stacks are not written yet).
- Source inventory: 1042 meson sources; 1014 linker objects across 125
  sections (Static main, 2 autoloads, 122 overlays); 1012 mapped; the two
  unmapped entries are `libos.a` (a library line, not an object) and
  `trainer_ai_script.o` (generated from `src/battle/trainer_ai/script.s`).
- Linker-spec normalization: 1012 objects rewritten to checkout paths, 2
  generated/unknown kept, 64 library lines. The overlay tool accepts it and
  emits 122 overlay IDs `dummy1`..`dw_warp` (0..121) plus the reset table
  skeleton. Object section renaming waits for real objects.
- LOTUS v0.0.2 pins every session to the `old3ds/software/...` profile and
  records `azahar_native_software`; its MCP `graphics_api` setting feeds the
  capture RPC, not the renderer, so it cannot select Vulkan. Evidence and
  commands are in `docs/LOTUS.md`.

## Not verified

- No sinjoh build, no emulator boot, no O3DS hardware run.
- The game-side compatibility stack and the engine/game link do not exist yet.
- No performance claim is possible.

## Next

1. M2: write `patches/pokeplatinum` from the compiler/ABI work queue and port
   the NitroSDK/NitroSystem compat to the `kj_*` bridge.
2. M2: name build objects `<source>.o` so the overlay tool can rename sections
   when the objects exist; change `overlay_table.c`'s include to sinjoh's
   overlay header.
3. M3: build the data pack and boot 2D in LOTUS.
