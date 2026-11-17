# LOTUS v0.0.3

Verified 2026-11-16 against `LOTUS-v0.0.3-windows-x64` on Windows 11. The
workers are pinned in `runtimes/*/build-manifest.json` (CITnLO experimental
`559f3f4d…`, AZAHAR integration `b4b9f0c…`). This replaces Azahar as the test
frontend: it is windowed, it serves MCP on stdio, it can keep several sessions
at once, and its CITnLO worker runs the **Vulkan** renderer.

## One window, many sessions, shared by both implementers

`lotus-desktop --mcp` speaks MCP on stdio, so only the process that spawned it
can drive it. `tools/lotus/bridge.py` owns that stdio once, keeps the window
open, and serves the same calls on `127.0.0.1:45761`, so several shells — the
sinjoh and kohjoh implementers included — share one LOTUS and one set of
sessions.

Start the bridge once and leave it running:

```sh
python tools/lotus/bridge.py --port 45761
```

It opens the visible window and waits. If `python tools/lotus/ctl.py status`
answers, a bridge is already running; do not start a second one (the port is
taken). The bridge's host configuration is `shared-host.json` in the LOTUS
folder; it approves both projects' builds and prefers Vulkan. Host
configuration is startup input: to approve a new build directory, edit the
JSON and restart the bridge.

All test traffic then goes through the bridge:

```sh
python tools/lotus/ctl.py status
python tools/lotus/ctl.py create --kind primary --card sinjoh --asset sinjoh
python tools/lotus/ctl.py run <session> 600        # <=600-frame batches
python tools/lotus/ctl.py capture <session> --out build/lotus/cap
python tools/lotus/ctl.py sessions
python tools/lotus/ctl.py stop <session>
python tools/lotus/ctl.py call lotus_session_status '{"session":"<session>"}'
```

A session handle belongs to the bridge's supervisor, not to the client that
created it: any `ctl.py` connection can run, capture or stop it, and it stays
listed to everyone. Create sessions for a test and `stop` them when done; a
`secondary` is deleted on stop, a `primary` keeps its card. The bridge
serialises MCP calls (one worker call at a time), so parallel sessions advance
by turns rather than truly simultaneously; that is the intended shared mode.
`max_sessions` is 4 in `shared-host.json`.

Use different cards per project and per scratch run: `sinjoh`, `kohjoh`, and
throw-away secondaries. A card's guest SD is
`<lotus>/data/citnlo/sessions/cards/<card>/sdmc/`; sinjoh's `stage_card.py`
fills the `sinjoh` card with `3ds/sinjoh-platinum*.3dsx` and `3ds/sinjoh/`,
and kohjoh copies its own files into its card from its pack. The two projects
also use different guest paths (`sdmc:/3ds/sinjoh` and `sdmc:/3ds/kohjoh`), so
a card from one cannot feed the other.

If the bridge exits, its sessions stop (a primary card keeps its data). Keep
the bridge process alive for the whole working session; `ctl.py shutdown`
closes it cleanly.

`tools/lotus/run_sinjoh.py` remains for a self-contained run that opens and
closes its own window; use the bridge when tests should share the window.

## Windowed, over MCP

`lotus-desktop.exe --mcp <host.json>` opens the window and serves the same MCP
tools on stdin/stdout, so the person watches the session the harness drives.
`lotus-mcp.exe <config>` is the headless variant. A session handle expires when
the server process exits; a primary card keeps its `sdmc/` data.

`sinjoh-host.json` in the LOTUS folder is the one-shot config (the bridge uses
`shared-host.json`); both approve the builds and prefer Vulkan:

```json
{
  "worker": "<lotus>/runtimes/citnlo/ctr-worker.exe",
  "storage_root": "<lotus>/data/citnlo/sessions",
  "assets": {
    "sinjoh": "<repo>/build/game/3ds/sinjoh-platinum.3dsx",
    "sinjoh-dbg": "<repo>/build/game/3ds-prof/sinjoh-platinum-dbg.3dsx"
  },
  "asset_directories": {
    "release": "<repo>/build/game/3ds",
    "debug": "<repo>/build/game/3ds-prof"
  },
  "allow_control": true,
  "prefer_vulkan": true,
  "max_sessions": 4
}
```

`prefer_vulkan` is the default; a refusal at load is reported as
`renderer_fallback`. The session status reports `renderer: "vulkan"` and an
empty fallback when it is the real thing. `graphics_api: 0` in a profile pins
software for a reference run.

## Driving it

```sh
# Stage the programs, pack, manifest and save into a persistent card, and
# optionally a script.txt for deterministic input.
python tools/lotus/stage_card.py --card sinjoh --script tests/inputs/lotus_field.txt

# Open the window, create a primary session on that card, run N frames,
# capture both screens as PNG and stop.
python tools/lotus/run_sinjoh.py --asset sinjoh --card sinjoh --frames 900
python tools/lotus/run_sinjoh.py --asset sinjoh-dbg --frames 600 --keep
```

`--hold SECONDS` leaves the window open after the capture; `--keep` also leaves
the session running until the client exits. The process owns the session, so
the run ends when the client does.

For a repeatable steady state, `tools/lotus/field_run.py` drives the title into
the field and records whole 600-picture windows from the standing field:

```sh
python tools/lotus/field_run.py --asset sinjoh-dbg --windows 2 --out build/lotus/field_now
```

It creates the session, runs the title (6600 frames), presses START, A
(Continue), START, then records each window and saves `top.png`/`bottom.png` for
the last one. The second START is the journal's: it turns pages on A/left/right
and closes on START or B at page 0 (`journal_controller.c`), so a one-page save
looks frozen if you keep pressing A. Windows land on the same picture numbers
every run, which is what makes two builds comparable: capture the same picture
in both, diff with `ImageChops`, and expect `bbox None`.

A primary card's guest SD is
`<lotus>/data/citnlo/sessions/cards/<card>/sdmc/`; sinjoh reads
`sdmc:/3ds/sinjoh/`, so `stage_card.py` writes
`.../cards/sinjoh/sdmc/3ds/sinjoh/` and the programs beside it at
`.../sdmc/3ds/`. A secondary session can copy that card for a disposable run,
or start empty.

Scripted input owns the pad for the whole run. While `script.txt` exists,
`kj_script_input` answers every frame, including all-zero frames, so
`lotus_input` is ignored; a live press during a scripted run proves nothing.
To drive a session by hand, stage with no `--script` (that deletes
`script.txt`) and keep the save: `stage_card.py` copies the tree over the
card and leaves `saves/` in place.

`lotus_input`'s `buttons` is a bitmask in LOTUS's `NativeButton` order, not
the DS or libctru order: A 1, B 2, X 4, Y 8, Up 16, Down 32, Left 64,
Right 128, L 256, R 512, Start 1024, Select 2048 (Debug 4096, then ZL, ZR,
Home, Power). So START is `0x400`, not `0x8`; sending `0x8` presses Y. The
debug build logs `[input] pad xxxx` when the pad changes, which is the quick
way to check a mapping.

NDSP needs `sdmc:/3ds/dspfirm.cdc`. Without it the port starts silent, and
before the silent-clock fix a sound wait (the title's exit) never returned.
Copy it once into the card with `stage_card.py --dspfirm <path>`; the file is
not part of the repo.

Captures are artifacts with a lifetime quota in v0.0.3. After a few dozen
`lotus_capture` calls, the RPC returns `artifact quota reached; restart host
to reset catalog`, `ctl.py capture` saves nothing, and the window can stay on
an old guest frame while the game keeps running (audio continues, the frame
counter advances). That is the host, not the port. Restart `bridge.py` to
reset the catalog; issue estyseesghosts/lotus#27 covers bounded retention and
release.

## Tools used

`lotus_status` (frontend, assets, cards), `lotus_create_session`
(`kind: primary|secondary`, `card`, `asset`), `lotus_run_until` (1–600 frames,
paused), `lotus_control` (`run`/`pause`/`reset`/`stop`), `lotus_session_status`,
`lotus_capture`, `lotus_input`, `lotus_list_sessions`, `lotus_list_cards`,
`lotus_focus_session`, `lotus_debug`, `lotus_registers`, `lotus_read_memory`,
`lotus_gdb`, `lotus_validate_scenario`.

Exact option schemas: `python tools/lotus_mcp.py --config <host.json>
--headless tools`.

## Captures

`lotus_capture` returns two artifacts named `top` and `bottom`: **raw 32-bit
BGRA**, 400x240 and 320x240 (384000 / 307200 bytes), not PNG. `run_sinjoh.py`
converts them to 8-bit RGB PNG with a built-in writer, so the harness has no
Pillow dependency.

## First verified runs

- 240 frames: windowed frontend, CITnLO, `renderer: "vulkan"`,
  `renderer_fallback: null`, 240 frames paused; both captures correct.
- 900 frames: the Game Freak frame, with the copyright gradient and red side
  bands, pixel-for-pixel at 400x240. This is the same picture melonDS shows and
  a second emulator's confirmation of the blend fix.
- 1903 and 2600 frames with `tests/inputs/lotus_field.txt`: the session
  advanced, but both captures were white. The card log stops at the end of the
  opening, so the run had not reached the field; treat the white frame as an
  unclassified transition until the script is checked. Not evidence about the
  renderer.

## Limits

LOTUS and Azahar are integration debuggers, not O3DS timing authorities.
CITnLO's Vulkan path is fast on this host but does not model the console's GPU
budget or CPU caches; `[perf]` counters and instruction counts rank changes,
hardware claims need hardware. Audio is muted in this release. The worker's
guest date/time can come from the host clock unless a run pins `init_clock`.
