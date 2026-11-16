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
- The box test is widened for widescreen so side content is not culled. That
  widening is also the remaster's "wider view" for Platinum.

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
