# Status

Verified 2026-11-16, Old 3DS profile in Azahar 2126.2. "Implemented",
"built", "ran" and "verified" are separate facts; this file keeps them apart.

## Implemented

- New repository layout: `engine/` (kohjoh's runtime and renderer),
  `tools/game/` (bootstrap, source inventory), `tools/wideart/` (package-time
  picture packer), `wideart/` (hand-drawn band sources).
- `tools/game/bootstrap.py`: fetches `pret/pokeplatinum` at `c248fb3` and the
  NitroSDK/NitroSystem decompilations at the revisions in its subproject wrap
  files; applies `patches/{pokeplatinum,NitroSDK,NitroSystem}` when present.
- `tools/game/platinum_sources.py`, `platinum_lsf.py`, `game_overlays.py`:
  the game's meson `files()` lists and `main.lsf` become the object list,
  overlay map and overlay table.
- Wide art, end to end:
  - `tools/wideart/pack_wideart.py` decodes the pictures, cuts both bands,
    converts to RGBA5551, places them in the PICA's Morton/tile order and
    writes one blob (header, table, texture). Nothing is decoded or
    converted on the console.
  - `engine/graphics/g2d/wideart.c` parses the blob, uploads a 512x1024
    texture (the 576 rows the pictures use) and looks a layer's picture up
    by its art key, nearest to the layer's scroll.
  - `engine/graphics/g2d/g2d.c`: `bg_art_key()` is pokeplatinum-3ds's
    `BgKey` (FNV-1a over kind, tile size, map entries, the used tiles and
    their palettes, `PlttColor & 0x7FFF`), so the pictures' names match.
  - `edge_band_quads()`: the band's fallback when no picture covers it. Per
    8-line row, the layer's edge tile is sampled at the screen's edge column
    and stretched across the 32-pixel band (pokeplatinum-3ds's "a plain edge
    goes on"). Atlas quads only, at most 48 per layer.
  - The 2D scissor is the whole target, so bands and pictures can draw
    beside the DS's picture; the DS's own quads still stay inside it.
- `tools/build.ps1` builds through devkitPro's MSYS2 shell; `engine/game.mk`
  converts response-file paths with `cygpath -w -m -f`, so the repo builds
  from any MSYS2 mount (`/home/<user>` included).

## Built

- `engine/compat/nitro` (libnitro.a) and `engine/compat/nitrosystem`
  (libnitrosystem.a) for ARM11, from the pinned decompilations and their
  patch stacks.
- The whole game: 1012 of 1012 game C sources, libcrypto/libgds/libspl, the
  trainer AI script, the Wi-Fi stand-ins, the overlay table and overlay IDs.
  `build/game/3ds/libplatinum_game.a` and `build/game/3ds/sinjoh.3dsx` link.
- A data pack from the user's own Rev 1 dump: 340 NitroFS files,
  `build/platinum.pak` (about 100 MB). Never committed.

## Ran

- sinjoh boots in Azahar 2126.2 with the O3DS profile
  (`is_new_3ds=false`, 100% CPU, OpenGL renderer): copyright, Game Freak
  opening, title, professor intro, name entry.
- GDB (Azahar's stub, port 24689) proves the band path: `draw_band` is
  entered with `count=2`, `screen=0`, `engine=1`, target `400x240`,
  `scale=1.250000`, `off=40.000000`; the left band's first vertex is
  `x=-32, y=0, u=3073, v=3073` and the right band's `x=256`, i.e. the
  picture's band at texture texel (192,192)/(224,192) — `6d5a3d55`'s
  record in the blob.
- Edge fill verified in a capture of the opening (`build/azahar/wideart10`):
  the top screen is 400 px with the DS's picture at 320; the band columns
  0..40 and 360..400 carry the picture's edge colour, row for row, e.g.
  band `(82,33,33)` at rows 200..500 against the DS edge's `(82,33,33)`.
  The white bars (the target clear colour, palette entry 0) are gone.

## Verified facts

- Bootstrap: 3 checkouts, 0 patches (the sinjoh stacks are not written yet).
- Source inventory: 1042 meson sources; 1014 linker objects across 125
  sections (Static main, 2 autoloads, 122 overlays); 1012 mapped; the two
  unmapped entries are `libos.a` and `trainer_ai_script.o`.
- Wide art's art key is bit-exact with pokeplatinum-3ds: live layer keys
  during the opening are `c348e56dbb30d48a` and `6d5a3d55615351bf`, two of
  the 24 picture names.
- The packed texture matches the source PNGs texel for texel: `6d5a3d55`'s
  left band at (192,192) is `0x739b, 0x0000, 0x739b, ...`, exactly the PNG's
  row 0 after `rgba5551()`.
- The pictures are sparse overlays: `6d5a3d55`'s bands are the alpha-64
  marker (transparent) except the 1-px grey border at rows 0 and 191. The
  marker means "the game's own pixel belongs here"; the port must supply it
  with the edge rule (above) or the map continuation.

## Not verified

- No real-O3DS run. Azahar is an integration debugger, not a timing
  authority.
- No frame-time measurement of the shipping path yet (the perf ring exists,
  `PROFILE=1`).
- The 3D wide camera, the lower-screen field menu, and the screens
  pokeplatinum-3ds lays out in parts are not implemented.

## Next

1. 3D wide view: the projection's clip x scaled by 0.8 and the top target's
   fixup mapping the DS's 256-pixel clip range across 400 px (320 DS px
   visible), gated on the top screen; the reference's
   `NitroPort_Gx3dSetWideView(320)`.
2. Lower-screen field menu (`engine` + game glue), following
   pokeplatinum-3ds's `port_lowermenu.c` contract but with the menu drawn as
   GPU quads from an atlas, not a CPU surface.
3. Measure: `PROFILE=1` run of the field, read the perf ring; remove the
   costs that show up (atlas rebuilds, per-frame texture binds).
