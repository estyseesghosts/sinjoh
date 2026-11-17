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
