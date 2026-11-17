# Lessons

Failure → cause → fix, with the evidence that settled each one. Written for
the kohjoh implementer as much as for sinjoh: most of these are engine or
workflow traps, not game-specific ones.

## The title gradient vanished while BG1 faded in

**Symptom.** The copyright screen showed BG1 (the © text) over flat black
instead of over BG3's gradient. BG3 was in the DS state and in the render, but
disappeared as BG1's EVA rose.

**Cause.** The screen is a first target (BG1, EVA 0→16/16) over a second
target (BG3, EVB 16/16). Alpha blending is two draws, and the engine ran the
blended pass first. That pass inverted stencil bit 0 for a layer that is not a
second target. The following opaque pass then tested bit 0, saw the inverted
value, and redrew the layer opaquely over the blend. Any full-screen first
target with EVA > 0 replaced everything under it.

**Fix.** `engine/graphics/g2d/g2d.c` `draw_layer`: draw the opaque pass (bit 0
clear) first, then the blended pass (bit 0 set). Commit `8cec61d`.

**Evidence.** A capture at the same game frames as melonDS (30 and 120) is
pixel-identical; the top screen shows BG3 with the 25%/94% BG1 fade. LOTUS
reproduced the same frame at 400x240.

**Transferable.** The compositor's ordering is part of the hardware contract.
The stencil mask "is there a second target below" must be read before anything
writes it. A one-line pass-order bug looks exactly like missing art or a bad
palette, so check draw order before touching data.

## The washed-out field

**Symptom.** The field looked over-bright and flat, as if a grey veil covered
the picture.

**Cause.** The same pass-order bug: a full-screen first target replaced the
scene with the overlay's own colour. The DS state, palettes and 5-bit expansion
were already correct.

**Fix.** The blend-order fix above, with no gamma, range or palette change.

**Evidence.** The 2D colours measured exactly DS 5-bit expansion before the
fix, and the field matched expectations after it. If a "washed out" picture has
correct measured colours, stop looking for a colour-space bug.

## A long detour before a pixel oracle existed

**Symptom.** Days of plausible theories (gamma, range, palette, TEV) about the
wash, none of which survived a test.

**Cause.** No way to say "this is what the frame *should* be" independently of
the renderer under suspicion.

**Fix.** A scratch offline DS renderer: dump the DS state (`KJD1`), draw text
BGs, OBJs, priorities and blending on the CPU, and compare with the emulator.
That proved the DS state was right and localised the fault to the engine.

**Transferable.** Build the oracle before the theory. It is cheaper than one
more speculative change, and it is reusable for the next visual bug.

## The wide bands went white only on the retained path

**Symptom.** The 40-pixel side bands on the top screen were pure white on the
copyright screen. A build from before the retention change was correct, and
the same frame was sometimes correct afterwards, so it looked intermittent.

**Cause.** The new retained edge/band vertex buffers were allocated with
`malloc`, while the layer's own retained quads use `linearAlloc`. The PICA
reads the vertex buffer from the address it is given; heap memory was stale, so
the bands drew nothing and the target's white clear showed through. Frames that
took the per-span path still used the arena (`linearAlloc`) and were correct,
which is why it was path-dependent rather than random.

**Fix.** `engine/graphics/g2d/g2d.c` `art_alloc`: allocate `lc->edge` and
`lc->band` with `linearAlloc`. Commit `f8a2637`.

**Evidence.** At frame 172 the capture is pixel-identical to the pre-change
build (`ImageChops` difference bounding box empty); frames 172 and 371 both
sample the band colour `(99, 33, 33)` at x=5/20/39 instead of white.

**Transferable.** Any buffer whose address is handed to the GPU must be
`linearAlloc` (or explicitly flushed), not heap memory. When a visual fault
looks intermittent, check whether it tracks a *code path* (retained vs
per-span, arena vs cache) before suspecting a race. A fixed-frame pixel diff
against the previous build is the fastest oracle.

## "The game ignores input" was the harness's button order

**Symptom.** Pressing START on the title/opening never advanced the game.
Scripted presses did nothing, and live presses appeared to do nothing.

**Cause, part one.** `lotus_input`'s `buttons` is a bitmask in LOTUS's
`NativeButton` order (A 1, B 2, X 4, Y 8, Up 16, Down 32, Left 64, Right 128,
L 256, R 512, Start 1024, Select 2048), not the DS/libctru order. Sending `8`
pressed Y. The engine and game were fine; the debug `[input]` log showed
`pad 0800`, and `0x400` produced `pad 0008`.

**Cause, part two.** While a `script.txt` is staged, `kj_script_input` answers
every frame, so live input is ignored by design. Earlier live-input tests ran
against a script and proved nothing.

**Fix.** Documented both in `docs/LOTUS.md`; added the profile-only
`[input] pad xxxx` edge log in `engine/runtime/kj_frame.c`. Commit `f8a2637`.

**Evidence.** `gSystem.heldKeysRaw = 0x8` and `pressedKeysRaw = 0x8` in guest
memory on a real START edge, read through `lotus_read_memory`.

**Transferable.** Verify the whole input path (harness mapping → engine
mapping → guest register → `gSystem`) before blaming the game. One
guest-memory read of `gSystem` settles it.

## GDB read the IO registers one halfword off

**Symptom.** A GDB session "proved" blend values that produced the wrong
picture.

**Cause.** The register map was misread. `DISPCNT` is IO 0x00, `DISPSTAT` 0x04,
`VCOUNT` 0x06, `BG0CNT` 0x08; the read started one halfword late, so every
field was shifted.

**Fix.** Dump the same frame and align on known `DISPCNT`/`DISPSTAT`/`VCOUNT`
values before reading anything else, then cross-check against the `.kjd` dump.

**Transferable.** When a debugger read contradicts the picture, verify the
address map with a known value first; a shifted read looks like a real bug.

## EVA/EVB "contradicted" the note

**Symptom.** A previous note said `EVA=0`, but the screen was clearly blending.

**Cause.** `BLDCNT`/`EVA`/`EVB` describe a fade at that instant, not a fixed
scene. The earlier note was taken at a different frame.

**Transferable.** Never record blend registers without the frame number, and
never compare two captures from different frames.

## The build ID never changed

**Symptom.** The log kept naming the old commit after new commits were built.

**Cause.** `build_id.h` was generated once and never refreshed; then it was
made an order-only prerequisite, so even a correct ID never relinked `main.o`.

**Fix.** Regenerate with `FORCE`, rewrite the file only when the content
changes (so a no-op build stays a no-op), and make `build_id.h` a normal
prerequisite of the ARM11 objects. Commits `b5f6077`, `466f698`. Verified:
release logs `sinjoh-a8ffd5820dd9`, debug logs `sinjoh-a8ffd5820dd9-dbg`.

**Transferable.** A generated header has two independent problems: generating
it, and depending on it. An order-only dependency silently defeats the second.

**Same bug, different header.** `nitro/fx/fx_const.h` is generated from the SDK
decomp's CSV and is not checked in; nothing in the tree generated it on a fresh
checkout, so a `-Clean` build died in `<nitro/gx/g2_oam.h>`, and so did the
first CI run. Fixed with a real rule in `engine/game.mk` (`python3
gen_fx_const.py <csv> <header>`) that `libs` and the engine objects depend on.
Verified by deleting the header and building: `GEN nitro/fx/fx_const.h` then a
clean link.

## `-All` died on a libnitro race

**Symptom.** The first build that produced both profiles failed with two makes
colliding on `build/3ds-prof/arm7_renamed/...`.

**Cause.** A fresh per-profile tree meant two recursive makes of `libnitro`
could run concurrently on the same filenames.

**Fix.** One serial `libs` target in `engine/game.mk` that builds
libnitro/libnitrosystem before the game. Both profiles then built cleanly.

**Transferable.** Separate object trees are necessary but not sufficient;
shared recursive sub-makes still need one owner.

## Outdoor test scripts never reached the field

**Symptom.** Scripted runs that were supposed to walk out of the bedroom
stalled; one run never reached the frame the harness waited for and had to be
killed.

**Cause.** The bedroom has a scripted rival encounter ("Roy: There you are!")
that takes control before the walk starts, so the input schedule pressed
buttons into a conversation instead of movement.

**Fix.** Reverted `save_outdoor.txt`, kept the interior field capture as the
verified data point, and left the outdoor wide 3D marked unverified rather
than claiming it. See `tests/inputs/lotus_field.txt` for the current schedule.

**Transferable.** A deterministic input script is only deterministic against
one game state. Scripted cutscenes invalidate the schedule; verify each step
with a capture instead of trusting the frame count.

## LOTUS captures looked like PNG and were not

**Symptom.** Saved "PNGs" would not open; the file sizes were exactly
`400*240*4` and `320*240*4`.

**Cause.** `lotus_capture` returns raw 32-bit BGRA artifacts, not images. They
were written out under a `.png` name.

**Fix.** `tools/lotus/run_sinjoh.py` `write_png()` converts BGRA to 8-bit RGB
with a small built-in writer, so the harness needs no Pillow. The channel order
was confirmed by the red side bands and the copyright colours.

**Transferable.** Check the resource description (`400x240`, byte count) before
naming a file.

## White frames looked like a hang

**Symptom.** Captures at 1903 and 2600 frames were pure white; the run looked
stuck.

**Cause.** The game was mid-transition. Stepping every 300 frames from 300 to
2100 showed the black/white fades and then the Pokémon logo.

**Fix.** Stepped captures instead of one endpoint, and filed no LOTUS issue.

**Transferable.** A white frame is usually the guest, not the renderer. Sample
the timeline before blaming the emulator.

## Sharing one windowed LOTUS

**Symptom.** Only the process that spawned `lotus-desktop --mcp` could drive
it; a second script could not attach.

**Cause.** Windowed MCP is stdio-only by design; there is no listener to
connect to.

**Fix.** `tools/lotus/bridge.py` owns the stdio once and serves calls on
`127.0.0.1:45761`; `tools/lotus/ctl.py` is the client. Sessions belong to the
bridge's supervisor, so any client can run/capture/stop them, and the window
shows the same sessions. Calls serialize, so parallel sessions advance in turn.

**Transferable.** Treat the emulator supervisor as a service. One owner of the
stdio, many clients, sessions addressed by ID.

## Sinjoh inherited its predecessor's SD path

**Symptom.** Sinjoh's first packaged builds wrote and read
`sdmc:/3ds/kohjoh/`, because the storage module came from the older port and
its root string came with it. On a card that also holds that port, both
programs shared `data/`, `saves/` and `logs/`.

**Cause.** A copied engine module carried a hardcoded product name. Two more
literals in the renderer's dump path repeated it.

**Fix.** The root is `sdmc:/3ds/sinjoh` in `engine/storage/paths.c`; the
programs are `sdmc:/3ds/sinjoh-platinum.3dsx` and
`sdmc:/3ds/sinjoh-platinum-dbg.3dsx`; the renderer asks
`kj_paths_get()` for the dump directory instead of repeating a literal. The
packager stages the programs at `3ds/` and their data at `3ds/sinjoh/`.

**Transferable.** Rename the product's namespace as soon as an engine module
is imported. A hardcoded path is a silent data-collision bug, and it only
shows up when two products share a card.

## Screen capture through the desktop window

**Symptom.** `PrintWindow` captures of the Azahar window were clipped or
included window chrome; PDF-then-PNG round-trips lost pixels.

**Fix.** Stopped capturing the host window. The emulator's own native capture
(`Ctrl+P` in Azahar; `lotus_capture` in LOTUS) yields the guest's 400x240 and
320x240 screens without the host compositor in the path.

**Transferable.** Capture at the emulator boundary, not from the desktop.
## A ported optimization needs this port's call count

**Symptom.** kohjoh's Pokemon-data keystream cache (its patches 2002/2005) is
a measured win there (crypto ~12% of field instructions). Porting it to
Platinum's `EncodeData` was worth -4.3% of logic, not 12%, and the first
`[mon]` reading of the field said `0 calls`, which would have made it worth
nothing.

**Cause.** Two separate things. The call count differs by game: Platinum's
field decrypts the party 168 times a frame (19 KB), HGSS's field decrypts far
more. And the `0 calls` was not a measurement at all: the counter lives in the
game patch, the engine reads it through a weak symbol, and the build that
printed zero had no such symbol. `nm` on the ELF showed
`EncodeData_TakeStats` missing, which is why the weak reference resolved to
NULL.

**Fix.** Ported the cache with a debug-only call/byte counter and a `[mon]`
window line, and read the count from a build that defines the symbol. Logic
p50 4500 -> 4308 us, active 6593 -> 6399, captures pixel-identical.

**Transferable.** A weak symbol that is absent reads as zero, and zero is a
plausible answer for a hot-path question, so the failure is silent. Check the
symbol exists in the ELF before believing a zero counter, and measure the
ported optimization in the target game before claiming the source game's
number.

## Two builds at once measure a binary that exists in no tree

**Symptom.** Field probe runs printed impossible splits: slot 0 (the whole
field update) 2408 us, slots 1 and 3 missing entirely, slots 8-10 present with
`0 us`, all in the same window that reported 15,520 3D draws. A later run of
the same source gave a complete, consistent split.

**Cause.** Two builds were running against the same trees. A `-All` started
while a `-Profile 1` build was still going, and both write
`build/game/3ds-prof/...`; the linked binary took `kj_frame.o` from one build
and `renderer.o` from the other. `KJ_PROBE_SLOTS` had changed from 6 to 11
between them, so the two halves disagreed about `kj_ds_profile`'s layout: the
engine wrote six slots at one offset and the renderer read eleven at another.
The object timestamps showed it (`kj_frame.o` older than the header edit while
`renderer.o` was newer).

**Fix.** Kill the stale build, check the object timestamps, and measure from a
clean build (`tools/build.ps1 -All -Clean`). The probe facility itself was
correct; the binary was not.

**Transferable.** When one number in a window contradicts another (0 us for a
slot that must have run, or an absent slot next to a huge draw count), suspect
the binary before the code. A partial rebuild that does not agree on a struct
in a shared header produces readings no single source tree can produce.


## A batch merge that joins nothing must be counted, then deleted

**Symptom.** Joining contiguous same-state 3D batches into one
`C3D_DrawElements` is the textbook lever for a PICA200 port: a separate draw
costs ~9.7 us of CPU, and the DS splits meshes into small strips. Applied to
Platinum's field it changed nothing: `3D batches 15560 draws 15560`.

**Cause.** The key required byte-identical state *and* an identical matrix
palette. Counters added for one run answered it in one line:
`merge joined 0 (blocked state 15093 matrices 0)`. Every consecutive batch in
the field is a different material (different `poly_attr`/`tex_param`), so the
key can never match, in the field or in the title scene (0 joins there too).
The DS batch is a *material*, not a strip of one material.

**Fix.** Removed the merge. Kept the redundant-state filter, which that same
run counted at 38,511 skipped `C3D_*` setters per 600 frames (82% of them) and
which is where the g3d win actually came from.

**Transferable.** A merge/batch optimization is not real until its join count
is printed and non-zero. Counter the *reason* it would decline (state vs
matrices vs index contiguity), measure once, and delete the code when the
answer is zero; otherwise it ships as an unmeasured memcmp per batch.

## Reverting a restructured loop means restoring its header too

**Symptom.** After removing the merge, reading the function showed
`for (uint32_t i = 0; i < f->batch_count; )` with the draw at the end and no
`++i`: a frame with any batch would have hung in `draw_pass`.

**Cause.** The merge had restructured the loop (`i = j` at the end, explicit
`++i` before each `continue`). Deleting the merge body and the trailing
assignment left the header, and the `continue` paths, in the merged shape.
Nothing warns: it compiles, and the `continue`s still increment.

**Fix.** Restored `++i` in the header and plain `continue`s, then rebuilt and
re-ran (g3d 832 us, captures pixel-identical to the pre-change baseline).

**Transferable.** When an optimization changes control flow, the revert is a
control-flow change too. Diff the loop header, not just the body, and re-run
the same capture comparison rather than trusting the absence of a crash.

## A field run that never reached the field still prints a full window

**Symptom.** A map-app probe run printed a complete 600-frame window with
`[perf]`, `[gpu]` and `[ds]` lines: g3d 0 us, `2D screens skipped 1200`,
`layers reused 3000 rebuilt 0`, `3D batches 0`, `g3 Fifo calls 0`, and no
`[probe]` line. Every engine counter was internally consistent; the window was
a still picture. The capture showed the journal screen.

**Cause.** The harness sends three presses (START, A, START) at fixed frame
offsets. Only the first two arrived (`[input] pad 0008` then `0001`; the log
prints DS keypad bits, so 0x8 is START and 0x1 is A); the third `lotus_input`
did not take, so the journal — which closes on START, never on A — stayed open
for the recorded windows.

**Fix.** Re-ran the same harness on the same binary; the second run reached the
field and printed the 3D counters and the probe slots.

**Transferable.** A window of zeros is not a measurement of "nothing ran"; it is
usually a measurement of the wrong screen. Before reading any number, check what
the run was showing: `[gpu] 3D batches 0` with `[scene] same scene 600` and a
capture of a menu is a harness failure, not a sample of a field that does no 3D
work. Take the capture from the same window the numbers come from.

