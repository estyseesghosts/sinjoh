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

Foundation. The engine is in place under `engine/`; the game source, the
NitroSDK and NitroSystem decompilations bootstrap reproducibly; the LOTUS MCP
harness drives windowed sessions. The game-side patch stack and the
engine/game link are the current work (see `docs/STATUS.md`).

Nothing here is certified on O3DS hardware. LOTUS and Azahar are integration
debuggers, not timing authorities.

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
python tools/game/platinum_game.py --target 3ds --out build/kj
```

The user's own Platinum dump is only needed to build the data pack; no game
data is stored in this repository.

## Provenance and licence

Sinjoh's own code is GPL-3.0. The engine is adapted from
[`kohjoh`](https://github.com/estyseesghosts/kohjoh) (GPL-3.0). The game-side
compatibility work is derived from the patch stack of
[`pokeplatinum-3ds`](https://github.com/GabeSud0/pokeplatinum-3ds) (GPL-3.0);
its renderer is **not** imported. See `PROVENANCE.md` and `NOTICE.md`.

No ROM, extracted asset, save or captured game image belongs in this
repository or its artifacts.
