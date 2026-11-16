# Porting plan

The order is chosen so each milestone is provable before the next one depends
on it. "Built" and "runs" and "verified in an emulator" are separate claims.

## M0 - foundation (done)

- New tree, provenance, licence.
- Pinned `pret/pokeplatinum` at `c248fb3`, plus the NitroSDK and NitroSystem
  decompilations at the revisions in its `subprojects/*.wrap`.
- `tools/game/bootstrap.py` reproduces the checkout on Windows.
- Engine imported from kohjoh under `engine/`.
- LOTUS MCP harness and its renderer limits documented.

Acceptance: `python tools/game/bootstrap.py` prints the three checkouts and
`build/upstream/platinum.us/main.lsf` exists.

## M1 - source inventory and overlay map

- Enumerate the game's C/C++/asm sources from the decomp's meson files, not a
  glob, so conditional and excluded sources are visible.
- Read `platinum.us/main.lsf` for every object's link section and every
  overlay's ID, region and `After` chain.
- Emit the same tables kohjoh's build driver needs (`overlay.map`,
  `overlay_ids.ld`, `overlay_table.c`).

Acceptance: every object in `main.lsf` maps to a source or is marked
build-generated; the overlay table lists 122 overlays in link order; no
duplicate object assignment.

## M2 - game-side compatibility stack

- Adapt the compiler/ABI/correctness patches from pokeplatinum-3ds's patch
  stack against this decomp pin. These are independent of the renderer:
  Metrowerks-to-GCC type widths, static/const mismatches, MSL runtime, overlay
  static initializers, CRC and math helpers.
- Port kohjoh's NitroSDK/NitroSystem compatibility implementation to the APIs
  pokeplatinum actually calls. The bridge stays `kj_*`; no `NitroPort_*` layer
  is introduced.
- Implement the game entry (`kj_boot.c` analogue): cartridge/firmware state,
  file system IDs, overlay loader, save chip, RTC.

Acceptance: the game compiles with no errors and links; the host32 build
(`TARGET=host32`) runs its first frames headless and logs a boot.

## M3 - boot on 3DS with 2D only

- Build the data pack from the user's own Platinum dump.
- Render engine B (bottom) and engine A (top) through the atlas path.
- Boot the Game Freak logo, title, and the first field map in LOTUS.
- 3D scenes are counted as unsupported until M4; no CPU rasterizer is added.

Acceptance: windowed LOTUS shows the boot sequence and a field 2D frame; the
log names the pack and the renderer; unsupported 3D counts are non-zero and
reported, not hidden.

## M4 - retained 3D

- Feed the game's G3 FIFO through `engine/runtime/kj_g3.c`.
- Retained object-space batches, 16-entry matrix palette, baked literal
  colours, clip-volume cull, PICA lighting only for lists that cannot bake.
- Native 400x240 top screen and the widened camera/box test.

Acceptance: field and battle 3D draw; held frames match the reference in the
DS 256x192 region; unsupported material modes are counted.

## M5 - audio, save, input

- DS sound chip host and decoded-ADPCM cache on the audio thread.
- Two-generation save store; raw 512 KiB payload import/export.
- Input and touch, APT suspend/resume.

Acceptance: 30 minutes of music/effects without dropouts; 20 save/load cycles;
HOME/sleep/return.

## M6 - remaster features

- Lower-screen field menu implemented in sinjoh's game glue.
- Wide camera layout for the field, 2D wide canvas, health-box/window geometry.
- WideArt: package-time band generation, runtime upload only. The bands in
  `wideart/` are hand-drawn sources; the packer composites them into the
  map-keyed textures the engine consumes, so the console never does image work.
- Options for the O3DS profile: native 3D, wide view, menu.

Acceptance: the O3DS tier gates in `docs/planning/O3DS_TIER.md` (G0-G8) pass in
emulator except the hardware-only ones, which stay listed as unverified.

## The patch stack

`patches/` holds three stacks, applied by `tools/game/bootstrap.py`:

```
patches/pokeplatinum/   game fixes and sinjoh hooks
patches/NitroSDK/       the SDK decompilation's GCC/3DS compatibility
patches/NitroSystem/    likewise
```

Rules:

- One patch, one purpose, with a message that says what and why.
- Runtime-facing changes call `kj_*`, never a second port's API.
- Any code adapted from kohjoh or pokeplatinum-3ds keeps its GPL notice and a
  header line naming the source and commit.
- No game data, saves, captures or ROM bytes in a patch or artifact.

## What is deliberately not planned

- A CPU software rasterizer, a full-frame CPU compositor, or a GPU readback
  path. A missing effect is a counted blocker.
- 60 FPS interpolation, stereo, smooth3d 2x2, sun shadows, edge marking, xBRZ.
- New 3DS-only threads, clock or memory assumptions in the baseline.
