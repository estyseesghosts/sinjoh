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
prediction of Old 3DS cycles.

## 1. What the New 3DS pays today

`pokeplatinum-3ds` targets the New 3DS family. The costs below are therefore
already visible on the hardware the maintainer supports. The Old 3DS is where
they become fatal, but it is not where they start.

### 1.1 The frame

- The game logic runs at 30 Hz; the remaster presents up to 60 pictures a
  second with interpolation. A 30 Hz game frame is 33.3 ms; a 60 Hz present
  interval is 16.7 ms.
- On a New 3DS, engine A's 2D drawer and the geometry thread share core 2.
  Engine B's drawer runs on core 1's share (or on core 0 when the geometry
  took core 1); the game and the display thread run on core 0. `[PP]`
- The geometry thread runs first on core 2 when both are ready. `[PP]`
- A 2D picture that is handed over is upscaled into the compositor's textures.
  That handover is part of the drawer's measured time. `[PP]`

The important consequence: **2D drawer time and geometry time are not separate
budgets.** They compete for the same core, and the game waits behind both.

### 1.2 The 2D change check

The software 2D renderer decides whether an engine's picture changed before it
redraws it. Since 2026-10-30 it hashes only the VRAM the screen shows, but that
is still:

- every map of every enabled BG,
- the tiles those maps use and their palettes,
- the OBJ VRAM while an OBJ is shown,
- the VRAM display's bank.

For engine A that is **864 KB read and hashed per frame when nothing changed**.
`[PP]`

The project's own measurement:

> "All of it (864 KB for engine A) was read each frame nothing changed, about
> 15 ms of every 33 on the 3D's core, half of engine A's drawer's time."
> `[PP]`, `docs/REMASTER.md`

The 15 ms is the unchanged-frame check's share of the drawer's wall time on
core 2, where it competes with the geometry thread. The 16.2 ms in section 1.3
is a picture that is actually drawn; the two are different frames, not two
parts of one budget.

That is roughly a whole 60 Hz present interval spent proving that nothing
needs to be drawn. In towns, with nothing changed, the upper screen's 2D was
still drawn again **5-11 times a second** because the check could not prove it
was unchanged. `[PP]`

The check has escape hatches that make it more expensive, not less:

- an H-blank effect or a bitmap BG forces the full read;
- a changed palette invalidates every dependent tile;
- OAM changes are hashed entry by entry in the naive case.

### 1.3 The 2D drawer

When a picture is drawn, the drawer costs about **16.2 ms**, of which **4.6 ms**
is handing the picture over to the compositor's textures. `[PP]`, from the
`[perf] game` line:

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

- **20-30 ms a scene** in the field. `[PP]`
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

### 1.5 Audio

The mixer already mixes in blocks (`BLOCK = 128` in `port_sound_chip.c`), so
the missing win is narrower than "rewrite the mixer". `[PP]`

What is missing is a **decoded-ADPCM cache**. A looping instrument re-decodes
the same nibbles every time its decoder state is clean. `kohjoh` measured the
cost of that decode and the win from caching it (section 2.3).

### 1.6 Scheduling

The current topology is sensible for a New 3DS: geometry and engine A's drawer
on core 2, engine B on core 1's share, game and display on core 0. But the
priorities and the present-skip
rules are tuned around the current costs. Once the change check and the
geometry are cheaper, the old pacing rules will be wrong: they can skip a
present that is now affordable, or starve a drawer that is now the critical
path. This is why `perf/lowend-schedule` exists, and why it comes after the
costs are removed rather than before.

## 2. What kohjoh measured

`kohjoh` is an HGSS port to the Old 3DS. It solved the same class of problems:
DS-era software rendering on PICA200 hardware, with a CPU that is slower than
the New 3DS's and a GPU that is roughly half as fast. Its techniques transfer;
its game code does not.

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

The display-list cache replays **74% of FIFO words**. On Azahar, the hotpaths
A/B (display-list cache, state-only replay, compact hot loops) cut game logic
from **16.648 ms to 15.430 ms (-7.3%)**. `[KJ]`,
`docs/worklog/2026-11-14-hotpaths.md`. The worklog explicitly warns that the
replay-rate increase includes state-only streams and must not be presented as a
retained geometry hit-rate gain.

The lighting shader reproduces the DS's fixed-point lighting semantics in
PICA vertex code: **409 instructions, 94 float registers including constants**.
On held frames it is pixel-exact against the CPU reference: Ho-Oh frames
2301/2501 match across the complete dual-screen client crop (801x960 screenshot
pixels), and the Route 34 field matches with zero differing client pixels.
`[KJ]`, `docs/worklog/2026-11-15-lit-plans.md`

This is the strongest evidence in the whole plan: a DS-exact lighting model is
achievable on PICA without dropping geometry or accepting visible drift. It
does not prove the same shader compiles and fits `pokeplatinum-3ds`'s material
set, which is why `perf/g3d-census` comes first.

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

- Goldenrod logic: about **37 ms** median; active play about **43 ms** median.
  `[KJ]`, O3DS log.
- Route 34 is near 30 FPS; Goldenrod is unplayable. `[KJ]`, O3DS log.

This is exactly why the O3DS tier is a stretch goal with its own gates, not a
promise inherited from `kohjoh`. A technique that works does not automatically
produce a playable frame on weaker hardware.

## 3. Transfer matrix

| kohjoh technique | `pokeplatinum-3ds` cost addressed | Expected New 3DS effect | Confidence | First proof |
| --- | --- | --- | --- | --- |
| Dirty-generation 2D change check | 864 KB full-VRAM hash, ~15 ms of a 33 ms frame | Returns most of the unchanged-frame drawer time; fewer needless redraws | High | `perf/render2d-change`: differential fuzz + drawer timing |
| Retained text-BG layers | Re-rasterizing unchanged BGs every frame | Lower drawer time in towns, menus, battles | High | `perf/g2d-atlas-text`: golden frames + timing |
| Tile atlas (512-1024) + palette dependencies | Software tile decode and CPU-to-GPU copy | Fewer bytes moved, fewer draws; foundation for all GPU 2D | High for text, medium for affine/extended | `perf/g2d-atlas-text`, `perf/g2d-layers` |
| Stencil windows + blend/brightness passes | Software windows, blending, brightness, H-blank spans | Full GPU 2D coverage without per-span CPU work | Medium | `perf/g2d-effects`: effect corpus |
| Retained object-space G3 + 16-entry matrix palette | 20-30 ms CPU transform/clip per scene | Target 8-12 ms geometry per scene `[TARGET]` | Medium-high | `perf/g3d-retained`: replay A/B + timing |
| PICA vertex lighting | Per-vertex CPU lighting | More geometry time returned; title and battle scenes | Medium | `perf/g3d-lighting`: lit-frame pixel compare |
| Decoded-ADPCM cache | Per-sample decode of looping instruments | Lower mixer CPU; core time back to the game | High | `perf/audio-adpcm`: bit-exact output + tick count |
| Display-list cache / state replay | Repeated G3 decode and submission | Lower logic time in worst-case scenes | Medium | `perf/g3d-fifo` (optional) |
| Present pacing and priorities | Over-eager skip or drawer starvation | More stable frame times once costs drop | Medium | `perf/lowend-schedule`: p95/p99 histograms |

The matrix is ordered by confidence, not by PR order. PR order is chosen so
each step makes the next one measurable.

## 4. What does not transfer

- **HGSS game logic, maps, scripts, and assets.** None of it is relevant, and
  none of it may be copied. `kohjoh` is GPL-3.0, like `pokeplatinum-3ds`, but
  game content is never part of the adaptation.
- **`kohjoh`'s citro2d compositor.** `pokeplatinum-3ds` has its own compositor
  and its own PICA command submission. The 2D *technique* transfers; the API
  calls do not.
- **Old 3DS cycle numbers.** `kohjoh`'s Azahar ticks are instruction counts on
  an emulator. They rank changes; they do not predict milliseconds.
- **The assumption that PICA lighting fits every material.** `kohjoh`'s shader
  is 409 instructions and 94 registers. `pokeplatinum-3ds` has more material
  modes, N3DS-only effects, and a different texture pipeline. The census
  decides what fits.
- **60 FPS interpolation, stereo 3D, sun shadows, edge marking, xBRZ, 2x2
  supersampling, and full WideArt.** These are New 3DS features. They stay on
  the existing path and are never folded into the shared low-end backend.
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
- Soak: 30+ minute runs with scene transitions, battles, menus, and saves.

### 5.2 Performance

- `[perf]` logs from our own New 3DS and Old 3DS runs: drawer time, handover
  time, geometry time, mixer time, skip counts, and tail frame times.
- Azahar instruction counts for A/B builds on the same scene and input script.
  These are comparisons, not absolute predictions.
- Histograms, not averages: p50, p95, p99, missed V-blanks, and the number of
  scenes left out.
- A fixed scene corpus and a fixed input script, so before/after numbers are
  comparable.

### 5.3 What we cannot claim

- We cannot claim an Old 3DS frame rate from Azahar ticks.
- We cannot claim a New 3DS win without a New 3DS log or a deterministic
  counter that the project already trusts.
- We cannot ask the maintainer to validate performance on hardware they do not
  target.
- We cannot treat "it looks faster" as a gate.

## 6. Measurement protocol

Every performance PR uses the same protocol:

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

- **No `pokeplatinum-3ds` Old 3DS baseline exists.** Any O3DS number in these
  documents is a `[TARGET]` or a `[KJ]` measurement, never a baseline.
- **The N3DS linear-memory floor is tight.** The remaster reports about 4.0 MB
  of linear memory left after the title screen and 2.5 MB at its lowest through
  a run. `[PP]` A 1024x1024 RGBA5551 atlas is 2 MB. Atlas sizing, eviction, and
  residency are therefore a first-class design constraint, not an
  afterthought.
- **VRAM differs by model.** Old 3DS has 6 MiB total; New 3DS has more.
  `[SPEC]`/`[KJ]` The low-end backend must budget VRAM explicitly and must not
  rely on New 3DS headroom.
- **`kohjoh`'s lighting shader may not fit every `pokeplatinum` material.**
  The census is the gate.
- **Azahar's GPU timing is not representative.** Use it for CPU instruction
  deltas and correctness, not for GPU cost.
- **The 426 line-ending-only files in `pokeplatinum-3ds` are not work.** Never
  include them in a PR diff.
