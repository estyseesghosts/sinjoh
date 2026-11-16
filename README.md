# Sinjoh

Performance work for `pokeplatinum-3ds`: **shared New 3DS wins first, an experimental Old 3DS tier as the stretch goal.**

## The reframing

This is not an "O3DS support" proposal, and it does not ask the upstream maintainer to own an Old 3DS test lab.

The upstream project is built for the New 3DS. It already boots on an Old 3DS, but only with the classic display (`remaster off` is the Old 3DS default), and the remastered display is advertised for New 3DS only. Its maintainer has no reason to accept a second hardware support burden. So the plan is framed around costs that are visible on the New 3DS:

- CPU-transformed, CPU-lighted 3D geometry, including the CPU-built 60 FPS in-between scenes,
- software-rasterized 2D and its handover to the GPU, on the same core as the geometry,
- per-sample ADPCM decoding in the software mixer, on the same core as the game,
- scheduling and present-skip rules tuned around those costs.

Those costs are worst on an Old 3DS, but they are real on a New 3DS too. Removing them gives the New 3DS more 60 FPS headroom, fewer dropped scenes, and shorter worst frames, and helps New 3DS users stuck in the 64 MB memory mode (issue #188). The Old 3DS is the stress test that tells us whether the work is genuinely efficient, not the justification for asking upstream to change its support policy.

**Every core PR in this series must be defensible on New 3DS terms alone.** The one exception is the final `perf/o3ds-tier` profile, which is additive, opt-in, and can be dropped without losing the New 3DS improvements.

## What this is

- A sequence of focused, reviewable pull requests against `GabeSud0/pokeplatinum-3ds`.
- An adaptation of specific, measured techniques from `kohjoh`, the HGSS O3DS port: a GPU tile atlas and retained 2D layers, retained object-space 3D geometry with clip-volume culling, CPU-baked lighting for stable lists with PICA lighting for the rest, a decoded-ADPCM cache, and conservative frame pacing.
- A plan for proving each change with deterministic tests and the project's existing `[perf]` lines, and for making the maintainer's own New 3DS check quick.
- An eventual `tier o3ds` profile that makes the remaster worth turning on there: both screens filled, native-resolution 3D, widescreen layout, the bottom-screen menu, crisp 2D, stable 30 FPS, working audio and saves.

## What this is not

- Not a fork, a rewrite, or a replacement of the New 3DS renderer.
- Not a request to make Old 3DS the default target or a supported platform in upstream's README.
- Not a port of every kohjoh feature. The N3DS-only effects stay N3DS-only.
- Not a promise that Old 3DS will run every scene at 30 FPS. The tier ships only if it passes its own gates, and stays experimental until it does.
- Not a reason to commit game content, captured assets, or benchmark saves.

## The bet

`pokeplatinum-3ds` currently pays for two expensive compatibility layers:

1. **3D is transformed, lit, and clipped on the CPU**, then handed to the GPU as screen-space triangles. Geometry costs about 20-30 ms a scene in the field, plus 3-9 ms for the 60 FPS in-between scene, on the core engine A's 2D drawer also uses. `[PP]`
2. **2D is drawn in software**, then upscaled and handed to the GPU as textures. Drawing a picture costs about 16.2 ms, 4.6 ms of it handing the picture over. `[PP]` (The once-dominant 864 KB / 15 ms change check was fixed upstream on 2026-10-30, `313ac80`; what remains of it is measured in step 0, not assumed.)

kohjoh shows that both can be moved off the CPU on O3DS-class hardware: a tile atlas for 2D, retained object-space meshes with a 16-entry matrix palette and clip-volume culling, and lighting that matches the DS's fixed-point arithmetic on held frames. It also shows the trap: **the GPU is the same 268 MHz PICA200 on both models, and Azahar does not charge for vertex work.** Lighting every map vertex on the PICA took kohjoh's Old 3DS frames from about 36 to 57 ms while Azahar showed 30 FPS; baking stable lighting on the CPU fixed it. So the plan retains and caches on the CPU first, moves to the GPU only what pays, and counts GPU work.

The plan adopts those techniques behind flags, measures them on New 3DS first, and only then assembles the O3DS tier.

## Guiding principles

1. **New 3DS benefit is the merge case.** If a PR only helps O3DS, it is the final tier or optional, and it goes last.
2. **Measure current `main` first.** The `[PP]` numbers are weeks old and upstream moves fast; one of them was fixed before this plan was written. Step 0 replaces them.
3. **Default behavior stays safe.** New backends are opt-in `remaster.txt` lines until they are pixel-correct and measurably faster. The old path remains selectable.
4. **The default New 3DS configuration is the one that counts.** `fps60`, `smooth3d`, and stereo are on by default; a backend that only works with them off has no merge case.
5. **GPU time is not free.** Moving work from an 804 MHz CPU to an unchanged 268 MHz GPU needs GPU work counts, not Azahar times.
6. **One cost per PR.** Each PR names the cost it removes, the test that proves correctness, and the counter that proves the gain.
7. **No maintainer benchmarks, but an easy maintainer check.** We provide deterministic tests, Azahar instruction counts, and `[perf]` logs; they test in Azahar and on a New 3DS anyway, so we make that a one-scene check. O3DS hardware validation is our job.
8. **No support burden by surprise.** The O3DS tier is documented as experimental, defaults off, and never changes New 3DS defaults.
9. **Measure, then keep or revert.** A change that does not beat noise on the target scenes is reverted, even if it looks elegant.

## PR map

Step 0, before any PR: a baseline of current upstream `main` on a New 3DS, an Old 3DS with `remaster off`, and an Old 3DS with `remaster on`.

Core sequence (11 PRs):

| # | Branch | What it removes | Primary benefit | Size | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | `perf/telemetry` | Averages without tails; no mixer timing | Makes every later claim measurable | S | - |
| 2 | `perf/render2d-change` | The residual shown-VRAM hash and H-blank/bitmap full reads | **Conditional:** only if step 0 shows it still matters | M | 1, step 0 |
| 3 | `perf/audio-adpcm` | Repeated ADPCM decode of looping instruments | Core 0 time back to the game; **first merge candidate** | M | 1 |
| 4 | `perf/g2d-atlas-text` | Software text-BG rasterization and handover | Cheaper changed 2D frames; foundation for GPU 2D | L | 1 |
| 5 | `perf/g2d-layers` | Software affine/extended BGs and sprites | Cheaper menus, battles, and effects | XL (split) | 4 |
| 6 | `perf/g2d-effects` | Software windows, blending, brightness, H-blank spans | Full GPU 2D coverage without fallback | XL | 5 |
| 7 | `perf/g3d-census` | Guesswork about which G3 lists can be retained, baked, or interpolated | A go/no-go gate for retained 3D | M | 1 |
| 8 | `perf/g3d-retained` | Per-vertex CPU transform, clipping, and in-between re-clipping of static meshes | Geometry from 20-30 ms toward 8-12 ms a scene with `fps60` on `[TARGET]` | XL | 7 |
| 9 | `perf/g3d-lighting` | Per-vertex CPU lighting | Baked colours for stable lists; PICA lighting for the rest | XL (split) | 8 |
| 10 | `perf/lowend-schedule` | Pacing and priorities tuned for the old costs | More stable 60 FPS on N3DS; tunes the existing O3DS topology | M | 3-6, 8-9 |
| 11 | `perf/o3ds-tier` | The gap between "fast enough" and "configured" | Opt-in O3DS profile; N3DS defaults untouched | S | all |

Optional, after the core track:

| # | Branch | What it removes | Why optional | Size |
| --- | --- | --- | --- | --- |
| 12 | `perf/g3d-fifo` | Repeated G3 command decode and submission | Useful for worst-case logic; may be superseded by retained geometry | M |
| 13 | `perf/game-hotpaths` | Telemetry-selected game-logic hot paths | Small, broad game-logic win; not a renderer change | S |

The detailed briefs are in [`PR_SERIES.md`](PR_SERIES.md).

## How to read the rest

- [`EVIDENCE.md`](EVIDENCE.md) - what the New 3DS pays today, what kohjoh measured (including what went wrong), and which techniques transfer.
- [`PR_SERIES.md`](PR_SERIES.md) - step 0 and the ordered PR briefs: scope, integration points, tests, gates, risks, rollback.
- [`O3DS_TIER.md`](O3DS_TIER.md) - the eventual Old 3DS target, hardware budget, scene corpus, and internal acceptance gates. This is a stretch goal, not an upstream contract.
- [`UPSTREAM_NOTES.md`](UPSTREAM_NOTES.md) - how to make the work reviewable: the maintainer's actual process, PR shape, evidence pack, CI, provenance, AI disclosure.

## Status

Planning only. No code has been written. The numbers in these documents are either quoted from the two repositories' own documentation or explicitly labelled as planning targets (`[TARGET]`); the full source-tag scheme is in [`EVIDENCE.md`](EVIDENCE.md). The first step is the step 0 baseline; the first PR is `perf/telemetry`; the first merge candidate is `perf/audio-adpcm`. Before any code, the opening issue asks the maintainer whether AI-assisted outside PRs are welcome at all (`AI_DISCLOSURE.md` says "all new features are created by the developer").

### Revision of 2026-11-15

Checked against `pokeplatinum-3ds` `c84883d`, `kohjoh` `fb0440a`, and the coffeepot hardware pages. Changed:

- **The flagship cost was already fixed.** The 864 KB / ~15 ms change check describes the code before `313ac80` (2026-10-30). PR 2 is now conditional on a fresh measurement, and the first merge candidate is the ADPCM cache.
- **The GPU and VRAM are the same on both models** (268 MHz, 6 MB). The old hardware table said 133 MHz and 10 MB. GPU-side PRs now report GPU work counts and gate on the New 3DS display rate.
- **kohjoh's later hardware result** (PICA lighting on every vertex: 36 → 57 ms on O3DS, invisible in Azahar; fixed by CPU baking and clip-volume culling) now shapes PRs 8 and 9.
- **`fps60` is on by default and builds in-between scenes from CPU clip-space polygons.** PR 8 must interpolate retained lists' matrices, or it never runs in the default New 3DS configuration.
- **The Old 3DS already boots, has a 2-core topology, and accepts `remaster on`.** The tier, PR 10, and PR 11 build on that instead of inventing it, and step 0 collects the O3DS baseline the plan said did not exist.
- **Integration details:** switches are `remaster.txt` lines (the 3DS build reads no environment variables); `gpuBgs`/`gpuObjs` are per-frame split fields, not user-facing levels; the existing sprite atlas, `port_gx3d_gpusim.c`, the light cache, and the `[perf]`/`[stall]` lines are reused; the mixer has no timing today; the 2D filter modes must be reproduced by the atlas path.
- **Process:** the maintainer does test performance work on a New 3DS; outside PRs are rebased by them; the "426 line-ending files" are a property of this Windows checkout (`core.autocrlf=true`), not of the repository.
