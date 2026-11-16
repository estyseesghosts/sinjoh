# Sinjoh

Performance work for `pokeplatinum-3ds`: **shared New 3DS wins first, an experimental Old 3DS tier as the stretch goal.**

## The reframing

This is not an "O3DS support" proposal, and it does not ask the upstream maintainer to own an Old 3DS test lab.

The upstream project targets the New 3DS family. Its maintainer has no reason to accept a second hardware support burden or to run benchmarks on a console they do not target. So the plan is framed around costs that are already visible on the New 3DS:

- the software 2D renderer's full-VRAM change check,
- CPU-transformed and CPU-lighted 3D geometry,
- per-sample ADPCM decoding in the software mixer,
- command submission and thread scheduling that leave performance on the table.

Those costs are worst on an Old 3DS, but they are real on a New 3DS too. Removing them gives the New 3DS more 60 FPS headroom, fewer dropped scenes, and shorter worst frames. The Old 3DS is the stress test that tells us whether the work is genuinely efficient, not the justification for asking upstream to change its support policy.

**Every core PR in this series must be defensible on New 3DS terms alone.** The one exception is the final `perf/o3ds-tier` profile, which is additive, opt-in, and can be dropped without losing the New 3DS improvements.

## What this is

- A sequence of focused, reviewable pull requests against `GabeSud0/pokeplatinum-3ds`.
- An adaptation of specific, measured techniques from `kohjoh`, the HGSS O3DS port: retained 2D layers, a GPU tile atlas, retained object-space 3D geometry, PICA vertex lighting, a decoded-ADPCM cache, and conservative frame pacing.
- A plan for proving each change with deterministic tests and existing performance counters, without asking the maintainer to benchmark hardware.
- An eventual `tier o3ds` profile that turns the remaster on with the effects that fit: both screens filled, native-resolution 3D, widescreen layout, the bottom-screen menu, crisp 2D, stable 30 FPS, working audio and saves.

## What this is not

- Not a fork, a rewrite, or a replacement of the New 3DS renderer.
- Not a request to make Old 3DS the default target or a supported platform in upstream's README.
- Not a port of every kohjoh feature. The N3DS-only effects stay N3DS-only.
- Not a promise that Old 3DS will run every scene at 30 FPS. The tier ships only if it passes its own gates, and stays experimental until it does.
- Not a reason to commit game content, captured assets, or benchmark saves.

## The bet

`pokeplatinum-3ds` currently pays for two expensive compatibility layers:

1. **2D is drawn in software**, then handed to the GPU as textures. A change check reads and hashes up to 864 KB of VRAM for engine A: about 15 ms of a 33 ms frame when nothing changed. Drawing a picture costs about 16.2 ms, 4.6 ms of it handing the picture over.
2. **3D is transformed, lit, and clipped on the CPU**, then handed to the GPU as screen-space triangles. Geometry costs 20-30 ms a scene in the field, and the upper screen's drawer can take 55-60 ms a picture when the geometry is busy.

kohjoh shows that both costs can be moved to the PICA200 on O3DS-class hardware: a 1024x1024 tile atlas for 2D (sized down to the local memory budget), retained object-space meshes with a 16-entry matrix palette, and a PICA lighting shader that matches the DS's fixed-point lighting on held frames. It also shows the supporting wins: a decoded-ADPCM cache, compact hot loops, and present-skip logic that keeps the screen fed.

The plan adopts those techniques behind flags, measures them on New 3DS/Azahar first, and only then assembles the O3DS tier.

## Guiding principles

1. **New 3DS benefit is the merge case.** If a PR only helps O3DS, it is the final tier or optional, and it goes last.
2. **Default behavior stays safe.** New backends are opt-in until they are pixel-correct and measurably faster. The old path remains selectable for N3DS-only features.
3. **One cost per PR.** Each PR names the cost it removes, the test that proves correctness, and the counter that proves the gain.
4. **No maintainer benchmarks.** We provide deterministic tests, Azahar instruction counts, and `[perf]` logs. O3DS hardware validation is our job.
5. **No support burden by surprise.** The O3DS tier is documented as experimental, defaults off, and never changes New 3DS defaults.
6. **Measure, then keep or revert.** A change that does not beat noise on the target scenes is reverted, even if it looks elegant.

## PR map

Core sequence (11 PRs):

| # | Branch | What it removes | Primary benefit | Size | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | `perf/telemetry` | Blind spots: averages instead of tail frame times | Makes every later claim measurable | S | - |
| 2 | `perf/render2d-change` | The 864 KB full-VRAM 2D change scan | **Largest N3DS win**: about 15 ms of unchanged-frame drawer time | M | 1 |
| 3 | `perf/audio-adpcm` | Repeated ADPCM decode of looping instruments | Lower mixer CPU on N3DS; core time back | M | 1 |
| 4 | `perf/g2d-atlas-text` | Software text-BG rasterization | Cheaper changed 2D frames; foundation for GPU 2D | L | 1, 2 |
| 5 | `perf/g2d-layers` | Software affine/extended BGs and sprites | Cheaper menus, battles, and effects | XL | 4 |
| 6 | `perf/g2d-effects` | Software windows, blending, brightness, H-blank spans | Full GPU 2D coverage without fallback | XL | 5 |
| 7 | `perf/g3d-census` | Guesswork about which G3 lists can be retained | A go/no-go gate for retained 3D | M | 1 |
| 8 | `perf/g3d-retained` | Per-vertex CPU transform and clipping of static meshes | Geometry from 20-30 ms toward 8-12 ms a scene `[TARGET]` | XL | 7 |
| 9 | `perf/g3d-lighting` | Per-vertex CPU lighting | More geometry time back; title and battle scenes | XL | 8 |
| 10 | `perf/lowend-schedule` | Thread contention and over-eager present skipping | More stable 60 FPS on N3DS; 2-core viability on O3DS | M | 2-6, 8-9 |
| 11 | `perf/o3ds-tier` | The gap between "fast enough" and "configured" | Opt-in O3DS profile; N3DS defaults untouched | S | all |

Optional, after the core track:

| # | Branch | What it removes | Why optional | Size |
| --- | --- | --- | --- | --- |
| 12 | `perf/g3d-fifo` | Repeated G3 command decode and submission | Useful for worst-case logic; may be superseded by retained geometry | M |
| 13 | `perf/game-hotpaths` | Telemetry-selected game-logic hot paths; per-word GX submission | Small, broad game-logic win; not a renderer change | S |

The detailed briefs are in [`PR_SERIES.md`](PR_SERIES.md).

## How to read the rest

- [`EVIDENCE.md`](EVIDENCE.md) - what the New 3DS pays today, what kohjoh measured, and which techniques transfer.
- [`PR_SERIES.md`](PR_SERIES.md) - the ordered PR briefs: scope, integration points, tests, gates, risks, rollback.
- [`O3DS_TIER.md`](O3DS_TIER.md) - the eventual Old 3DS target, hardware budget, scene corpus, and internal acceptance gates. This is a stretch goal, not an upstream contract.
- [`UPSTREAM_NOTES.md`](UPSTREAM_NOTES.md) - how to make the work reviewable by a maintainer who does not benchmark hardware: PR shape, evidence pack, CI, provenance, AI disclosure.

## Status

Planning only. No code has been written. The numbers in these documents are either quoted from the two repositories' own documentation or explicitly labelled as planning targets (`[TARGET]`); the full source-tag scheme is in [`EVIDENCE.md`](EVIDENCE.md). The first implementation step is `perf/telemetry`; the first merge candidate is `perf/render2d-change`, because it is the clearest New 3DS win and the lowest-risk proof that the approach is worth continuing.
