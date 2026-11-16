# Provenance

Sinjoh is GPL-3.0. This file records what was imported or adapted and from
where. Game data is never imported.

## Engine: kohjoh

`engine/` is adapted from [estyseesghosts/kohjoh](https://github.com/estyseesghosts/kohjoh)
at `fb0440a` (pinned in `upstream.lock`), GPL-3.0. That includes the frame
bridge (`runtime/kj_bridge.h`), the G3 display-list interpreter
(`runtime/kj_g3.c`), the frame publisher (`runtime/kj_frame.c`), the GPU
renderer (`graphics/renderer.c`, `graphics/g2d/`, `graphics/g3d/`,
`graphics/resources/`), the audio host and mixer (`audio/`), the content pack,
storage, diagnostics and the app lifecycle.

Modifications for sinjoh are made in this tree; each touched file keeps the
original GPL notice and gains a header line naming the change.

## Game-side compatibility: reference, not import

The Platinum game's compiler/ABI/correctness fixes and the shape of the SDK
compatibility layer were derived by reading
[GabeSud0/pokeplatinum-3ds](https://github.com/GabeSud0/pokeplatinum-3ds) at
`c84883d` (GPL-3.0), in particular its `patches/` stacks. Its renderer,
compositor, software 2D path and `NitroPort_*` API are **not** imported: sinjoh
targets kohjoh's `kj_*` bridge instead. Adapted patch files carry a header
naming the source file and commit, and the reason for the change.

## WideArt

`wideart/` contains hand-drawn wide-view bands from `pokeplatinum-3ds`, which
states they contain none of the game's pixels. The sinjoh packer composites
them offline into map-keyed textures; the console only uploads the result.

## Game source

`build/upstream` is a fetch of [pret/pokeplatinum](https://github.com/pret/pokeplatinum)
at the pin in `upstream.lock`, and `build/NitroSDK`/`build/NitroSystem` are the
SDK decompilations named by its subproject wrap files. They are not committed.

## Hardware and platform references

- [coffeepot](https://github.com/estyseesghosts/coffeepot) CTR hardware,
  PICA200 and engineering pages (`ctr/hardware/`, `ctr/engineering/`), used
  for hardware budgets, the GPU model and the C style guide.
- libctru, citro3d, citro2d and 3dstools API documentation.

## Not used

- Any leaked source.
- Any ROM, extracted asset, save, capture or game text.
- Any code from a port that bundles game assets.
