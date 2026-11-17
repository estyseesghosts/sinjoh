# sinjoh

A native Nintendo 3DS source port of **Pokémon Platinum**, built for the
**original 2011 3DS** (and 2DS) at stock clock and 64 MB application memory.

Sinjoh is a new runtime, not a fork of `pokeplatinum-3ds`. Its internals are
**kohjoh's**: the HGSS Old-3DS port's single game-owned frame loop, GPU-native
2D tile atlas, object-space retained 3D with a PICA matrix palette, baked CPU
lighting for stable lists, decoded-ADPCM cache, and conservative pacing. The
game itself is the pinned `pret/pokeplatinum` decompilation, compiled for the
3DS's ARM11 against a NitroSDK compatibility layer, exactly as kohjoh compiles
HeartGold.

The target experience is the `pokeplatinum-3ds` remaster on hardware that
project does not support:

- both screens filled, native-resolution 3D at 400x240 on the top screen;
- the widened field camera and layout (25% more world at the sides);
- the lower screen as a menu in the field;
- crisp GPU-rendered 2D from a tile atlas;
- WideArt bands, **precomputed at package time** so O3DS only uploads them;
- stable 30 Hz presentation, no interpolation, no stereo, no sun shadows,
  no 2x2 supersampling, no xBRZ.

Those exclusions are deliberate. The GPU is the same 268 MHz PICA200 on both
models; the New 3DS's advantage is CPU and RAM. Sinjoh spends the O3DS budget
on CPU work removed (retained geometry, atlas 2D, ADPCM cache) and keeps GPU
work flat.

## Status

Boots the retail game through title, opening and save load into the field, with
both screens filled and the lower-screen remaster menu live. The 2D and 3D
paths are GPU-native, the field is a measured steady state (windowed LOTUS,
600-picture windows, `[perf]`/`[gpu]`/`[ds]` counters), and the last passes have
been work removal rather than feature work: a display-list cache, retained
band quads, a keystream cache for the Pokemon cipher, per-batch 3D state
filtering, and a decoded-ADPCM cache. `docs/STATUS.md` has the numbers;
`docs/ARCHITECTURE.md` explains how a frame is put together and how to measure
one.

Nothing here is certified on O3DS hardware. LOTUS and Azahar are integration
debuggers, not timing authorities; only counts of work removed transfer to the
stock console. The field's framing, the 3D wide camera and the lower menu's
apps are the open correctness items.

## Layout

```
engine/        kohjoh's runtime and GPU renderer, adapted (GPL-3.0)
  app/         entry, lifecycle, pacing
  runtime/     the DS/3DS bridge, G3 interpreter, frame publisher
  graphics/    g2d atlas, g3d retained geometry, textures, renderer
  audio/       sound-chip host, mixer, ADPCM cache
  content/     indexed data pack
  storage/     save store
  diagnostics/ perf ring, crash handler
tools/
  game/        bootstrap, source inventory, overlay map, build driver
  forwarder/   HOME Menu CIA forwarder (see docs/FORWARDER.md)
  lotus_mcp.py MCP client for windowed LOTUS
wideart/       hand-drawn wide-view bands (no game pixels)
patches/       sinjoh patch stacks (pokeplatinum, NitroSDK, NitroSystem)
docs/          architecture, porting plan, LOTUS findings, provenance
```

## Build

Prerequisites: devkitPro (`devkitARM`, `libctru`, `citro3d`, `3dstools`,
`picasso`) and Git for Windows on PATH ahead of MSYS2's git.

```sh
python tools/game/bootstrap.py        # pinned decomp + SDKs, apply patches
pwsh tools/build.ps1                  # release:  build/game/3ds/sinjoh-platinum.3dsx
pwsh tools/build.ps1 -Profile 1       # debug:    build/game/3ds-prof/sinjoh-platinum-dbg.3dsx
pwsh tools/build.ps1 -All             # both, side by side
```

The two profiles use separate build trees (`build/game/3ds` and
`build/game/3ds-prof`, and likewise for `libnitro`/`libnitrosystem`), so a
build never reuses objects compiled under the other profile's flags. The debug
build turns on the `[perf]`/`[gpu]`/`[pace]`/`[snd*]` counters and nothing
else; it is the one to use for measurements. On Windows, run make from the
devkitPro MSYS2 shell with Git for Windows first on `PATH` (its own git can
fetch over HTTPS; MSYS2's cannot).

The data pack needs the player's own Platinum dump, never committed. One
script does the whole job (check the dump, extract, pack, verify the pack, and
stage the built programs beside it):

```sh
python builder/prepare.py path/to/platinum.nds            # -> sinjoh-sd/3ds/
python builder/prepare.py path/to/platinum.nds --sd E:\   # write to the card
```

On Windows, dragging the `.nds` onto `builder/prepare.bat` does the same. The
result is an SD-card root; copy its `3ds` folder to the card's root. The
`.pak` is your game's data: never commit or share it. For a single pack
instead, `builder/extract_rom.py` and `builder/pack.py` still work on their
own. `pwsh tools/azahar/run.ps1 -Edition platinum -Pack ... -Manifest ...`
stages a pack for Azahar and collects screenshots and the log.

## HOME Menu forwarder

`tools/forwarder/` builds a small CIA that starts
`sdmc:/3ds/sinjoh-platinum.3dsx` from the HOME Menu. It contains no game code;
install it once with FBI and update the `.3dsx` normally.

```sh
pwsh tools/forwarder/build.ps1    # -> build/forwarder/sinjoh-platinum.cia
```

It needs `makerom` and `bannertool` in addition to devkitPro; see
`docs/FORWARDER.md` for the tool paths, title identity and limits.

## Provenance and licence

Sinjoh's own code is GPL-3.0. The engine is adapted from
[`kohjoh`](https://github.com/estyseesghosts/kohjoh) (GPL-3.0). The game-side
compatibility work is derived from the patch stack of
[`pokeplatinum-3ds`](https://github.com/GabeSud0/pokeplatinum-3ds) (GPL-3.0);
its renderer is **not** imported. See `PROVENANCE.md` and `NOTICE.md`.

No ROM, extracted asset, save or captured game image belongs in this
repository or its artifacts.
