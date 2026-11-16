# Upstream notes

> How to make this work reviewable by a maintainer who does not benchmark
> hardware and does not want an Old 3DS support burden.

## 1. The maintainer's position

Assume the maintainer:

- targets the New 3DS family;
- does not run benchmarks on request;
- does not want to own an Old 3DS test lab;
- will judge a PR by its code, its tests, and its effect on the supported
  hardware;
- has seen large "port it to weaker hardware" proposals before and is right to
  be wary of them.

The plan works with that position, not against it:

- every core performance PR is justified by a cost visible on New 3DS;
- the evidence is self-produced and deterministic;
- the Old 3DS tier is last, opt-in, and optional;
- no PR changes New 3DS defaults without a measured win.

## 2. Start with one small conversation, not the whole plan

Do not open with an 11-PR roadmap and an Old 3DS tier. Open with the two costs
the project already documents:

1. the 864 KB / ~15 ms unchanged-frame 2D change check;
2. the 20-30 ms CPU geometry per scene.

Then say: these are New 3DS costs; I have a sequence of small changes that
remove them, each with a deterministic test; the first is telemetry, the second
is the change check. Ask whether that direction is welcome before writing the
large PRs.

If the maintainer prefers a different order or a different approach, take it.
The plan is a proposal, not a contract.

## 3. PR shape

- One branch per cost, named `perf/...`.
- One idea per PR. No drive-by cleanups, no reformatting, no line-ending
  churn.
- Keep the diff as small as the change allows. If a brief says XL, look for a
  natural split during implementation (for example affine BGs and sprites are
  separate costs) and open two PRs rather than one giant one.
- New behavior is off by default until it passes its gate.
- The old path remains selectable.
- Each PR includes its own evidence. A reviewer should not have to run
  hardware to see the point.
- A PR that depends on an unmerged branch is opened as a draft and says so.

Commit messages follow `CONTRIBUTING.md`: imperative summary, blank line, then
what and why. AI-assisted commits carry `Co-Authored-By: Claude`.

## 4. Evidence pack

The PR description carries a short, self-contained evidence section:

- **What changed:** one paragraph.
- **Why it matters on New 3DS:** the measured cost and the expected effect.
- **Correctness:** the exact test command and the result, including the
  differential or golden-frame comparison.
- **Performance:** before/after counters from our own hardware, with the scene,
  build, and run count. Label Azahar instruction counts as instruction counts,
  not milliseconds.
- **Risks:** what could regress and how the fallback works.
- **Rollback:** the flag or config key.

Rules for evidence:

- No game content in the PR. No ROMs, saves, captured assets, or screenshots of
  game footage. The repository's rules are strict about game content, and a PR
  that attaches game imagery risks being closed for that alone.
- Use synthetic fixtures, numeric pixel diffs, and logs. If a visual is
  genuinely needed, describe the scene and let the reviewer reproduce it with
  their own data.
- Do not ask the maintainer to benchmark. If they choose to test in Azahar,
  that is a bonus, not a requirement.
- Do not present an emulator instruction count as a hardware frame time.
- Do not lean on an Old 3DS number to justify a core PR. A core PR's merge
  case is the New 3DS. PR 10's 2-core mode is an optional sub-feature, not the
  reason for the PR.

## 5. CI and tests

The project's CI builds the 3DS code and runs the Python tools. A red build
does not merge. `CONTRIBUTING.md` also asks for an Azahar test when possible.

Every PR should:

- pass `make test` for the host build, and the host32 suites
  (`make -C 3ds_port/nitro TARGET=host32 test`,
  `make -C 3ds_port/game TARGET=host32 test`);
- pass `make game` for the 3DS build;
- add host tests for new logic, not hardware-dependent tests;
- keep the existing suites green: `test_render`, `test_gx3d`,
  `test_gx3d_plumbing`, `test_sound_chip`, `test_threads`, `test_speed`, and
  the VRAM/upscale/shadow/lower-menu/options suites;
- not add CI that publishes a build containing game code. The artifact
  allow-list in `tools/check_ci_artifacts.py` is not a place to broaden.

If a test needs a captured G3 stream, use the existing `gx3d_replay` harness
and a small synthetic fixture, not a game capture.

## 6. AI disclosure

Follow `AI_DISCLOSURE.md` exactly:

- AI-assisted changes arrive as pull requests, never as direct pushes to
  `main`.
- Commits carry `Co-Authored-By: Claude`.
- The PR description says what the AI did and what was verified by a human.
- Every change is built by CI and tested by a human before merge.
- AI is never used to generate, recreate, or "clean up" game assets.
- No code from leaked sources and no code from ports that bundle game assets.

A short disclosure paragraph in the PR is enough:

> This change was developed with Claude, which helped with the design and wrote
> parts of the code and tests. A human reviewed the change and ran the tests.
> Commits carry `Co-Authored-By: Claude`. No game assets were generated or
> copied.

Do not over-explain or apologize for AI assistance. The project already has a
policy; follow it.

## 7. GPL provenance

`pokeplatinum-3ds` and `kohjoh` are both GPL-3.0. Adapting a technique or a
small piece of code is compatible, but it needs provenance:

- State the source repository and the commit or file in the commit message.
- Keep the GPL notice and the original copyright notice in any file that
  contains adapted code.
- Add a file-header note: "Adapted from kohjoh (GPL-3.0), <commit>, for
  pokeplatinum-3ds; modified for <reason>."
- If the adaptation is substantial, add the attribution to `NOTICE.md` as well
  as the file header.
- Do not copy game data, textures, models, scripts, or captured streams from
  either project.
- Do not copy code from leaked sources or from ports that bundle the game's
  assets. `kohjoh` is GPL-3.0, but its license does not make HGSS assets
  usable.

When in doubt, describe the technique in the PR and write the implementation
against `pokeplatinum`'s own data structures. A described technique is not a
copyright problem; a copied file without attribution is.

## 8. Review strategy

### Before the first PR

- Open one short issue or discussion with the two costs and the proposed first
  two steps. Do not paste the whole plan.
- Ask for the maintainer's preferred direction. If they want the change check
  first and telemetry later, reorder.
- Confirm that a config-gated, default-off backend is acceptable.

### The first two PRs

- `perf/telemetry`: small, no behavior change, easy to review. It establishes
  the measurement vocabulary.
- `perf/render2d-change`: the clearest New 3DS win, the lowest-risk proof that
  the approach works. It should be the first merge candidate.

Do not open the XL renderer PRs until these two are understood. If the
maintainer rejects the change-check approach, the rest of the plan needs
rethinking, and it is better to know early.

### The XL PRs

- Ask for design feedback before writing the full implementation. A short
  design comment with the integration points and the fallback strategy is
  cheaper than a rejected 3,000-line PR.
- Split by cost when possible: affine BGs vs sprites, retained geometry vs
  lighting, windows vs blending.
- Keep the fallback path visible in the diff; it is the reviewer's assurance
  that the old behavior is safe.
- If a PR stalls, reduce scope rather than adding features to justify it.

### Handling pushback

- **"We don't support O3DS."** Agree. The core PRs are N3DS performance work;
  the tier is an optional last step and does not change support policy.
- **"I can't benchmark this."** You are not asking them to. Point to the
  deterministic test and the self-produced log.
- **"This is a huge renderer rewrite."** It is not; it extends the existing
  compositor and keeps the old path. Show the integration points and the
  fallback.
- **"Why not use citro2d?"** The project already has a PICA compositor and a
  working 2D path. The plan extends it rather than adding a second renderer.
- **"The numbers are from an emulator."** Correct. They are instruction-count
  comparisons, not frame-time claims. The hardware claims come from our own
  logs and are labelled.

## 9. PR description template

```markdown
## What this changes

<One paragraph. The cost removed, the approach, the flag.>

## Why it matters on New 3DS

<The measured cost, quoted from the project's docs or from our `[perf]` logs.
No Old 3DS claims in a core PR.>

## How it works

<The design in prose. Integration points. The fallback path.>

## Correctness

- `make test`
- `make -C 3ds_port/nitro TARGET=host32 test`
- `make -C 3ds_port/game TARGET=host32 test`
- <New deterministic test>: <result>
- <Golden-frame / differential comparison>: <zero differing pixels / exact>

## Performance

Scene: <name>
Build: <commit>
Hardware: <New 3DS model, or Azahar instruction count>
Before: <counter>
After: <counter>
Runs: <n>

## Risks and rollback

<What can regress. The flag or config key that restores the old path.>

## AI assistance

This change was developed with Claude, which helped with the design and wrote
parts of the code and tests. A human reviewed it and ran the tests. Commits
carry `Co-Authored-By: Claude`. No game assets were generated or copied.

## Provenance

<If adapted from kohjoh: repository, commit, file, and the GPL notice. Otherwise
state "No third-party code.">
```

## 10. What not to do

- Do not open a single "O3DS support" PR. It conflates support policy with
  performance work and invites a rejection.
- Do not attach game screenshots, saves, ROMs, or captured assets to a PR or
  issue.
- Do not ask the maintainer to run benchmarks or test Old 3DS hardware.
- Do not change New 3DS defaults in the same PR that adds an experimental
  backend.
- Do not present `kohjoh`'s Azahar ticks as `pokeplatinum` frame times.
- Do not copy a `kohjoh` file wholesale and call it an adaptation.
- Do not let the diff include the repository's line-ending-only files.
- Do not argue about support policy. Restate the New 3DS merge case and let the
  code speak.
