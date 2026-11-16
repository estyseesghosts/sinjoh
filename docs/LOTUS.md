# LOTUS v0.0.2: what works, what does not

Verified 2026-11-16 against `LOTUS-v0.0.2-windows-x64` on Windows 11, worker
sources pinned in the release's `runtimes/*/build-manifest.json`
(AZAHAR `5a3c702f…`, CITnLO `6361ddc3…`).

## MCP works, windowed or headless

Both launchers serve the same MCP tools:
`lotus_status`, `lotus_create_session`, `lotus_load`, `lotus_control`,
`lotus_run_until` (1-600 frames), `lotus_input`, `lotus_capture`,
`lotus_session_status`, `lotus_read_memory`, `lotus_registers`,
`lotus_debug`, `lotus_focus_session`, `lotus_list_cards`,
`lotus_list_sessions`, `lotus_gdb`, `lotus_trace`,
`lotus_validate_scenario`.

`lotus_focus_session` is what makes a run watchable: the window shows that
session while the harness drives it. `tools/lotus_mcp.py` is a small stdio
client used for exactly this.

```sh
# Rewrite host.json for the windowed AZAHAR worker and approve a fixture.
powershell -File launch.ps1 -Backend AZAHAR -Mode Desktop -Fixture app.3dsx -ConfigureOnly

# Drive it from a script while the window shows the focused session.
python tools/lotus_mcp.py --config <lotus>/data/azahar/host.json status
python tools/lotus_mcp.py --config <lotus>/data/azahar/host.json \
    call lotus_create_session '{"asset":"homebrew","kind":"secondary"}'
```

A session handle expires when the MCP server exits. A `secondary` card is
disposable; a `primary` card persists. Sessions can run in parallel (the
worker limit is four), which is why renderer speed matters here.

## Vulkan cannot be forced in v0.0.2

The worker binaries are built with `-DENABLE_VULKAN=ON` and
`-DENABLE_SOFTWARE_RENDERER=ON`, and the worker reports
`worker supports software and Vulkan`. The frontend still pins the session
profile:

- `native-manifest.json` records
  `"backend": "azahar_native_software"` and
  `"profile": "old3ds/software/hle/dsp-muted/ticks-0/time-2000-01-01"`
  for every session, before and after any setting change.
- The only renderer-like setting exposed over MCP is `graphics_api`
  (`choices [0, 1, 2]`). Its consumer source is
  `src/core/rpc/rpc_server.cpp:170` - the capture RPC - not
  `src/core/frontend/emu_window.cpp`. Setting it to 1 is rejected with
  `InvalidArgument: worker supports software and Vulkan`; 0 and 2 are accepted
  and both still produce the `azahar_native_software` backend.
- The pinned profile string in `lotus-desktop.exe`/`lotus-mcp.exe` contains
  only `old3ds/software`.

So the portable v0.0.2 release cannot switch its worker to Vulkan without
rebuilding the worker from its integration branch. That is out of scope for
this repository.

Consequence for sinjoh:

- **Vulkan and visual/performance observation:** vanilla Azahar
  (`C:\Program Files\Azahar\azahar.exe`), windowed, `graphics_api = Vulkan`.
  This is the only accelerated renderer available on this machine.
- **Deterministic frame-driven runs and parallel sessions:** LOTUS over MCP,
  accepting that it is software and therefore slow. Use short frame counts
  and bound each request to the 600-frame limit.

## Guest layout

A session root is `data/<backend>/sessions/<handle>/` (`scratch/<handle>/`
also appears); `sdmc/` maps to `sdmc:/`. For sinjoh the expected paths are:

```
sdmc:/3ds/sinjoh/data/platinum.pak
sdmc:/3ds/sinjoh/data/platinum.manifest.json
sdmc:/3ds/sinjoh/saves/platinum.sav
sdmc:/3ds/sinjoh/script.txt
sdmc:/3ds/sinjoh/logs/sinjoh.log
```

A session created with an asset loads it paused, so pack staging is:
create, copy pack/manifest into `sdmc/`, `reset`, then run.

## Not authoritative

Neither LOTUS nor Azahar certifies O3DS timing. LOTUS's software renderer is far
slower than the console; Azahar charges nothing for PICA vertex work. `[perf]`
counters and instruction counts rank changes; hardware claims need hardware.
