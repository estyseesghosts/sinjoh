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

## Both ports read `sdmc:/3ds/kohjoh`

**Symptom.** Staging sinjoh's pack for LOTUS risked replacing kohjoh's data.

**Cause.** Both ports use the same guest path; separate storage roots do not
separate them, because both would still resolve `sdmc:/3ds/kohjoh`.

**Fix.** One primary **card** per project (`cards/sinjoh`, `cards/kohjoh`),
each with its own `sdmc/`. `tools/lotus/stage_card.py --card sinjoh` fills only
sinjoh's card; kohjoh copies its own pack into `cards/kohjoh/sdmc/3ds/kohjoh/`.

**Transferable.** Isolate by the guest's namespace (the card), not by the
host's directory layout.

## Screen capture through the desktop window

**Symptom.** `PrintWindow` captures of the Azahar window were clipped or
included window chrome; PDF-then-PNG round-trips lost pixels.

**Fix.** Stopped capturing the host window. The emulator's own native capture
(`Ctrl+P` in Azahar; `lotus_capture` in LOTUS) yields the guest's 400x240 and
320x240 screens without the host compositor in the path.

**Transferable.** Capture at the emulator boundary, not from the desktop.
