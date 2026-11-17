# Architecture

Sinjoh compiles the original game for the 3DS's ARM11 and gives it a presentable
frame, the way kohjoh does for HeartGold. The renderer never rasterizes a single
pixel on the CPU in the shipping path.

## Two halves, one bridge

| Half | Compiled with | Contents |
| --- | --- | --- |
| DS side | NitroSDK types, 4-byte enums | `build/upstream` (game), `engine/runtime`, `engine/compat/nitro`, `engine/compat/nitrosystem` |
| 3DS side | libctru/citro3d, short enums | `engine/app`, `engine/graphics`, `engine/audio`, `engine/content`, `engine/storage`, `engine/diagnostics` |

They meet only at `engine/runtime/kj_bridge.h`: fixed-width types, plain
structs, `kj_ds_*` implemented on the DS side and `kj_ctr_*` on the 3DS side.
No enums cross the line, and no NitroSDK or libctru header is included there.
The boundary is kohjoh's and is kept unchanged; sinjoh's work goes into what is
on each side of it.

## Frame flow

1. The game's own main loop runs on the main thread (`kj_game_main`).
2. Every emulated DS V-blank (`OS_Halt`) calls `kj_ctr_vblank`: APT, input,
   audio service, then a wait locked to the physical V-blank count. A late
   frame does not wait, so the game never loses DS time against real-time
   audio; a stall over 30 V-blanks resynchronises.
3. After the V-blank callback and vwait tasks, `engine/runtime/kj_frame.c` walks
   any H-blank effect and publishes one coherent snapshot: registers, palettes,
   OAM, VRAM banks, per-line registers and the last swapped 3D scene.
4. `engine/graphics/renderer.c` waits for the previous GPU frame, records both
   screens and submits. Nothing reads DS memory after it returns. If the game
   is two or more refreshes behind, the presentation is skipped and counted;
   the game tick is not.

There is one frame loop: the game's. O3DS is the design floor: the program
never enables the New 3DS clock or L2, and it runs in the ordinary 64 MB
application memory mode.

Presentation is 30 Hz on O3DS by contract: the DS game ticks at 60 Hz, the
renderer presents every second coherent frame, and a late frame is dropped
rather than delaying the game. 60 Hz frame interpolation, if added, is an
opt-in New 3DS enhancement with its own thread budget; it is not part of the
O3DS baseline and must never consume O3DS memory or CPU.

## 2D

DS tiles are palette-expanded into a 1024x1024 RGBA5551 atlas, one DS 8x8 tile
per PICA tile. A slot is reused only when its tile bytes are byte-identical and
its palette version unchanged: no write tracking, no hashing of VRAM. Layers
draw in DS priority order, with the 3D scene at BG0's slot. Stencil bits carry
blend-target membership and window regions; BLDY and master brightness are
full-screen passes. Text-BG and OBJ layers are retained when their inputs
(registers, palette, map/OAM, ext palettes, the character bytes read) are
byte-identical; an unchanged screen is not redrawn or transferred.

For sinjoh this is also the 2D remaster path: the top screen's 2D is drawn on a
320-pixel-wide logical canvas at 1.25x, not upscaled from 256x192. The class
"crisp 2D" in the O3DS tier is this atlas, not a software surface.

## 3D

- The DS side interprets matrix stacks (20.12 fixed), texgen, and readable
  box/position/vector tests on the CPU. NORMAL latches its transformed normal
  and immutable lighting inputs; the PICA evaluates DS diffuse/specular,
  shininess, ambient and emission with exact fixed-point rounding.
- Vertices stay in object space. Each batch carries a palette of up to 16 clip
  matrices; the 3DS side multiplies each by one fixup matrix (viewport,
  widescreen x-scale, screen rotation, depth range) and the vertex shader
  transforms on the GPU. Lit draws use six clip matrices to leave uniform
  space for four lights and the shininess table; the vertex ABI stays 16 bytes.
- The prior publish selects capture before the next scene starts, so field and
  title producers can skip discarded geometry traversal and FIFO submission
  while preserving game updates, animation and resource retirement.
- Retained object-space meshes, the literal-colour baked block cache, and the
  clip-volume side-plane cull are kohjoh's O3DS wins and are kept.
- Per-batch state is filtered: culling, depth and blend are sent only when their
  value changes, and the 32-word shininess table only when the table itself
  changes. In the field 82% of those setter calls were redundant (38,511 of
  46,680 per 600 frames), and skipping them cost nothing anywhere else. The
  caches are sentinelled and reset at the frame's program bind, so the first
  batch of a frame is always unconditional.
- The box test is widened for widescreen so side content is not culled. That
  widening is also the remaster's "wider view" for Platinum.
- A batch is a *material*, not a strip of one material: consecutive field
  batches share no state, so joining them into fewer draws needs a union
  palette and a remapped index buffer, not an adjacency test. That is an idea,
  not a feature; the measurement that says so is in `docs/STATUS.md`.

Not implemented yet, and counted rather than silently dropped: fog, toon
highlight, edge marking, shadow volumes, wireframe, display capture, bitmap
BGs. The O3DS tier excludes sun shadows, edge marking, stereo, interpolation
and xBRZ by design.

## Audio, content, storage

- The vendored ARM7 sequencer and DS sound chip mix 32768 Hz stereo on an
  audio thread (core 0, above the game), fed by NDSP. The decoded-ADPCM cache
  is kohjoh's `adpcmClean` cache: voices whose decoder state comes from data
  alone are decoded once.
- The data pack is an indexed, versioned file keyed by original game file IDs.
  The renderer, game and pack never know whether the pack is on SD or in RomFS.
- Saves are two-generation raw payloads with a checked header, on SD for the
  `.3dsx` and in the title archive for a `.cia`.

## Remaster feature map

| Feature | Where it lives | O3DS cost |
| --- | --- | --- |
| Both screens filled | renderer viewports (2D 1.25x, 3D native 400x240) | flat |
| Native-resolution 3D | g3d fixup + 400-wide targets | flat (GPU bound) |
| Wider field view | g3d fixup x-scale + widened box test | few CPU tests |
| Lower-screen menu | sinjoh game glue (`menu/`), not the renderer | 2D only |
| Crisp 2D | g2d atlas | replaces software drawer |
| WideArt | package-time bands loaded as textures | upload once |
| Stable 30 Hz | pacing in `app/main.c`, present skip | measurement |
| Pixel-perfect overworld | layout mode in the game glue | optional |

Excluded on O3DS: 60 FPS interpolation, stereo, smooth3d 2x2, sun shadows,
edge marking, xBRZ, full WideArt packs. The layout uses the reduced wide
canvas; WideArt bands are precomputed, not synthesized per frame.

## What is deliberately different from pokeplatinum-3ds

- No CPU transform/light/clip of 3D scenes, no software 2D rasterizer, no
  GPU-to-CPU readback, no per-frame compositor upload.
- No N3DS thread topology. The game owns the main thread; audio is the only
  worker. Core 1 is treated as a shared system core, not a second full core.
- No interpolation path to satisfy: the O3DS tier is 30 Hz by contract.
- The patch stack is re-derived against the `kj_*` bridge instead of carrying
  a second renderer's `NitroPort_*` API.

## Measuring

Two profiles, never mixed: `tools/build.ps1` builds the release binary with the
instrumentation compiled out (`HGSS_PROFILE_OFF`) and `-Profile 1` the
measurement binary with every counter on. Only the debug build prints
`[perf]`, `[gpu]`, `[ds]`, `[mon]` and `[probe]`.

The steady state is the field: `tools/lotus/field_run.py` drives title, START,
A (Continue), START, then records whole 600-picture windows. Windows are compared
at fixed picture numbers (4201-4800), so two builds see the same content.

What counts as evidence, in order:

1. **Work removed** - draws, decodes, uploads, skipped calls, bytes read. These
   transfer to a stock O3DS. A counter that shows an optimization *declining*
   is as valuable as one that shows it firing (`merge joined 0` ended a day of
   guessing).
2. **Host microseconds** from `[perf]` - indicative only. LOTUS is an emulator;
   a microsecond delta is not an O3DS delta.
3. **Pixels** - captures of both screens at fixed pictures, compared with
   `ImageChops.difference`. `bbox None` is the correctness claim; anything else
   means the change altered output and must be explained.

Attribution uses `NitroPort_ProbeNow`/`NitroPort_NoteProbeSince`
(`KJ_PROBE_SLOTS` slots, printed per game frame by the `[probe]` line). Slots
are laid out as siblings - the whole call in slot 0, its parts in 1..n - so the
remainder is the part still not measured. Two rules learned the hard way: use
`svcGetSystemTick`, never `OS_GetTick` (which syncs the DS timers, ~8 us per
frame), and remove the temporary slots from the game sources once the reading
is taken; the facility stays, the probes do not.

Three traps that produced wrong numbers here, all now in `docs/LESSONS.md`:
two builds at once (a linked binary that exists in no tree), a weak symbol
absent from the ELF (a counter that reads zero because nothing defines it), and
comparing runs from different sources.
