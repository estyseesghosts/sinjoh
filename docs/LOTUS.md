# LOTUS v0.0.3

Verified 2026-11-16 against `LOTUS-v0.0.3-windows-x64` on Windows 11. The
workers are pinned in `runtimes/*/build-manifest.json` (CITnLO experimental
`559f3f4d…`, AZAHAR integration `b4b9f0c…`). This replaces Azahar as the test
frontend: it is windowed, it serves MCP on stdio, it can keep several sessions
at once, and its CITnLO worker runs the **Vulkan** renderer.

## Windowed, over MCP

`lotus-desktop.exe --mcp <host.json>` opens the window and serves the same MCP
tools on stdin/stdout, so the person watches the session the harness drives.
`lotus-mcp.exe <config>` is the headless variant. A session handle expires when
the server process exits; a primary card keeps its `sdmc/` data.

`sinjoh-host.json` in the LOTUS folder approves both builds and prefers Vulkan:

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

A primary card's guest SD is
`<lotus>/data/citnlo/sessions/cards/<card>/sdmc/`; sinjoh reads the usual
`sdmc:/3ds/kohjoh/` paths, so `stage_card.py` writes
`.../cards/sinjoh/sdmc/3ds/kohjoh/`. A secondary session can copy that card for
a disposable run, or start empty.

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
