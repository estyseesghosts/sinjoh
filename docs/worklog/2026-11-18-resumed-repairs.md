# 2026-11-18 resumed repairs

The interrupted session's LOTUS MCP connection is working again, with both
projects' build directories exposed. The commits below were pushed to `master`.

## Changes and host checks

- `ce4f523` fixes scripted input ownership ([#10](https://github.com/estyseesghosts/sinjoh/issues/10),
  closed). Settings-only scripts leave live input enabled; timed scripts own
  pad and touch through the final exclusive endpoint, including gaps, then
  release both. Native tests cover overlaps, gaps, settings, malformed input
  and endpoint overflow.
- `110004a` tracks transparent BG and OBJ tile bytes in retained-layer
  invalidation and corrects blend-pass ordering ([#7](https://github.com/estyseesghosts/sinjoh/issues/7)).
  Native tests exercise both engines, unchanged reuse, blank-to-visible and
  visible-to-blank edits, palette changes and atlas failure. A synthetic
  stencil model passes for production and rejects both fixed pass orders.
- `76fd367` adds checked DeSmuME/No$GBA import, backup preservation and
  recovery documentation ([#11](https://github.com/estyseesghosts/sinjoh/issues/11),
  open). Follow-up `52b693f` checks
  whether a candidate is occupied after a failed exclusive create, then tries
  the next suffix with exclusive create. All nine native importer tests pass,
  including backup collisions and injected write/replace failures.

Release and profile builds passed with these changes present in a dirty source
tree; both profiles were also rebuilt after the collision-handling change.
Native checks do not exercise the PICA GPU. A screen-level blank-tile capture,
a targeted blended wide-band capture, and comparison with an independent DS
reference remain useful regression coverage.

## LOTUS observations

LOTUS used CITnLO worker source `c3422b0a712b14cdeabc638693a55d733b43e524`,
worker SHA-256 `c77d459de1a143d88ef168462f0a74295896562b1b5fe1fbcfdef19094921568`,
renderer 2 (Vulkan), and no renderer fallback. These are emulator observations,
not O3DS timing results.

- With a settings-only script, live START and touch appeared in the game log.
  A neutral timed event over V-blanks `[0, 200)` suppressed held live START and
  touch during the interval; both appeared after its endpoint without a guest
  restart. Native tests cover the more detailed overlap and gap cases.
- In a disposable card copy, a user-owned raw Platinum save wrapped locally in
  a DeSmuME-format container converted byte-for-byte to raw and retained the
  complete container as `.orig`. Continue reached the journal and Mt. Coronet
  field; in-game Save, reset and Continue returned to the field. The wrapper
  was constructed locally, not exported by an independently run emulator.
- A locally constructed packed No$GBA container from the same save initially
  failed to import with `.orig` occupied; the active packed input and earlier
  `.orig` remained byte-identical. After the collision-handling change, the
  debug build retained the existing 524,410-byte `.orig`, created a 528,498-byte
  `.orig.1`, and produced the expected 524,288-byte raw save byte-for-byte.
  Continue reached Mt. Coronet; in-game Save changed the raw file, and reset,
  Continue and journal dismissal returned to the field. Both backups still
  matched their local fixtures exactly. The errno from the original failure
  was not measured. Independently produced emulator exports remain to be
  tested; #11 remains open.

A packed container whose entire file is exactly 512 KiB currently follows the
raw-save path; [SAVE-IMPORT.md](../SAVE-IMPORT.md) records the ambiguity. The
backup is also the recovery copy across a potentially non-atomic rename;
[Coffeepot's save guidance](https://github.com/estyseesghosts/coffeepot/blob/main/ctr/engineering/filesystem-and-saves.md)
explains the filesystem constraint.

## Remaining gates

The broader [WideArt conformance issue #6](https://github.com/estyseesghosts/sinjoh/issues/6)
still needs scene comparisons and physical O3DS validation. Widescreen window
effects, semantic layouts, OBJ-window support and build provenance remain
separate open issues. This pass did not measure O3DS frame pacing or certify
the outstanding release and hardware checks.
