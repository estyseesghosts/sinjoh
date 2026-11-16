# PR series

> Planning document. No code has been written. Each brief describes a change
> that can become one branch and one pull request into `main`.

## How to read a brief

Every core brief has the same shape:

- **Merge case (N3DS)** - why this is worth taking on the hardware upstream
  supports. If this line is weak, the PR is optional.
- **Cost removed** - the specific measured or inferred cost.
- **Scope** - what is in, and what is deliberately out.
- **Integration points** - the files and functions the change touches.
- **Design** - the approach, in prose.
- **Flags and defaults** - how the old path stays available.
- **Correctness tests** - what proves it did not change the picture.
- **Performance gate** - what proves it was worth doing.
- **Risks and rollback** - how it fails safely.
- **Size and dependencies** - planning estimate.

Common rules for every PR:

1. Every PR before `perf/o3ds-tier` needs an N3DS merge case. The tier is the
   one exception: it is the optional assembly step.
2. One branch, one cost, one reviewable idea. No drive-by refactors.
3. New behavior is off by default until it passes its gate.
4. The old path remains selectable, at least for one release cycle.
5. No game content, no captured assets, no save files, no built ROMs.
6. AI assistance is disclosed in the commit and the PR description.
7. `make test` and `make game` are green before review.
8. The PR includes its own before/after evidence; the maintainer is not asked
   to benchmark hardware.
9. Never include the 426 line-ending-only files in the diff.

## Order and dependencies

```
perf/telemetry
  ├─ perf/render2d-change
  │    └─ perf/g2d-atlas-text
  │         └─ perf/g2d-layers
  │              └─ perf/g2d-effects
  ├─ perf/audio-adpcm
  └─ perf/g3d-census
       └─ perf/g3d-retained
            └─ perf/g3d-lighting

the core backends (2-6, 8-9)
  └─ perf/lowend-schedule
       └─ perf/o3ds-tier

optional, after the core track:
  perf/g3d-fifo
  perf/game-hotpaths
```

The order is chosen so each step makes the next one measurable:

- telemetry before any timing claim;
- the change check before GPU 2D, because it is the clearest N3DS win and the
  lowest-risk proof that the approach works;
- the census before retained geometry, because it decides whether the
  technique fits `pokeplatinum`'s G3 stream;
- scheduling after the costs are removed, because the old pacing rules are
  tuned for the old costs;
- the O3DS tier last, because it is an assembly of things that must already
  work on N3DS terms.

A PR may be opened as a draft while its dependency is unmerged. It is not
rebased into a long private stack; each PR is based on `main` plus its
dependency branch, and the dependency is called out in the description.

---

## 1. `perf/telemetry` - make the costs visible

**Merge case (N3DS):** every later claim about frame time becomes checkable
from a log, instead of an argument.

**Cost removed:** blind spots. Today the project has excellent `[perf]` lines
for the drawer, the geometry, and the mixer, but they are averages and
per-event counters. They do not say p95/p99, and they do not split the change
check from the draw from the handover consistently across scenes.

**Scope**

- In: a small histogram module with fixed buckets, scene markers, and stable
  log lines.
- In: per-stage counters for 2D (change check, draw, handover), 3D (decode,
  transform, light, clip, submit), audio (decode, mix), and presentation
  (shown, kept, skipped, late).
- In: a one-line summary per scene: p50/p95/p99 frame time, drawer time,
  geometry time, missed V-blanks, scenes left out.
- Out: any change to rendering, scheduling, or defaults.
- Out: a telemetry upload or any network access.

**Integration points**

- `3ds_port/game/app/main_3ds.c`: the `[perf] game`, `[perf] geometry`, and
  frame-loop logging.
- `3ds_port/nitro/src/port_render2d.c`: `NitroPort_Render2DTimes` and the
  change-check/draw/handover boundaries.
- `3ds_port/nitro/src/port_gx3d.c`: the decode/transform/light/clip stages.
- `3ds_port/nitro/src/port_sound_chip.c`: the mixer's stage counters.
- `3ds_port/nitro/src/port_speed.c`: frame pacing and present decisions.
- New: `3ds_port/nitro/src/port_perf.c` and a header, if a shared module is
  cleaner than growing `main_3ds.c`.

**Design**

- Fixed-bucket histograms (for example 0.25 ms resolution up to 100 ms) with
  no allocation in the frame path.
- Counters are relaxed atomic increments or per-thread accumulators merged at
  scene end. No locks in hot paths.
- Scene boundaries come from the existing place-name/scene markers, so a log
  can be sliced without a new game hook.
- The summary is emitted once per scene or once per second, buffered, and
  written off the critical path.
- Enabled by a config key (for example `perf 1`) or a compile-time switch.
  Disabled means no measurable cost, not "cheap enough".

**Flags and defaults**

- Default off in release builds.
- When on, the same scene and input script produce comparable logs across
  builds.
- No behavior change when off.

**Correctness tests**

- A host unit test for the histogram math (bucket edges, percentiles,
  overflow).
- A test that enabling telemetry does not change rendered output or timing
  decisions in the deterministic host suite.
- A log-parser test with a fixed sample log.

**Performance gate**

- Overhead under 0.2 ms per frame when enabled `[TARGET]`.
- Zero measurable difference when disabled.
- The summary is stable across three runs of the same scene.

**Risks and rollback**

- Risk: log I/O perturbs the measurement. Mitigation: buffered writes, one
  line per scene, no per-frame file flush.
- Risk: counters become a maintenance burden. Mitigation: a small fixed set,
  documented in one header.
- Rollback: delete the module and the call sites; no rendering code depends
  on it.

**Size and dependencies:** S. None.

---

## 2. `perf/render2d-change` - stop hashing 864 KB to learn nothing changed

**Merge case (N3DS):** the project's own documentation puts the unchanged-frame
VRAM read at about 15 ms of a 33 ms frame, half of engine A's drawer's time.
Removing it is the largest single New 3DS win in the plan, and it is invisible
to the player when it is correct.

**Cost removed:** `EngineShownVramSignature` reads and hashes up to 864 KB of
shown VRAM for engine A every frame, even when nothing changed. Related costs:
the OAM entry-by-entry hash, the palette invalidation sweep, and the forced
full read for H-blank effects and bitmap BGs.

**Scope**

- In: a generation-based change check for the common case: text/affine BGs,
  OBJ tiles, palettes, maps, and the VRAM display bank.
- In: write hooks on every CPU-visible VRAM path the port controls, including
  the SDK's GX load routines (reached through the port's NitroSDK patches),
  DMA, and direct CPU stores.
- In: a conservative fallback to the existing hash when a frame uses a path
  that cannot be tracked, or when the game changes bank mapping or display
  mode in a way the generation vector cannot describe.
- In: a debug verify mode that runs both checks periodically and logs any
  disagreement.
- Out: changing what is drawn, the compositor, or the GPU 2D path.
- Out: replacing the existing signature functions; they remain the reference
  and the fallback.

**Integration points**

- `3ds_port/nitro/src/port_render2d.c`: `ShownVramSignature`,
  `EngineShownVramSignature`, `EngineSmallSignature`, the per-frame change
  decision, and `NitroPort_Render2DTimes`.
- `3ds_port/nitro/src/port_dma.c`: the port's software DMA, which carries
  `GX_Load*` and `MI_DmaCopy*` writes into the VRAM blocks.
- `3ds_port/nitro/src/port_memory.c`: the VRAM blocks (`NitroPort_BgVram`,
  `NitroPort_ObjVram`, `NitroPort_Pltt`, `NitroPort_Oam`) and direct CPU
  stores into them.
- `patches/NitroSDK/`: the patched GX load and DMA routines, where a written
  range becomes a dirty region. The port's `src/port_gx.c` is FIFO status
  only and is not the place for this.
- `3ds_port/nitro/src/port_gx3d_texture.c`: 3D texture and palette uploads into
  VRAM, which the 2D check must treat as dependencies when the 3D is shown.

**Design**

- Split the shown VRAM into regions with stable identities: BG maps (per BG),
  BG tile data (per BG or bank), BG palettes, OBJ tile data, OBJ palettes,
  extended palettes, VRAM display bank, and the register/OAM snapshot.
- Every write path increments the generation of the region it touched. A GX
  load command increments once per command, not once per byte. A DMA
  increments every region its range covers. A direct store increments the
  containing region.
- The change check compares the current generation vector against the vector
  stored with the last picture. If any shown region's generation differs, the
  picture is redrawn. This is O(regions), not O(bytes).
- Register and OAM changes are already small; keep the existing small-signature
  logic for them, or fold them into the vector.
- The "shown" set is still computed by the existing code. The optimization is
  in how the bytes are validated, not in which bytes matter.
- Fallbacks:
  - H-blank effect or bitmap BG: use the existing hash, as today.
  - Bank remap or mode change that aliases regions: invalidate broadly.
  - A write path with no hook: set an "unknown write" flag, redraw this frame,
    and hash to confirm the next one.
- Debug verify mode: once per second, or on a config key, compute both the
  generation result and the full hash. A mismatch logs the region and the
  frame, and forces a redraw. This is how the hook coverage is proven on
  hardware without asking the maintainer to test it.

**Flags and defaults**

- Default on only after the fuzz and hardware verification pass; until then,
  a config key selects it.
- `NITRO_PORT_2D_SCAN=hash` (or the config equivalent) restores the old path.
- The fallback is per-frame and automatic; a scene that uses an untracked
  effect does not lose correctness.

**Correctness tests**

- Differential fuzz: random writes through every hooked path, random bank and
  mode changes, random OAM and palette updates. After each step, compare the
  generation result against the full hash. Any disagreement fails the test.
- A test that writes the same value to a region and confirms the generation
  still changes (conservative, not a correctness bug).
- A test that a read-only frame reports unchanged.
- `test_render` plus a new `test_render_change` suite, run under `host` and
  `host32`.
- Golden-frame comparison on the scene corpus: the fast path and the hash path
  must produce identical client pixels.

**Performance gate**

- Unchanged-frame change-check time drops from about 15 ms to under 1 ms on
  New 3DS `[TARGET]`.
- Engine A's drawer p95 improves in towns and menus, where the check is the
  dominant cost.
- No increase in missed redraws: the verify mode reports zero mismatches over
  a 30-minute run.
- No regression in changed-frame time.

**Risks and rollback**

- Risk: a missed write path produces a stale screen. This is the central risk.
  Mitigation: conservative invalidation, the unknown-write flag, the verify
  mode, and the hash fallback. A missed write is a correctness failure, not a
  tolerance.
- Risk: generation checks become more expensive than the hash for very small
  scenes. Mitigation: the region count is fixed and small; measure both.
- Rollback: flip the default to the hash path; the code remains.

**Size and dependencies:** M. Depends on 1 for measurement.

---

## 3. `perf/audio-adpcm` - stop re-decoding looping instruments

**Merge case (N3DS):** the mixer's decode work is real CPU time on the same
core as the game. `kohjoh` halved its mixer instruction count with a
decoded-ADPCM cache; the same shape of work exists here, and the output can be
bit-exact.

**Cost removed:** per-sample ADPCM decode of voices whose decoder state is
clean, especially looping instruments. `port_sound_chip.c` already tracks
`adpcmClean` and `adpcmSource`, and already walks from the start to the loop
point when a loop begins (`adpcm_to_loop`), but it does not cache the decoded
samples.

**Scope**

- In: a decoded-run cache for clean ADPCM voices, keyed by source, run start,
  and starting decoder state.
- In: invalidation on source change, key-on with a new sample, wave-buffer
  writes, and any state that is not clean.
- In: a cache-off switch for A/B testing.
- Out: a mixer rewrite. The block mixer stays.
- Out: changing the resampling, the sequencer, or the output rate.

**Integration points**

- `3ds_port/nitro/src/port_sound_chip.c`: `adpcm_init`, `adpcm_step`,
  `adpcm_at`, `adpcm_to_loop`, the voice key-on path, and the mixer's
  per-sample loop.
- `3ds_port/nitro/include/nitro_port_sound_chip.h`: the voice state, if the
  cache lives per voice.
- `3ds_port/nitro/tests/test_sound_chip.c` and
  `tests/sound_chip_reference.c`: the differential reference.

**Design**

- DS ADPCM is a continuous nibble stream after a 4-byte header; a decoded
  run's output depends on the decoder state at its start.
- Cache only when the state at the run start is derivable from the data alone
  (`adpcmClean`), which is exactly the case `kohjoh` measured. Store the
  decoded samples plus the starting state; on a hit, verify the state matches
  before using them.
- A small direct-mapped cache per voice or a shared cache with a tag is enough;
  the working set is a few runs per looping instrument. Keep it in the voice's
  existing memory if possible, so no allocation is needed.
- On a loop, the decoded runs from the first pass are reused instead of
  re-decoding from the loop point. `adpcm_to_loop` becomes a cache fill, not a
  full walk, after the first loop.
- If the state is dirty, the source changed, or the cache collides, decode
  exactly as today. There is no approximation.
- The cache must not change the mixer's timing or the sequencer's view of the
  voice.

**Flags and defaults**

- Default on after bit-exact differential tests pass.
- A config key or compile-time switch disables it for A/B.
- No change to the audio output when the cache is off.

**Correctness tests**

- `test_sound_chip` with the cache on and off, over every existing sequence:
  bit-exact output.
- Long looping instruments: multiple loops, pitch changes, key-on/key-off,
  and source changes; bit-exact against the reference.
- Wave-buffer writes while a voice is playing: the cache is invalidated and
  the output matches.
- A cache hit/miss counter test that the cache is actually used in the
  looping case.
- A soak test with music and effects for 30 minutes: no dropouts, no drift.

**Performance gate**

- Mixer decode ticks drop by at least 20% in a scene with looping music
  `[TARGET]`; `kohjoh` saw about 55% on its workload.
- Mixer core share drops measurably in the `[perf]` summary.
- No increase in audio latency or dropouts.

**Risks and rollback**

- Risk: a cache hit with the wrong starting state produces a click or a
  persistent wrong sample. Mitigation: verify the state on every hit; fall back
  to decode on any doubt.
- Risk: the cache costs more memory than it saves. Mitigation: per-voice,
  bounded, no allocation in the mixer.
- Rollback: disable the cache; the decoder is unchanged.

**Size and dependencies:** M. Depends on 1 for measurement. Independent of the
renderer track.

---

## 4. `perf/g2d-atlas-text` - draw text BGs from a tile atlas

**Merge case (N3DS):** the software 2D drawer costs about 16.2 ms a picture,
4.6 ms of it handover. Towns and menus redraw more often than they need to
because the change check cannot prove they are static. A GPU text-BG path
removes the per-tile CPU rasterization for the most common BG type, and in
scenes whose picture is text BGs alone it removes the full-picture handover
too.

**Cost removed:** software rasterization of text BGs; and, for scenes whose
picture is text BGs alone, the CPU-to-GPU copy of the resulting picture.

**Scope**

- In: text BGs in modes 0 and 1 (the text layers those modes use), 4bpp and
  8bpp, drawn from a tile atlas with exact palette decode.
- In: tile cache identity by VRAM generation, tile number, palette, bpp, and
  mapping; palette dependencies; dirty-tile upload.
- In: scroll, wrap, priority, and the existing compositor ordering.
- Out: affine BGs, extended BGs, sprites, windows, blending, brightness, and
  H-blank spans. Those are PRs 5 and 6, or stay on the software path.
- Out: bitmap BGs (fallback).
- Out: changing the software renderer's output for unsupported cases.

**Integration points**

- `3ds_port/nitro/src/port_render2d.c`: the existing `gpuBgs` decision
  (`GpuBgOf`, `GpuBgEmptyWindowOf`), the split structure, and the fallback
  conditions.
- `3ds_port/game/app/port_compose_pica.c`: the compositor's BG textures,
  `make_texture`, `alloc_sets`, and the draw path.
- `3ds_port/nitro/src/port_memory.c` and `port_render2d.c`: the VRAM blocks
  the atlas reads tiles and palettes from, and the bank mapping that decides
  which block a BG sees.
- New: an atlas module (for example `3ds_port/nitro/src/port_g2d_atlas.c`)
  shared by both engines, or a section of the compositor if that is cleaner.
- Existing tests: `test_render` and `render2d_reference.c`.

**Design**

- Build atlas pages from 8x8 DS tiles, decoded to RGBA5551. PICA stores
  textures as 8x8 tiles in Morton order, so one DS tile maps to one atlas tile
  with a fixed 8x8 permutation, not a whole-texture swizzle.
- Atlas entry identity: VRAM region generation, tile number, palette
  generation, palette bank, bpp, and flip if it affects packing. Derived
  color tiles are immutable once published.
- Palette changes invalidate the dependent tiles, not the whole atlas. Keep a
  reverse dependency from palette to atlas slots.
- Draw each visible map cell as a quad with the atlas UV. The quad generator
  wraps the map coordinates before looking up the cell; the atlas UV never
  wraps, so a map edge does not sample the opposite edge of the tile.
- Leave a 1-texel gutter between atlas entries (or bind the atlas with
  nearest filtering) so a bilinear tap cannot pull in a neighboring tile.
- Start with a 512x512 atlas (512 KB RGBA5551) to fit the New 3DS linear-memory
  floor; grow to 1024x1024 only if the memory log and the atlas stats show
  room. `kohjoh` uses 1024x1024, but `pokeplatinum-3ds` reports about 4.0 MB of
  linear memory left after the title screen and 2.5 MB at its lowest. `[PP]`
  Atlas size is a measured decision, not a copied constant.
- If the atlas is full, evict the least recently used page or fall back to the
  software path for that BG. A fallback is logged once per scene, not per
  frame.
- The existing `gpuBgs` path already draws some BGs; this PR extends it rather
  than creating a parallel renderer.

**Flags and defaults**

- `gpuText` (or the existing `gpuBgs` level) selects the path.
- Default off until golden frames pass; then default on for text BGs only.
- Per-BG fallback: a BG that uses an unsupported mode stays in the software
  picture, and the compositor draws it in the right order.

**Correctness tests**

- Golden-frame comparison for text-BG-only scenes: title, menus, towns,
  summary, PC. Zero differing client pixels on held frames.
- Palette change: one palette entry changes; only dependent tiles update; the
  frame matches the reference.
- Tile change: one tile changes; the frame matches.
- Scroll and wrap: a full 256-pixel scroll and a map-edge wrap; no seams.
- Atlas eviction: force a full atlas and verify the fallback still matches.
- `test_render` under `host` and `host32`.

**Performance gate**

- Text-BG drawer time in towns and menus drops measurably against the
  software path, including handover where the picture is text BGs alone.
- No regression in changed-frame time.
- Atlas upload bytes per frame are bounded and logged.
- No fallback storm: the log shows the fallback reason and the scene.

**Risks and rollback**

- Risk: palette aliasing produces wrong colors. Mitigation: exact identity
  includes the palette generation and bank; a palette write invalidates
  dependents.
- Risk: the atlas does not fit the linear heap. Mitigation: start small,
  evict, fall back, and measure.
- Risk: the compositor's ordering changes. Mitigation: draw through the
  existing split/order, not a new pass.
- Rollback: set `gpuText` off; the software path is unchanged.

**Size and dependencies:** L. Depends on 2 (the change check must be cheap
enough that the drawer is worth optimizing) and 1.

---

## 5. `perf/g2d-layers` - affine BGs, extended BGs, and all sprites

**Merge case (N3DS):** battles, the Distortion World, contests, and the
summary screen still spend software raster time on affine/extended BGs and
sprites. Moving them to the atlas path removes that time and makes the 2D
drawer's cost predictable.

**Cost removed:** software affine/extended BG rasterization, OAM sprite
rasterization, and the handover of pictures whose layers are all GPU-drawable
after this PR.

**Scope**

- In: affine BGs without per-line parameter changes, drawn as transformed
  quads with the atlas.
- In: extended BGs (256-color/8bpp modes) with exact palette decode.
- In: sprites: priority, affine, mosaic, flip, double-size, disabled, and
  per-OBJ palette.
- In: the existing `gpuObjs` path extended, not replaced.
- Out: per-line affine changes (fallback to software or PR 6 spans).
- Out: bitmap BGs and OBJ windows (fallback).
- Out: windows, blending, brightness (PR 6).

**Integration points**

- `3ds_port/nitro/src/port_render2d.c`: `GpuObjsOf`, `MakeGpuObjs`,
  `GpuObjsLeaveOut`, `NitroPort_Render2DObjPlaces`, the affine BG path, and
  the split structure.
- `3ds_port/game/app/port_compose_pica.c`: the OBJ texture sets and the
  compositor's sprite draw.
- The atlas module from PR 4.
- `test_render` and the reference renderer.

**Design**

- Affine BG: if the affine parameters are constant for the frame, draw one
  transformed quad (or a small grid for wrapping) with the atlas texture.
  If the game changes parameters per line, fall back for that BG.
- Extended BG: same tile atlas, but the tile decode uses the 8bpp palette and
  the extended palette banks. The identity includes the extended palette
  generation.
- Sprites: decode OAM into the existing `NitroGpuObj`/key form, batch by
  texture page and priority, and draw in the compositor's order. The existing
  sprite path already handles weather and some priority cases; this PR fills
  the remaining modes.
- Mosaic: implement in the shader or as a per-sprite UV quantization; if it
  cannot be exact, fall back for that sprite and log it.
- Double-size and affine sprites need the same transform math as the software
  path; test against the reference.
- Priority and blend order are the compositor's existing responsibility; do
  not invent a new sort.

**Flags and defaults**

- Extend the existing `gpuBgs`/`gpuObjs` levels rather than adding a second
  switch.
- Default off until the battle and Distortion World golden frames pass.
- Per-BG and per-OBJ fallback remains.

**Correctness tests**

- Battle intro, singles and doubles, contest, summary, PC, Distortion World,
  and a rotating affine BG: golden frames, zero differing client pixels.
- Sprite priority: overlapping sprites with different priorities and palettes.
- Sprite transforms: flip, affine, double-size, mosaic.
- Extended palette change: only dependent tiles update.
- `test_render` under both host targets.

**Performance gate**

- Drawer time in battles and the Distortion World drops against the software
  path.
- No regression in scenes that fall back.
- No new atlas eviction spikes beyond the PR 4 baseline.

**Risks and rollback**

- Risk: affine transform rounding differs from the DS. Mitigation: match the
  reference's fixed-point math, and compare pixels, not just geometry.
- Risk: sprite ordering regresses. Mitigation: reuse the existing compositor
  order and add an overlap test.
- Rollback: lower the `gpuBgs`/`gpuObjs` level; the software path remains.

**Size and dependencies:** XL. Depends on 4.

---

## 6. `perf/g2d-effects` - windows, blending, brightness, and H-blank spans

**Merge case (N3DS):** this is the difference between "GPU 2D for simple
scenes" and "GPU 2D for the scenes that actually drop frames": weather,
flash/fade transitions, menus with windows, and H-blank effects. It also
removes the software fallback that currently forces a full redraw.

**Cost removed:** software window evaluation, alpha blending, brightness
passes, and per-span rasterization for the remaining 2D effects.

**Scope**

- In: WIN0/WIN1 regions via stencil, as `kohjoh` does.
- In: alpha blending (BLDCNT mode 1 and semi-transparent OBJ) as two passes,
  with the second-target bit updated per layer.
- In: BLDY brightness and master brightness as passes over target-1 pixels.
- In: H-blank spans: per-line register changes drawn as scissored passes, or
  a documented fallback if the span count makes it slower.
- Out: OBJ windows and bitmap BGs, which stay on the software path with a
  logged fallback.
- Out: changing the N3DS-only 3D effects.

**Integration points**

- `3ds_port/nitro/src/port_render2d.c`: the span machinery (`LinesSpans`,
  `split->spanLo`/`spanHi`, per-line registers), the window/blend/brightness
  decisions, and `DrawEngine`.
- `3ds_port/game/app/port_compose_pica.c`: the compositor's passes, stencil
  state, and target textures.
- The atlas module from PR 4 and the layer path from PR 5.
- `test_render` and the effect corpus.

**Design**

- Follow `kohjoh`'s proven decomposition:
  - window regions to stencil bits 4-5 (0 outside, 1 WIN0, 2 WIN1);
  - BGs and OBJs in priority order, with the 3D layer where it belongs;
  - alpha blending as two draws: blended where the second-target bit is set,
    opaque where not; each draw updates the bit to the layer's own membership;
  - BLDY on target-1 pixels, then master brightness.
- The stencil bits are per-pixel state; clear them at the start of each
  engine's pass and at the end, so no state leaks between screens.
- H-blank spans: the existing code already computes the line ranges. For each
  span, set the registers and draw the affected layers with a scissor. If a
  frame has too many spans, fall back to the software picture for that frame
  and log the reason. The gate is correctness first; the performance gate is
  that the common effect scenes do not regress.
- Bitmap BGs and OBJ windows: keep the software path, and make the fallback
  per-engine so the other engine can still use GPU 2D.

**Flags and defaults**

- A `gpuEffects` level (or the existing `gpuBgs` level) selects windows,
  blending, and brightness independently, so a regression can be narrowed.
- Default off until the effect corpus passes.
- H-blank spans default to the software fallback until their own timing gate
  passes; the rest of the effect path can ship without them.

**Correctness tests**

- Effect corpus: weather (rain), flash/fade, menu windows, the HM cut-in's
  band, a battle-start transition, and a bright/dark room transition.
- Window regions: WIN0, WIN1, both, and outside; verify the stencil region
  per pixel.
- Alpha blending: all BLDCNT modes, EVA/EVB values, and semi-transparent OBJ.
- Brightness: BLDY and master brightness, including negative/positive.
- H-blank: a known per-line effect; compare against the software picture.
- Stencil leak: run two engines in sequence and verify the second is not
  affected by the first's window state.
- `test_render` under both host targets.

**Performance gate**

- The effect scenes no longer force a full software picture; drawer time drops
  or stays flat, and the fallback rate goes to zero for the corpus except the
  documented exclusions.
- No regression in simple scenes.
- No stencil-related visual artifacts over a 30-minute soak.

**Risks and rollback**

- Risk: blending order differs from the DS. Mitigation: the two-pass model is
  the DS's own order; compare pixels, not just final colors.
- Risk: stencil state leaks. Mitigation: explicit clear at pass boundaries and
  a two-engine test.
- Risk: H-blank spans are slower than software. Mitigation: they are a
  separately gated sub-feature; keep the fallback.
- Rollback: lower the `gpuEffects` level; the software path remains.

**Size and dependencies:** XL. Depends on 5.

---

## 7. `perf/g3d-census` - decide what can be retained, with data

**Merge case (N3DS):** geometry costs 20-30 ms a scene in the field, and the
upper screen's drawer can take 55-60 ms a picture in the worst contention.
Before rewriting the pipeline, the project needs to know which G3 lists are
static, which are dynamic, and which modes dominate. The census is cheap,
deterministic, and de-risks the largest PR in the series.

**Cost removed:** guesswork. It does not remove frame time by itself.

**Scope**

- In: instrumentation of the G3 decode path: per-list hash, word count, vertex
  count, command mix, state changes, texture binds, matrix changes, repeat
  behavior, and estimated retained size.
- In: a machine-readable report over the scene corpus, generated locally.
- In: a classification: retainable static, retainable with per-frame matrix,
  dynamic, unsupported.
- Out: any rendering change, any default change, any committed capture.
- Out: the retained path itself (PR 8).

**Integration points**

- `3ds_port/nitro/src/port_gx3d.c`: the command decode and scene build.
- `3ds_port/nitro/src/port_gx3d_dump.c`: the existing dump/replay tooling.
- `3ds_port/nitro/tests/gx3d_replay.c`: the replay harness.
- `3ds_port/nitro/include/nitro_port_gx3d.h`: the scene/list structures.
- A new report tool, host-side, not shipped in the game.

**Design**

- For each display list, record a content hash and a structural summary. Do
  not store the list's bytes in the report.
- Classify a list as static if the same hash repeats across scenes and the
  camera moves without changing its commands. Classify as dynamic if the game
  rewrites vertices or matrices per scene.
- Record the maximum live vertices, the number of matrix changes per list, the
  texture binds per list, and the modes used. These decide the matrix-palette
  size and the batch strategy for PR 8.
- Run the census on the fixed scene corpus with the same input script as the
  performance protocol.
- The report is generated locally and summarized in the PR. No game content,
  no captured streams, no hashes of assets that could identify content.

**Flags and defaults**

- Compile-time or config-gated; off in release.
- Zero behavior change when off.

**Correctness tests**

- The census is deterministic: the same scene and input produce the same
  report on two runs.
- A host test with a synthetic G3 stream checks the counters and the
  classification.
- The replay harness still passes with the instrumentation enabled.

**Performance gate**

- The census itself does not ship enabled; its overhead is irrelevant to
  release.
- The report covers at least 95% of G3 words in the corpus `[TARGET]`.
- The classification is stable across three runs.

**Risks and rollback**

- Risk: the census is wrong, and PR 8 is built on it. Mitigation: cross-check
  a sample of lists against the dump tool and the replay output.
- Risk: the report tempts the project to commit captured data. Mitigation: the
  report contains counts and hashes only, and the PR states this explicitly.
- Rollback: delete the instrumentation; no runtime dependency.

**Size and dependencies:** M. Depends on 1.

---

## 8. `perf/g3d-retained` - keep object-space geometry on the GPU

**Merge case (N3DS):** the geometry thread spends 20-30 ms a scene transforming
and clipping static meshes on the CPU, and the game waits behind it. Retaining
object-space geometry and transforming it on the PICA vertex unit returns that
time to the frame, with the same picture.

**Cost removed:** per-vertex CPU transform, clip, and screen-space vertex
rewrite for static display lists. The existing path rebuilds and re-uploads the
same vertices every scene.

**Scope**

- In: retained immutable vertex/index buffers for static G3 lists.
- In: a matrix-palette vertex shader (16 matrices x 4 rows, as `kohjoh` uses)
  and packed per-vertex matrix indices.
- In: per-frame matrix updates only; no per-vertex CPU work for retained
  lists.
- In: invalidation when a list's commands change in place, using the existing
  command hash.
- In: per-scene fallback to the CPU path for dynamic lists and for N3DS-only
  effects that need screen-space vertices.
- Out: lighting (PR 9), shadows, edge marking, W-buffer, stereo, and 60 FPS
  interpolation. Those stay on the existing path or disable the retained path
  for that scene.
- Out: a new texture pipeline; reuse `get_texture` and the existing cache.

**Integration points**

- `3ds_port/nitro/src/port_gx3d.c`: the decode/scene build, the command hash
  (`NitroPort_Gx3dSameAs`), and the list boundaries.
- `3ds_port/nitro/include/nitro_port_gx3d_vertex.h`: the vertex and batch
  structures; a new retained-vertex format.
- `3ds_port/game/app/port_gx3d_pica.c`: `NitroPort_PicaPrepareScene`,
  `NitroPort_PicaDrawScene`, `bind_batch`, the vertex buffers, and the scene
  depth normalization.
- New: `gx3d_retained.v.pica`, alongside `gx3d_passthrough.v.pica`.
- `3ds_port/game/app/port_pica.h`: the new entry points.
- Existing tests: `test_gx3d`, `test_gx3d_plumbing`; the `gx3d_replay`
  harness (`make -C 3ds_port/nitro replay`).

**Design**

- The CPU still decodes G3 commands and decides what is static. It builds an
  immutable object-space vertex/index buffer per retained list, once, and
  keeps it across scenes.
- The retained vertex carries position, normal, UV, and a matrix index. Pack
  positions to 16-bit where the census shows it is safe; keep 32-bit for
  precision-sensitive geometry.
- Per scene, the CPU writes only the matrix palette (the list's model/view
  matrices, up to 16 per batch) and any per-object uniforms. The vertex shader
  does the transform; the PICA rasterizer does the rest.
- Batch by material and by matrix-palette capacity. If a batch needs more than
  16 matrices, split it or fall back for that batch. The census says whether
  16 is enough; do not assume.
- Static lists are the common case in the field. Dynamic lists (characters,
  followers, animated props, direct vertex writes) stay on the CPU path.
- In-place rewrites: hash the list's commands as they are decoded. If the hash
  differs from the retained copy, rebuild that list before drawing. This is
  the same invalidation idea as the 2D generation check, applied to G3.
- Depth and fog: preserve the DS's depth semantics. If the existing
  `normalize_depth` behavior is needed, implement the equivalent in the
  retained shader, or keep the scene on the CPU path until it matches.
- N3DS-only effects: if sun shadows, edge marking, W-buffer, stereo, or
  interpolation need CPU screen-space vertices, the scene uses the existing
  path for that frame. The retained path is an optimization, not a
  replacement for those features. This is the rule that keeps the N3DS
  feature set intact.
- Memory: retained buffers live in the linear heap or VRAM, whichever the
  census and the memory log support. They are bounded and evictable; a scene
  that exceeds the budget falls back rather than failing to boot.

**Flags and defaults**

- A `gpuGeometry` level or config key selects retained, CPU, or auto.
- Default off until the replay A/B and the golden frames pass; then auto for
  scenes the census classifies as static.
- Per-scene fallback is logged once, with the reason.

**Correctness tests**

- `test_gx3d` and `test_gx3d_plumbing` under both host targets.
- `gx3d_replay` A/B: the same captured stream through the CPU path and the
  retained path; compare client pixels and final state.
- In-place rewrite: change a list between scenes and verify the retained copy
  is rebuilt before it is drawn.
- Matrix-palette overflow: a synthetic batch with more than 16 matrices; verify
  the split or fallback.
- 30-minute soak with scene transitions, battles, and menus: no stale
  geometry, no leak, no progressive slowdown.
- Golden frames: title, field, battle, Distortion World, and a cutscene.

**Performance gate**

- Geometry time per scene moves from 20-30 ms toward 8-12 ms `[TARGET]`.
- The geometry thread's p95 drops; the game's wait behind it drops.
- No increase in dropped scenes or missed V-blanks.
- No regression in scenes that fall back.

**Risks and rollback**

- Risk: the shader does not fit the register budget with all the material
  modes. Mitigation: census first; start with the dominant modes; fall back
  per material.
- Risk: matrix-palette batching is inefficient. Mitigation: measure draws per
  batch; split by material, not by object.
- Risk: stale retained geometry after an in-place rewrite. Mitigation: hash
  invalidation, a replay test, and a conservative rebuild on any doubt.
- Risk: memory pressure on N3DS. Mitigation: bounded buffers, eviction, and a
  fallback to the CPU path.
- Rollback: set `gpuGeometry` to CPU; the existing path is untouched.

**Size and dependencies:** XL. Depends on 7 and 1.

---

## 9. `perf/g3d-lighting` - move DS-exact lighting to the vertex unit

**Merge case (N3DS):** after retained geometry, per-vertex lighting is the
remaining CPU cost in the geometry thread. `kohjoh` proved a DS-exact lighting
model fits PICA at 409 instructions and 94 registers, pixel-exact on held
frames. The same win is available here for the material modes that fit.

**Cost removed:** per-vertex CPU lighting (`light_vertex`, `shade`,
`make_products`, `update_light_cache`, the normal cache) for scenes that use
the retained path.

**Scope**

- In: a PICA vertex-lighting shader that matches the CPU path's fixed-point
  arithmetic on held frames.
- In: diffuse, ambient, specular, emission, and the normal cache semantics
  that affect the result.
- In: per-material fallback when the shader cannot match a mode.
- Out: sun shadows, edge marking, and any N3DS-only effect that needs the CPU
  path. Those keep the existing behavior.
- Out: changing the lighting model or "improving" the look. The goal is
  equality, not a remaster.

**Integration points**

- `3ds_port/nitro/src/port_gx3d.c`: `light_vertex`, `shade`, `make_products`,
  `update_light_cache`, `normal_slot`, `settle_lighting`, and the vertex
  output.
- `3ds_port/game/app/port_gx3d_pica.c`: the retained shader and its uniforms.
- New: `gx3d_lit.v.pica`, or an additional DVLE in the retained shader.
- `3ds_port/nitro/include/nitro_port_gx3d_vertex.h`: the normal and color
  attributes.
- Existing tests: `test_gx3d`; the `gx3d_replay` harness; plus a new lit-frame
  reference.

**Design**

- Reproduce the DS's lighting arithmetic exactly: the same fixed-point
  products, the same normal transformation, the same clamping, and the same
  material/light ordering. `kohjoh`'s shader is the reference for the
  technique; the constants and material mapping come from
  `pokeplatinum-3ds`'s CPU path.
- Start with the material modes the census says dominate the field and
  battles. A mode that cannot be matched stays on the CPU path for that batch.
- Keep the CPU path's normal cache semantics: a normal reused across vertices
  must produce the same color as the cached CPU result. If the shader cannot
  reproduce the cache's rounding, fall back for that batch.
- Uniforms: lights, material colors, and the matrix palette. Watch the
  register budget; the census and the shader compiler output decide.
- The retained geometry path and the lit path are independent flags: retained
  geometry can ship before lighting, and lighting can be disabled without
  losing retention.

**Flags and defaults**

- `gpuLighting` level or config key: off, auto, on.
- Default off until the lit-frame comparison passes across the corpus.
- Per-batch fallback remains.

**Correctness tests**

- Lit-frame comparison: held frames across the corpus, zero differing client
  pixels. Include a worst-case scene with many lights and materials.
- Normal-cache test: a mesh with shared normals; compare CPU and shader output.
- Specular and emission: a material that uses each; compare.
- Fallback: a mode the shader does not support; verify the CPU output is used
  and the frame is still correct.
- `test_gx3d`, `gx3d_replay`, and a 30-minute soak.

**Performance gate**

- Geometry time drops further against PR 8, especially in the field and
  battles.
- No increase in dropped scenes.
- Shader compilation stays within the project's startup budget; log the
  instruction/register count.

**Risks and rollback**

- Risk: a 1-bit color difference on a held frame. Mitigation: exact arithmetic,
  a pixel test, and a per-mode fallback. "Close" is not accepted.
- Risk: register pressure forces spills. Mitigation: split the shader by
  material mode, or fall back.
- Risk: lighting changes interact with the N3DS shadow/edge path. Mitigation:
  keep those on the existing path and do not fold them into the lit shader.
- Rollback: set `gpuLighting` off; retained geometry still works.

**Size and dependencies:** XL. Depends on 8.

---

## 10. `perf/lowend-schedule` - rebalance after the costs are gone

**Merge case (N3DS):** once the change check and geometry are cheaper, the old
priorities and present-skip rules are tuned for the wrong costs. Rebalancing
turns the saved time into stable frames instead of skipped pictures.

**Cost removed:** thread contention, over-eager present skipping, and drawer
starvation that the old cost model hides.

**Scope**

- In: measure the new critical path with telemetry, then adjust priorities,
  present-skip hysteresis, and the display thread's wait policy.
- In: a 2-core scheduling mode for the eventual O3DS tier, kept behind a flag.
- Out: changing the game's logic rate or the 60 FPS interpolation on N3DS.
- Out: changing N3DS defaults without evidence.

**Integration points**

- `3ds_port/game/app/main_3ds.c`: `StartDrawers`, `StartMapDrawer`, the
  display loop, `sComposing`, `sStretchShown`, and the present decisions.
- `3ds_port/nitro/src/port_speed.c`: frame pacing and speed state.
- `3ds_port/nitro/src/port_thread.c`: thread creation and priorities.
- `3ds_port/game/app/port_compose_pica.c`: present/keep/field-picture logic.
- `test_threads`, `test_speed`, and the telemetry summary.

**Design**

- Do not tune by intuition. Run the telemetry corpus after PRs 2-9 and find
  the new critical path per scene class: field, battle, menu, effect.
- Adjust in this order:
  1. present-skip hysteresis: skip only when the next scene cannot be ready,
     not merely because the previous scene was late;
  2. drawer vs geometry priority: the geometry-first rule was correct when
     geometry was 30 ms; it may be wrong when it is 8 ms;
  3. display-thread wait policy: the display thread must not wait behind a
     drawer that is no longer the bottleneck;
  4. core assignment: keep the N3DS topology; add a 2-core mode for O3DS that
     merges or serializes work rather than pretending there are four cores.
- Every change is individually switchable and measured. A change that does not
  improve p95/p99 is reverted.
- The O3DS 2-core mode is not enabled by default and does not affect N3DS.

**Flags and defaults**

- N3DS defaults stay as they are until a scene class shows a measured win.
- The 2-core mode is opt-in and documented as part of the O3DS tier.
- A config key restores the old schedule for A/B.

**Correctness tests**

- `test_threads` and `test_speed`.
- A long soak with scene transitions, audio, and menus: no deadlock, no
  starvation, no audio dropout.
- A test that a skipped present still shows the correct picture and the
  correct 2D/3D pairing.
- A test that the display thread makes progress under a synthetic slow drawer.

**Performance gate**

- p99 frame time improves in at least one scene class, with no regression in
  the others.
- No increase in missed V-blanks or dropped scenes.
- The 2-core mode is stable on O3DS for 30 minutes (internal gate).

**Risks and rollback**

- Risk: priority changes cause audio or input starvation. Mitigation: a
  watchdog counter and the old schedule behind a flag.
- Risk: present-skip changes make motion less smooth. Mitigation: measure
  skipped presents and scene lateness together; do not optimize one at the
  expense of the other.
- Rollback: restore the old constants; the code is unchanged.

**Size and dependencies:** M. Depends on 2-6 and 8-9.

---

## 11. `perf/o3ds-tier` - assemble the opt-in low-end profile

**Merge case (N3DS):** none directly. This PR is the payoff for the O3DS
stretch goal, and it must not change New 3DS behavior. It is last for that
reason.

**Cost removed:** the configuration gap between "the shared backends are fast
enough on O3DS" and "the remaster is actually turned on with the right
effects."

**Scope**

- In: a `tier o3ds` config profile that enables the remaster with the effects
  that fit: both screens filled, native-resolution 3D, widescreen layout, the
  bottom-screen menu, crisp 2D, stable 30 FPS, audio and saves intact.
- In: explicit exclusions: 60 FPS interpolation, stereo 3D, sun shadows, edge
  marking, xBRZ, 2x2 supersampling, full WideArt.
- In: boot-time memory/VRAM checks with a clean fallback to the classic
  display.
- In: documentation that the tier is experimental and opt-in.
- Out: auto-enabling on O3DS. Detection may suggest it, but the user chooses.
- Out: changing any N3DS default.

**Integration points**

- `3ds_port/game/app/main_3ds.c`: `ReadRemasterConfig`, `sRemaster`, the
  option handlers, and `APT_CheckNew3DS`.
- `3ds_port/game/app/port_compose_pica.c`: the small-display path and the
  memory checks.
- `docs/REMASTER.md` or a new `docs/O3DS.md`: the profile and its limits.
- `test_options` and a config-parse test.

**Design**

- The config parser accepts a tier name. `tier n3ds` is today's behavior;
  `tier o3ds` turns on the remaster with the exclusion list.
- The tier is parsed into its own variable and resolved after the whole file,
  so `remaster on` and `tier o3ds` mean the same thing in either order.
- On O3DS, `remaster on` without a tier selects the `o3ds` tier, or logs a
  warning and falls back to classic. It never applies the N3DS profile blindly.
- The tier is a profile, not a separate renderer. It selects the shared
  backends and turns off the effects that do not fit.
- On boot, check the memory and VRAM budget before allocating the compositor.
  If the check fails, log the reason once and fall back to the classic display.
  A failed allocation must never leave a black screen.
- The tier is default off on every model. On O3DS, the classic display remains
  the default until the user opts in.
- The profile's target experience and internal gates are in
  [`O3DS_TIER.md`](O3DS_TIER.md).

**Flags and defaults**

- `tier o3ds` off by default.
- The individual backend flags remain available for debugging.
- N3DS behavior is byte-identical when the tier is off.

**Correctness tests**

- Config parse: `tier o3ds`, `tier n3ds`, unknown tier, missing keys.
- Boot on O3DS with the tier on: both screens, 3D, menu, audio, save.
- Boot on O3DS with the tier off: classic display, unchanged.
- Forced allocation failure: clean fallback, no crash.
- Save round-trip: write, reboot, load.
- N3DS regression: the tier-off logs and golden frames match the pre-PR
  build.

**Performance gate**

- The internal O3DS gates in `O3DS_TIER.md` pass.
- No N3DS performance change with the tier off.
- No increase in boot time beyond the documented check.

**Risks and rollback**

- Risk: the tier is mistaken for a support promise. Mitigation: docs call it
  experimental; the PR description says it defaults off and is not a
  maintainer obligation.
- Risk: an O3DS allocation failure produces a black screen. Mitigation: the
  boot check and fallback.
- Rollback: remove the profile; the shared backends remain.

**Size and dependencies:** S. Depends on all core PRs.

---

## Optional 12. `perf/g3d-fifo` - cache and replay G3 submission

**Why optional:** PR 8 retains static geometry. If the census shows that
dynamic lists and state-only streams still dominate the geometry thread, this
PR removes the repeated decode and submission. If retained geometry already
covers the cost, this is unnecessary complexity.

**Merge case (N3DS):** `kohjoh` replays 74% of FIFO words, and its hotpaths A/B
(display-list cache, state-only replay, compact hot loops) cut Azahar game logic
from 16.648 ms to 15.430 ms (-7.3%). The same shape of repeated decode exists
in `pokeplatinum`'s G3 stream.

**Scope**

- In: a display-list cache with exact packed-opcode validation, state-only
  replay, and batching of repeated submissions.
- In: invalidation on any state or command change.
- Out: retained geometry (PR 8) and lighting (PR 9).

**Integration points:** `port_gx3d.c`, `port_gx3d_dump.c`, `gx3d_replay`, and
the FIFO/command-ring code in `port_gx3d.c`.

**Design**

- Cache a list by its exact command bytes and the state it inherits. On replay,
  validate the packed opcodes and the live parameters before reusing.
- State-only lists replay their state changes without re-decoding vertices.
- A list that misses on its key is decoded normally; a list proven uncacheable
  is marked and skipped next time.
- This is the same technique as `kohjoh`'s `KJ_DL_CACHE`, adapted to
  `pokeplatinum`'s command set.

**Tests:** replay equivalence, invalidation fuzz, `test_gx3d`,
`test_gx3d_plumbing`, 30-minute soak.

**Gate:** logic time drops in the scenes the census identifies; no stale state;
no increase in dropped scenes.

**Size and dependencies:** M. Depends on 7; can run in parallel with 8.

---

## Optional 13. `perf/game-hotpaths` - fix what telemetry actually finds

**Why optional:** this is not a renderer change. It is a place for game-logic
wins that the telemetry surfaces, such as repeated per-frame data transforms
or per-word command submission. Do not assume the hot path; measure it.

**Merge case (N3DS):** the game thread is on the same core as the display
thread and engine B's drawer. A logic win returns time to all three.

**Scope**

- In: one measured hot path per PR, with before/after `[perf]` evidence.
- Out: speculative rewrites, gameplay changes, save-format changes.

**Integration points:** determined by the telemetry; likely
`3ds_port/game/app/main_3ds.c`, the game's per-frame update, and the GX
submission path.

**Tests:** the game test suite, save round-trip, and a 30-minute soak.

**Gate:** logic time drops by more than noise; no behavior or save change.

**Size and dependencies:** S. Depends on 1.

---

## Cross-PR checklist

Before opening any PR:

- [ ] The branch name matches the brief (`perf/...`).
- [ ] The diff contains one idea and no line-ending-only files.
- [ ] The old path is selectable and the new path defaults off until gated.
- [ ] `make test` passes, and so do the host32 suites.
- [ ] `make game` builds for 3DS.
- [ ] The PR includes before/after logs, the scene, the build, and the
      hardware.
- [ ] The correctness test is deterministic and does not require the
      maintainer's hardware.
- [ ] No game content, no captured assets, no ROM-derived files.
- [ ] The commit and PR description disclose AI assistance with
      `Co-Authored-By: Claude`.
- [ ] The PR description follows the template in
      [`UPSTREAM_NOTES.md`](UPSTREAM_NOTES.md).
- [ ] If the PR touches adapted `kohjoh` code, the provenance note is in the
      commit and the file header.

## What not to include

- A giant "O3DS support" PR. It will be rejected, and it conflates the
  maintainer's support policy with a set of performance fixes.
- A new renderer that bypasses the existing compositor. The project already
  has a working PICA pipeline; extend it.
- A benchmark request to the maintainer.
- A default change that turns on an unproven path for existing New 3DS users.
- Any claim that "kohjoh does it" is sufficient evidence for a `pokeplatinum`
  scene. The census and the pixel tests decide.
