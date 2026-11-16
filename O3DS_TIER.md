# Old 3DS tier

> Stretch goal, not an upstream contract. This document describes the eventual
> opt-in profile and the internal gates it must pass. It does not ask the
> maintainer to support Old 3DS, and it does not change New 3DS defaults.

## 1. Status

The core PR series exists to remove costs that are visible on the New 3DS.
The Old 3DS tier is what those costs look like when the hardware is slower and
the memory is tighter. It is assembled last, from backends that already work on
New 3DS terms.

The tier is:

- **additive:** it selects the shared backends and turns off effects that do
  not fit;
- **opt-in:** it is off by default on every model, including Old 3DS;
- **experimental:** it ships only if it passes the internal gates below;
- **droppable:** if it fails, the New 3DS PRs still stand.

It is not:

- a new renderer;
- a promise that every scene reaches 30 FPS;
- a request for the maintainer to own Old 3DS testing;
- a change to the project's supported-platform statement.

## 2. Target experience

The tier aims to deliver as much of the remastered experience as the hardware
can hold:

- [ ] Both screens filled, not the classic centered DS screens.
- [ ] Native-resolution 3D on the upper screen, without stereo.
- [ ] Widescreen layout where the scene supports it.
- [ ] The bottom-screen menu.
- [ ] Crisp 2D: the GPU 2D path, not a blurry upscale.
- [ ] A stable 30 FPS target in the field and in battles.
- [ ] Audio intact: music, effects, and sequencing.
- [ ] Saves intact: read, write, reboot, load.

"Stable 30 FPS" means the game logic still runs at 30 Hz and the picture keeps
up. It does not mean 60 FPS interpolation, which is an N3DS-only feature.

"Widescreen" here means the existing wide-layout path, with the 3D view widened
to the screen's aspect and the 2D layers placed for the wider canvas. It does
not mean the memory-heavy full WideArt pack; the tier uses the reduced layout
that fits. "Native-resolution 3D" means the upper screen's 400x240, not the
DS's 256x192 upscaled.

## 3. Exclusions

The tier deliberately excludes:

| Feature | Why it is out |
| --- | --- |
| 60 FPS interpolation | Doubles the present work and the vertex/CPU budget; the first goal is a stable 30. |
| Stereo 3D | Doubles the 3D render and the framebuffer; not affordable on O3DS at this scale. |
| Sun shadows | Extra passes and vertex work; a large cost for a subtle effect. |
| Edge marking | Extra passes and buffers; the DS look survives without it on the small screen. |
| xBRZ | CPU-heavy upscaling; the GPU 2D path makes it unnecessary for crispness. |
| 2x2 supersampling | Four times the pixels; the first goal is native resolution. |
| Full WideArt | Memory and bandwidth; the tier may use a reduced wide layout where the scene supports it. |
| High-resolution 2D textures | The atlas is sized to the memory budget, not to the N3DS's. |

These are not permanent bans. They are the first tier's scope. A later tier
can add one back if it passes its own gate.

## 4. Hardware budget

Public specifications, not measurements of this port `[SPEC]`:

| | Old 3DS | New 3DS |
| --- | --- | --- |
| CPU | 2 x ARM11 MPCore, 268 MHz | 4 x ARM11 MPCore, 804 MHz |
| GPU | PICA200, 133 MHz | PICA200, 268 MHz |
| System RAM | 128 MB | 256 MB |
| VRAM | 6 MiB | 10 MiB |
| Upper screen | 400x240 (800x240 for stereo) | 400x240 (800x240 for stereo) |
| Lower screen | 320x240 | 320x240 |

The application does not get all of the CPU or all of the RAM. Homebrew
commonly runs in a 64 MiB memory mode; `pokeplatinum-3ds` already has a
smaller-display path for that mode. `[PP]` The conservative planning assumption
for the tier is **64 MiB of application memory and 6 MiB of VRAM**, not the
full system RAM.

Frame budget at 30 FPS: **33.3 ms**. At 268 MHz, that is about 8.9 million
cycles per core, before the OS and the display thread take their share. `[SPEC]`
The tier targets two usable cores, not four.

## 5. Memory ledger

This is a planning ledger, not an allocation plan. Every row must be replaced
by a measured value from `NitroPort_PicaLogMemory` and the `[perf]` logs before
the tier can ship.

| Item | Planning budget | Source | Gate |
| --- | --- | --- | --- |
| Game code, data, and heap | Existing 64 MiB-mode footprint | `[PP]` | Must boot and save |
| Compositor textures (both screens) | Existing small-display path | `[PP]` | Both screens filled, no black screen |
| 2D tile atlas | 512 KB at 512x512 RGBA5551; 2 MB at 1024x1024 | `[TARGET]` | Fits with eviction; no fallback storm |
| 2D layer/vertex buffers | 256-512 KB | `[TARGET]` | Bounded per frame |
| Retained 3D geometry | 1-4 MB, evictable | `[TARGET]` | Scene falls back rather than fails |
| 3D texture cache | Existing budget, reduced | `[PP]` | No thrash in the corpus |
| Decoded ADPCM cache | 64-256 KB | `[TARGET]` | No audio dropouts |
| Framebuffers and depth | Existing, no stereo | `[PP]` | Native resolution |
| Reserve and fragmentation | At least 15% of the linear heap | `[TARGET]` | Boot check passes |

Rules:

- The tier checks the budget **before** allocating the compositor. If the check
  fails, it logs the reason once and falls back to the classic display.
- A failed allocation must never leave a black screen or a half-initialized
  remaster.
- VRAM is budgeted by bank, not by summing image sizes. Targets, depth, and
  textures share the 6 MiB.
- The atlas and retained geometry are evictable. The tier must survive a full
  atlas and a full geometry cache by falling back, not by crashing.
- The 64 MiB mode is the floor. Do not let New 3DS headroom hide an O3DS
  failure.

## 6. Scene corpus

The tier is judged on a fixed corpus, not on a demo. At minimum:

**Boot and menus**
- Boot to title, load a save, open the options page.
- Lower-screen menu, party screen, summary, bag, Pokédex, PC.
- Save, reboot, load.

**Field**
- Twinleaf Town, Sandgem Town, Jubilife City.
- Route 202, Route 203, Route 206, Route 215.
- Eterna City, Hearthome City, Solaceon Town, Veilstone City.
- Pastoria City, Canalave City, Snowpoint City, Sunyshore City.
- The Distortion World.
- A rainy route and a route with a sandstorm.

**Battles and effects**
- Singles battle, doubles battle, a battle-start transition.
- A contest.
- The HM cut-in (Strength, Rock Smash, or Surf).
- A flash/fade transition and a weather transition.

Each scene runs with a fixed input script, a 10-second warm-up, and a
60-second capture. Three runs per scene. The same script and corpus are used
for every build.

## 7. Internal acceptance gates

These gates are ours. They are not a request to the maintainer.

### G0 - Boot and configuration

- The tier parses from the config and reports its profile in the log.
- With the tier off, the classic display is unchanged.
- With the tier on, both screens initialize; a forced allocation failure falls
  back cleanly.
- No crash on a cold boot, a warm boot, or a reboot after a save.

### G1 - Field traversal

- Every field scene in the corpus loads and is playable for 5 minutes.
- No black screen, no stuck transition, no missing map, no stuck 3D.
- The picture keeps up at 30 Hz; the log shows no more than 10% dropped
  presents in the first tier `[TARGET]`.

### G2 - Towns and menus

- Towns, the lower-screen menu, the party screen, the summary, the bag, the
  Pokédex, and the PC are usable.
- Text is crisp; no missing glyphs; no wrong palette.
- The menu opens and closes without a frame spike that breaks input.

### G3 - Battles

- Singles and doubles run at the target frame rate.
- Move animations, ability popups, and the battle-start transition are
  correct.
- No missing geometry, no wrong depth order, no transparent surface drawn
  opaque.

### G4 - Effects and cutscenes

- Weather, the HM cut-in, flash/fade, and the Distortion World are correct.
- The documented exclusions are the only visual differences: no shadows, no
  edge marking, no stereo, no interpolation.
- No H-blank effect is silently dropped; if a frame falls back, it is correct.

### G5 - Audio

- Music, effects, and sequencing play for 30 minutes without dropouts.
- No clicks on loop points; no drift against the game's timing.
- The decoded-ADPCM cache is bit-exact against the reference.

### G6 - Saves

- 20 save/load cycles across the corpus.
- No corruption, no truncated save, no change to the save format.
- A save written by the tier loads in the classic path and vice versa.

### G7 - Memory and soak

- A 2-hour soak with scene transitions, battles, menus, and audio.
- Memory does not grow beyond the documented reserve; no progressive
  slowdown.
- The atlas and geometry caches evict correctly under pressure.
- No crash on a forced low-memory boot.

### G8 - Visual parity

- For 2D, the tier matches the New 3DS remaster's 2D exactly on the scenes the
  atlas path covers: zero differing client pixels on held frames. A scene that
  falls back to the software path must produce the same picture as the
  remaster's software path.
- For 3D, the tier matches the same scene's geometry and layout, with the
  documented exclusions. Differences are listed and approved, not hand-waved.

## 8. Performance targets

All of these are `[TARGET]`, not measurements. They are the numbers the tier
must beat to ship, and they are deliberately conservative.

| Metric | Target | Notes |
| --- | --- | --- |
| Field frame time p50 | ≤ 33.3 ms | Stable 30 Hz |
| Field frame time p95 | ≤ 40 ms in the first tier; ≤ 33.3 ms for exit | Tighten only with evidence |
| Dropped presents | ≤ 10% first tier; ≤ 5% for exit | Counted by telemetry |
| Geometry per scene | ≤ 12 ms | After retained geometry and lighting |
| 2D drawer per picture | ≤ 8 ms | After the change check and GPU 2D |
| Mixer core share | ≤ 6% | After the ADPCM cache |
| Boot time | No more than 2 seconds over classic | The budget check is cheap |
| Memory reserve | ≥ 15% of the linear heap | No fragmentation failure |

If a target is missed, the tier does not ship. The core PRs still do.

## 9. Exit criteria

The tier exits "experimental" only when:

1. All G0-G8 gates pass on at least one original 3DS or 2DS, in at least one
   region, with the retail game data path.
2. The performance targets are met on the corpus, not on a single scene.
3. The tier is default off and documented as opt-in.
4. The N3DS build's logs and golden frames are unchanged with the tier off.
5. The PR series' core changes are merged or accepted; the tier does not carry
   an unmerged renderer.
6. The maintainer has not been asked to test Old 3DS hardware. The evidence
   pack is self-contained.

## 10. Drop criteria

Drop the tier, or leave it downstream, if any of these happen:

- The field p95 stays above 50 ms after PRs 2-10, with no clear path to 40 ms.
- The memory ledger cannot fit the 64 MiB mode without starving the game.
- The 2D atlas or retained geometry causes a fallback storm in common scenes.
- The tier requires disabling saves, audio, or a core gameplay feature.
- Upstream objects to the profile's presence. The core PRs are independent;
  the tier can live in a downstream branch without blocking them.

Dropping the tier is a successful outcome for the core series, not a failure
of the plan. The New 3DS wins are the point.

## 11. Relationship to upstream

- The core PRs are proposed one at a time, on New 3DS terms.
- The tier is proposed last, as an opt-in profile. It does not change the
  supported-platform statement.
- If upstream accepts the core and declines the tier, the tier remains a
  downstream patch or a documented build option. The core work is unaffected.
- If upstream declines both, the work is still a coherent downstream series;
  it is not a fork with a divergent renderer.

## 12. Open risks

- **No baseline.** There is no `pokeplatinum-3ds` Old 3DS baseline. Every
  number here is a target or a `kohjoh` measurement.
- **Two cores, not four.** The scheduling work must have a real 2-core mode.
  Pretending the O3DS has four cores will fail under load.
- **VRAM is 6 MiB.** The atlas, retained geometry, and 3D textures compete for
  it. The ledger is a hard constraint.
- **The GPU is half the clock.** A technique that is comfortable on N3DS may
  be marginal on O3DS. Measure, do not extrapolate.
- **The tier is a support surface.** Even opt-in and experimental, it will
  attract bug reports. The documentation must say what it is and is not.
