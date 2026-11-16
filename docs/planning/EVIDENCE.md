# Evidence

> Planning document. Every number below carries a source tag. If a claim has no
> tag, it is not evidence yet.

## 0. Source tags

| Tag | Meaning |
| --- | --- |
| `[PP]` | Quoted from `pokeplatinum-3ds`'s own documentation or logs (`docs/REMASTER.md`, `docs/`). These are the project's measurements on New 3DS hardware. |
| `[KJ]` | Measured by `kohjoh`, the HGSS Old 3DS port. Almost all of these are **Azahar instruction counts**, not Old 3DS cycles, unless a line says "O3DS log". |
| `[SPEC]` | Public hardware specification, not a measurement of either project. |
| `[TARGET]` | A planning target. Not measured. Must not appear in a PR description as a result. |

The distinction matters. `kohjoh`'s Azahar tick counts are excellent for
comparing two builds of the same code on the same emulator. They are not a
prediction of `pokeplatinum-3ds` frame time on a New 3DS, and they are not a
prediction of Old 3DS cycles. Azahar also charges nothing for PICA vertex
work, so a change that moves work from the CPU to the GPU always looks free
there. `[KJ]`, `docs/worklog/2026-11-15-hardware-cuts.md`

**Every `[PP]` number is dated.** They come from `docs/REMASTER.md` and commit
messages written between 2026-10-14 and 2026-11-12, and upstream merges
several performance PRs a week. Before any brief below is implemented, its
cost is re-measured on current `main` (section 6, step 0). A `[PP]` number
that upstream has since fixed is history, not a merge case; see section 1.2.

## 1. What the New 3DS pays today

`pokeplatinum-3ds` is built for the New 3DS. It already boots on an Old 3DS,
but only with the classic display (`remaster off` is the Old 3DS default;
`docs/REMASTER.md`, Settings). The costs below are visible on the hardware the
maintainer tests on. The Old 3DS is where they become fatal, but it is not
where they start.

### 1.1 The frame

- The game logic runs at 30 Hz; the remaster presents up to 60 pictures a
  second with interpolation. A 30 Hz game frame is 33.3 ms; a 60 Hz present
  interval is 16.7 ms.
- On a New 3DS, engine A's 2D drawer and the geometry thread share core 2.
  Engine B's drawer runs on core 1's share (or on core 0 when the geometry
  took core 1); the game, the display thread, and the sound thread run on
  core 0. `[PP]`, `main_3ds.c` `StartDrawers`, `StartSound`. (`REMASTER.md`
  still says engine B is on core 0; the code is newer.)
- On an Old 3DS the port already has a 2-core topology: the geometry on
  core 1's share, one drawer for both engines on core 0. `[PP]`,
  `StartDrawers(..., isNew3ds = false)`
- The geometry thread runs first on core 2 when both are ready. `[PP]`
- A 2D picture that is handed over is upscaled into the compositor's textures.
  That handover is part of the drawer's measured time. `[PP]`
- The **GPU is the same on both models**: PICA200 at 268 MHz, 6 MB of VRAM.
  `[SPEC]`, coffeepot `ctr/hardware/gpu.md`. The New 3DS's extra speed is all
  CPU (804 MHz, four cores, L2). On the New 3DS the GPU already carries the
  remaster's defaults: the upper screen drawn 2x2 and scaled down
  (`smooth3d`), stereo, and 60 FPS presents.

The important consequences: **2D drawer time and geometry time are not
separate budgets.** They compete for the same core, and the game waits behind
both. And **GPU time is not free headroom on a New 3DS.** Moving work from
an 804 MHz CPU to an unchanged 268 MHz GPU can lose, and needs its own gate.

### 1.2 The 2D change check

The software 2D renderer decides whether an engine's picture changed before it
redraws it. It compares the small parts (registers, palettes, OAM) first, and
hashes VRAM only when they match.

**The 864 KB / 15 ms cost is already fixed upstream.** Before 2026-10-30 the
check read all of engine A's VRAM (864 KB), about 15 ms of every 33 on core 2,
and because the 3D's texture palettes (bank E) were in it, the upper screen
was redrawn 5-11 times a second in towns with nothing changed. `[PP]`, commit
`313ac80`. That commit made the check hash only the VRAM the screen shows:
each shown BG's map, the tiles it uses and their palettes, the OBJ VRAM while
an OBJ is shown, and the VRAM display's bank (`EngineShownVramSignature`). The
next day, `d0dfe9e` stopped window-only H-blank effects (the building-exit band,
circle fades) from forcing the full read. `[PP]`

What remains, and must be measured before it is a merge case:

- the shown-VRAM hash on unchanged frames. Its time is already logged: the
  `[perf] game` line splits engine A's drawer into checking, drawing, and
  sprites (`NitroPort_Render2DTimes`). No current number is quoted in
  `REMASTER.md`;
- the full read that still happens with a non-window H-blank effect or a
  bitmap BG;
- redraws the check cannot avoid because the game really rewrote the bytes
  (the `[perf] game` line counts redraws by cause:
  `NitroPort_Render2DChangeStats`).

An earlier draft of this plan quoted the 864 KB / 15 ms as today's cost and
built its first merge candidate on it. It is not today's cost.

### 1.3 The 2D drawer

When a picture is drawn, the drawer costs about **16.2 ms**, of which **4.6 ms**
is handing the picture over to the compositor's textures. `[PP]`, from a
`[perf] game` line logged after the `313ac80` fix:

> `upper 29.9/s (6.0/s new: 4.0 for registers, palettes or sprites, 2.0 for
> VRAM), 16.2 ms, 4.6 of it handing over (core 2)`

Field effects make this worse. On the Cycling Road, with a battle-start effect
playing, engine A's drawer got **8-15 pictures a second at 50-87 ms each**, and
the effect ran at a third of its speed. `[PP]`

The HM cut-in is a known worst case: **37-77 ms a frame** under Route 206's
bridge, 15-32 ms in Eterna before that. `[PP]`

These are not Old 3DS problems. They are New 3DS frames that miss their
deadline.

### 1.4 The geometry thread

3D is decoded, transformed, lit, and clipped on the CPU, then submitted as
screen-space triangles. The project measures:

- **about 20-30 ms a scene** in the field: 18-30, 20-28, 25-29, and
  23.9 → 20.0 ms in different logs. `[PP]` (The range is ours; no single log
  says "20-30".)
- **21-29 ms a scene** while a field effect plays, while engine A's drawer
  simultaneously drops to 8-15 pictures a second at 50-87 ms each. `[PP]`
- **55-60 ms** for the upper screen's drawer to hand over each picture when
  the geometry is busy 80% of the time at the top of Route 215 in the rain.
  `[PP]`
- About **30 ms a picture** on the geometry's core in the rain, 10-15 ms of it
  handing over, next to 20-28 ms of geometry on Route 215. `[PP]`

A scene has two V-blanks to finish. When it does not, the previous scene stays
on screen and the next one arrives a frame late. The game waits for the
geometry thread before its next frame's display work; behind a 25 ms stretch
where maps change, the game "waited for it and stepped unevenly". `[PP]`

The current skip logic is conservative and correct, but it is treating a
symptom. The cost is the CPU transform and lighting of geometry that has not
changed.

Two parts of the geometry thread already have caches or costs worth knowing
before designing around them:

- **Lighting already keeps 64 normals' colours**, forgotten together when the
  vector matrix, the lights, the material, or the polygon's lights change
  (12% less lighting work). `[PP]`, `REMASTER.md`
- **60 FPS in-between scenes are built on the CPU from clip-space polygons.**
  With `fps60` on (the New 3DS default), each scene's polygons are recorded in
  clip space, matched in order with the previous scene's, and a halfway scene
  is clipped and culled again (`PolyRecord`, `replay_polygon`). The in-between
  part costs 3-9 ms a scene (4.7 ms after the latest cut); the `[perf]
  geometry's work` line splits it out. `[PP]` Any retained-geometry design that
  falls back to the CPU path whenever interpolation is on is therefore off in
  the New 3DS's default configuration.

### 1.5 Audio

The mixer already mixes in blocks (`BLOCK = 128` in `port_sound_chip.c`), so
the missing win is narrower than "rewrite the mixer". `[PP]`

What is missing is a **decoded-ADPCM cache**. A looping instrument re-decodes
the same nibbles every time its decoder state is clean. `kohjoh` measured the
cost of that decode and the win from caching it (section 2.3).

The sound thread runs on core 0, above the game, beside the display thread
(`StartSound`). `REMASTER.md` describes core 0 as "nearly full" during the
lower-screen map work. Mixer time is therefore taken directly from the game.
There is **no mixer timing in the `[perf]` lines today**, so the N3DS size of
this cost is unknown until `perf/telemetry` adds one.

### 1.6 Scheduling

The current topology is sensible for a New 3DS: geometry and engine A's drawer
on core 2, engine B on core 1's share, game, display, and sound on core 0. The
Old 3DS topology also exists already (section 1.1). But the priorities and the
present-skip rules are tuned around the current costs. Once the change check and the
geometry are cheaper, the old pacing rules will be wrong: they can skip a
present that is now affordable, or starve a drawer that is now the critical
path. This is why `perf/lowend-schedule` exists, and why it comes after the
costs are removed rather than before.

## 2. What kohjoh measured

`kohjoh` is an HGSS port to the Old 3DS. It solved the same class of problems:
DS-era software rendering on PICA200 hardware, with a CPU about a third as
fast as an unlocked New 3DS's and the same GPU. Its techniques transfer; its
game code does not.

### 2.1 Retained 2D and the tile atlas

`kohjoh`'s 2D renderer translates one engine's per-scanline state into ordered
GPU passes:

- window regions become stencil bits;
- BGs and OBJs are drawn in priority order;
- alpha blending is two draws (blended where the second-target bit is set,
  opaque where not);
- brightness is a pass over target-1 pixels, then a master-brightness pass.

Crucially, when a frame has no per-line register changes, each text BG and the
OBJ layer keep last frame's quads. The cache is exact: it compares the layer's
palette and the tile bytes it used, with no write tracking and no hashing of
the whole VRAM. `[KJ]`, `src/graphics/g2d/g2d.c`

The tile atlas is **1024x1024 RGBA5551**, built from 8x8 DS tiles in Morton
order (which is PICA's native tiling). Cache identity is content plus effective
palette, mode, and mapping. Palette changes invalidate dependent tiles, not the
whole atlas. `[KJ]`, `src/graphics/resources/atlas.c`

`kohjoh`'s local Coffeepot tile benchmark, on Old 3DS, for a 416-tile synthetic
setup: direct citro2d 1.497 ms, manual vertices 1.019 ms, retained chunks
0.899 ms, cached surface 0.868 ms. `[KJ]`, approximate local benchmark, not a
`pokeplatinum` scene. Cached surfaces also cost extra VRAM and produce redraw
spikes, which is why the proposed baseline is retained chunks plus dynamic
tiles, with surfaces only for static content.

### 2.2 Retained 3D, the matrix palette, and lighting

`kohjoh` retains G3 display lists as object-space geometry and transforms them
on the PICA vertex unit with a **16-entry matrix palette**. The vertex shader
reads a matrix index from the packed vertex and does four `dp4`s against
`palette[64]` (16 matrices x 4 rows). `[KJ]`,
`src/graphics/pica/shaders/g3d.v.pica`

The display-list cache replays **74% of FIFO words** (`[KJ]`,
`docs/worklog/2026-11-12.md`). On Azahar, the hotpaths A/B (display-list
cache, state-only replay, compact hot loops) cut game logic p50 from
**16.648 ms to 15.430 ms (-7.3%)**. `[KJ]`,
`docs/worklog/2026-11-14-hotpaths.md`. The worklog explicitly warns that the
replay-rate increase includes state-only streams and must not be presented as a
retained geometry hit-rate gain.

The lighting shader reproduces the DS's fixed-point lighting semantics in
PICA vertex code: **409 instructions, 94 float registers including constants**
(the lit-plans worklog's count, before the later light-skip flags).
On held frames it is pixel-exact against the CPU reference: Ho-Oh frames
2301/2501 match across the complete dual-screen client crop (801x960 screenshot
pixels), and the Route 34 field matches with zero differing client pixels.
`[KJ]`, `docs/worklog/2026-11-15-lit-plans.md`

This proves a DS-exact lighting model is achievable on PICA without visible
drift. It does **not** prove that lighting on the PICA is faster, and
`kohjoh`'s own hardware run says it often is not:

- Sending every list with a NORMAL down the per-vertex PICA-lit path, static
  map scenery included, took Old 3DS captured frames in Goldenrod from about
  **36 ms to 57 ms**. Azahar stayed at 30 FPS throughout, because it does not
  charge for vertex shader work. `[KJ]`, O3DS log,
  `docs/worklog/2026-11-15-hardware-cuts.md`
- The fix (`84d46dc`) **bakes stable lit lists once with exact CPU lighting**
  and replays them as literal-colour blocks through the unlit shader. Only
  lists whose lighting key misses on consecutive calls stay PICA-lit. Azahar
  logic p50 fell from 25.35 to 14.06 ms, with held frames pixel-identical.
  `[KJ]`
- The lit shader now skips disabled lights and lights with no specular
  colour: **101 instructions per one-light vertex instead of 409**
  (`eeb4b37`). Its flags live in the unused `.w` of float uniforms, because
  PICA bool uniforms read false in Azahar. The float uniform file is full: the
  worklog counts "91 float uniforms plus 7 constants of the 96", so there is
  no room for a separate flags array. `[KJ]`
- Culling retained blocks wholly outside the clip volume's side planes before
  copying them (`413d0cc`) cut triangles from 5.02M to 1.94M and draws from
  80.3k to 61.7k over 600 frames. `[KJ]`

So the transferable lesson is: **retain and cache on the CPU first; light on
the PICA only what cannot be baked; count GPU work, not Azahar time.** Fitting
`pokeplatinum-3ds`'s material set is still the census's question.

### 2.3 Decoded ADPCM

`kohjoh` added a decoded-sample cache for voices whose decoder state came from
the data alone (`adpcmClean`). On Azahar, Goldenrod:

| Build | Ticks per channel-sample | Mixer core share |
| --- | --- | --- |
| Measurement only | 107.6 | 14.8% |
| Decoded-ADPCM cache | 48.0 | 6.6% |

`[KJ]`, `docs/worklog/2026-11-15-audio.md`. The cache halved the mixer's
instruction count and cut its core share by more than half. A later kernel
flush of wave buffers kept the same numbers.

`pokeplatinum-3ds` already block-mixes, so the expected win is smaller in
absolute terms, but the decode itself is the same shape of work. `[PP]`/`[KJ]`

### 2.4 The Old 3DS reality check

`kohjoh` is not a blanket 30 FPS guarantee on Old 3DS:

- At its first profiled O3DS run (2026-11-12), Route 34 was near 30 FPS and
  Goldenrod unplayable; field logic was about 37 ms before the decoder fast
  paths. `[KJ]`, O3DS log, `docs/worklog/2026-11-12.md`
- Goldenrod captured frames later measured about 36 ms, then 57 ms after the
  PICA-lighting change above, before the hardware cuts. `[KJ]`, O3DS log.
  O3DS ran about 2.3x slower than Azahar for logic and publish. A post-cut
  O3DS number is not yet in the worklog.

This is exactly why the O3DS tier is a stretch goal with its own gates, not a
promise inherited from `kohjoh`. A technique that works does not automatically
produce a playable frame on weaker hardware.

## 3. Transfer matrix

| kohjoh technique | `pokeplatinum-3ds` cost addressed | Expected New 3DS effect | Confidence | First proof |
| --- | --- | --- | --- | --- |
| Dirty-generation 2D change check (ours; `kohjoh` compares used tiles instead) | The residual shown-VRAM hash and the H-blank/bitmap full read, size unknown | Unknown until step 0; possibly small after `313ac80` | Low until measured | `perf/render2d-change`: differential fuzz + drawer timing |
| Retained text-BG layers | Re-rasterizing unchanged BGs every frame | Lower drawer time in towns, menus, battles | High | `perf/g2d-atlas-text`: golden frames + timing |
| Tile atlas (512-1024) + palette dependencies | Software tile decode and CPU-to-GPU copy | Fewer bytes moved, fewer draws; foundation for all GPU 2D | High for text, medium for affine/extended | `perf/g2d-atlas-text`, `perf/g2d-layers` |
| Stencil windows + blend/brightness passes | Software windows, blending, brightness, H-blank spans | Full GPU 2D coverage without per-span CPU work | Medium | `perf/g2d-effects`: effect corpus |
| Retained object-space G3 + 16-entry matrix palette + clip-volume cull | 20-30 ms CPU transform/clip per scene, plus 3-9 ms of in-between scenes | Target 8-12 ms geometry per scene `[TARGET]`, only if it also covers `fps60` | Medium | `perf/g3d-retained`: replay A/B + timing + GPU work counts |
| Baked lighting for stable lists; PICA lighting for the rest | Per-vertex CPU lighting | More geometry time returned without new GPU load for static scenery | Medium | `perf/g3d-lighting`: lit-frame pixel compare + GPU work counts |
| Decoded-ADPCM cache | Per-sample decode of looping instruments | Lower mixer CPU; core time back to the game | High | `perf/audio-adpcm`: bit-exact output + tick count |
| Display-list cache / state replay | Repeated G3 decode and submission | Lower logic time in worst-case scenes | Medium | `perf/g3d-fifo` (optional) |
| Present pacing and priorities | Over-eager skip or drawer starvation | More stable frame times once costs drop | Medium | `perf/lowend-schedule`: p95/p99 histograms |

The matrix follows the 2D, 3D, audio, scheduling grouping, not PR order or
confidence. PR order is chosen so each step makes the next one measurable.

## 4. What does not transfer

- **HGSS game logic, maps, scripts, and assets.** None of it is relevant, and
  none of it may be copied. `kohjoh` is GPL-3.0, like `pokeplatinum-3ds`, but
  game content is never part of the adaptation.
- **`kohjoh`'s citro2d compositor.** `pokeplatinum-3ds` has its own compositor
  and its own PICA command submission. The 2D *technique* transfers; the API
  calls do not.
- **Old 3DS cycle numbers.** `kohjoh`'s Azahar ticks are instruction counts on
  an emulator. They rank changes; they do not predict milliseconds.
- **The assumption that PICA lighting fits every material, or is cheaper.**
  `kohjoh`'s shader is 409 instructions worst case and its float uniform file
  is full (section 2.2). `pokeplatinum-3ds` has more material
  modes, N3DS-only effects, and a different texture pipeline. The census
  decides what fits; GPU work counts decide whether it pays.
- **Azahar as a GPU judge.** It does not charge for vertex work. GPU-side
  changes are judged by vertices, shader instructions per vertex, triangles,
  and draws, and on hardware.
- **Stereo 3D, sun shadows, edge marking, xBRZ, 2x2 supersampling, and full
  WideArt.** These are New 3DS features. They stay on the existing path and
  are never folded into the shared low-end backend. 60 FPS interpolation is
  different: it is on by default on New 3DS, so the shared geometry backend
  has to support it (section 1.4) or it does not help the default
  configuration.
- **A blanket Old 3DS 30 FPS promise.** See section 2.4.

## 5. Evidence we can produce without the maintainer

The maintainer does not need to run benchmarks. The evidence pack has to stand
on its own.

### 5.1 Correctness

- Deterministic host tests: `make test`, plus the host32 suites
  (`make -C 3ds_port/nitro TARGET=host32 test`,
  `make -C 3ds_port/game TARGET=host32 test`). The suites already include
  `test_render`, `test_gx3d`, `test_gx3d_plumbing`, `test_sound_chip`,
  `test_threads`, `test_speed`, and the VRAM/upscale/shadow/lower-menu/options
  suites.
- Golden-frame comparisons: render a fixed scene through the old and new paths
  and compare client pixels. `kohjoh`'s 801x960 dual-screen comparison is the
  model.
- Differential fuzzing for cache invalidation: random writes to VRAM, OAM,
  palettes, and tilemaps; compare the fast change check against the full hash.
  Any disagreement is a failure, not a tolerance.
- Replay: `gx3d_replay FILE` already exists for captured G3 streams. Use it to
  compare CPU and retained paths on the same input.
- GPU stand-in: `port_gx3d_gpusim.c` already draws a scene the way
  `port_gx3d_pica.c` asks the PICA to (same batches, tiled textures, combiner,
  alpha, blend, and depth rules) on a PC. A retained or lit path that is
  mirrored there can be compared against the CPU path in the host suite,
  without hardware. It does not model PICA rasterization exactly, so edge
  pixels need a stated tolerance; held-frame equality stays a hardware check.
- Soak: 30+ minute runs with scene transitions, battles, menus, and saves.

### 5.2 Performance

- `[perf]` logs from our own New 3DS and Old 3DS runs: drawer time, handover
  time, geometry time, mixer time, skip counts, and tail frame times. The New
  3DS runs must confirm the 804 MHz speed-up was accepted (the `[perf] New 3DS
  speed-up` line); a log without it is a compatibility-mode log.
- Azahar instruction counts for A/B builds on the same scene and input script.
  These are CPU comparisons, not absolute predictions, and say nothing about
  GPU cost.
- GPU work counts for any change that moves work to the PICA: vertices,
  shader instructions per vertex, triangles, draws, and texture upload bytes
  per frame.
- Histograms, not averages: p50, p95, p99, missed V-blanks, and the number of
  scenes left out.
- A fixed scene corpus and a fixed input script, so before/after numbers are
  comparable.

### 5.3 What we cannot claim

- We cannot claim an Old 3DS frame rate from Azahar ticks.
- We cannot claim a New 3DS win without a New 3DS log or a deterministic
  counter that the project already trusts.
- We cannot ask the maintainer to validate performance on hardware they do not
  target. (They do test performance-sensitive work on a New 3DS themselves:
  `AI_DISCLOSURE.md`. The evidence pack should make that check quick and
  reproducible, not replace it.)
- We cannot treat "it looks faster" as a gate.

## 6. Measurement protocol

Every performance PR uses the same protocol:

0. **Baseline on current `main`.** Before the first PR, and again before each
   PR is opened, run the corpus on current upstream `main` on a New 3DS (speed-up
   on), an Old 3DS with `remaster off` (today's O3DS experience), and an Old
   3DS with `remaster on` (today's O3DS remaster, which is not blocked, only
   unsupported). These three logs replace every stale `[PP]` number and give
   the O3DS tier the baseline it currently lacks.
1. **Scene corpus.** At minimum: title, Twinleaf, Sandgem, Jubilife, Route 202,
   Route 203, Route 206, Eterna, Hearthome, Solaceon, Veilstone, Pastoria, the
   Distortion World, a singles battle, a doubles battle, a contest, the summary
   screen, the PC, and the lower-screen menu.
2. **Input script.** Fixed movement and menu path per scene; no random walks.
   The same script runs on both builds.
3. **Warm-up.** 10 seconds discarded, then 60 seconds captured, three runs.
4. **Counter set.** Frame time p50/p95/p99, drawer time by part (change check,
   draw, handover), geometry time by part (decode, transform, light, clip,
   submit), mixer ticks, skipped presents, missed deadlines.
5. **Noise floor.** A change is kept only if its median improves by more than
   the run-to-run spread of the measurement, and its p95 does not regress.
6. **Reporting.** The PR includes the raw log lines, the scene, the build, and
   the hardware. No cherry-picked single frame.

If a change cannot clear the noise floor, it is reverted. Elegance is not a
gate.

## 7. Gaps and open questions

- **No `pokeplatinum-3ds` Old 3DS baseline has been collected yet.** One is
  cheap: the port boots on Old 3DS today (step 0 above). Until then, any O3DS
  number in these documents is a `[TARGET]` or a `[KJ]` measurement.
- **The N3DS linear-memory floor is tight.** Before the place-name sign's
  textures (2026-11-04), New 3DS logs had about 4.2 MB (4253 KB) of linear
  memory left after the title screen and 2.5 MB (2571 KB) at the fewest
  through a run; after them, 4069 KB. Below `COMPOSE_TEXTURE_ROOM` (now 3 MB)
  the compositor already takes its smaller display. `[PP]` A 1024x1024
  RGBA5551 atlas is 2 MB. Atlas sizing, eviction, and residency are a
  first-class design constraint.
- **The 64 MB memory mode is a New 3DS case too.** Issue #188: a New 2DS XL
  launched in the 64 MB mode had about 16.5 MB of linear heap and fell back to
  the classic display. `[PP]` Memory the shared backends save helps New 3DS
  users in that mode, which is an N3DS merge case for memory work that does not
  depend on the O3DS tier.
- **VRAM is 6 MB on both models.** `[SPEC]`, coffeepot `ctr/hardware/gpu.md`.
  (An earlier draft said the New 3DS has more; its extra memory is FCRAM, not
  VRAM.) The backends must budget VRAM explicitly on every model.
- **Upstream moves fast.** About 200 PRs in a month, nearly all by the owner,
  who rebases outside work onto `main` themself before a release (PR #219).
  Long-lived XL branches will rot; small PRs land.
- **`kohjoh`'s lighting shader may not fit every `pokeplatinum` material.**
  The census is the gate.
- **Azahar's GPU timing is not representative.** Use it for CPU instruction
  deltas and correctness, not for GPU cost.
- **Line endings.** The local Windows checkout has `core.autocrlf=true`, so
  426 text files are CRLF in the working tree and LF in the index. That is a
  property of this checkout, not of the repository; `git status` is clean.
  Do not commit from a tool that rewrites them, and check `git diff --stat`
  for whole-file churn before pushing.
