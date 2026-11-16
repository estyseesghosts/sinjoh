# Status

Verified 2026-11-16, Old 3DS profile in Azahar 2126.2. "Implemented",
"built", "ran" and "verified" are separate facts; this file keeps them apart.

## 2026-11-16 second pass

- **The missing title gradient was a blend-order bug, not data.** The
  copyright screen is BG1 (first target, EVA 0 -> 16/16) over BG3 (second
  target, EVB 16/16): result = BG1*EVA + BG3. Alpha blending is two draws.
  The blended draw ran first and inverted stencil bit 0 for a layer that is
  not a second target; the following opaque draw tested bit 0, saw the
  inverted value and redrew the layer opaquely over the blend. Any
  full-screen first target with EVA > 0 therefore replaced everything under
  it, which is why BG3's gradient vanished as BG1 faded in. Swapping the two
  passes (opaque where bit 0 is clear, then blended where it is set) keeps
  the same stencil ops correct. Verified against melonDS on the copyright
  screen at game frames 30 and 120; the top screen now shows BG3 and the
  25%/94% BG1 fade.
- The same bug flattened any scene with a full-screen first target, which is
  the most likely source of the reported washed-out/over-bright field: the
  picture was replaced by the overlay's colour. No gamma or palette change
  was made, and none is needed: the 2D palette expands exactly as it did.
- The 3D wide view is implemented (g3d.c) and reference-exact; still not
  exercised in an outdoor 3D scene.
- The start menu is the lower menu (patch 0013, engine API): built and
  checked visually. Tap routing and every app are not yet exercised.

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
- The lower-screen field menu, engine side and game side:
  - `engine/graphics/menu/lowermenu.c`: pokeplatinum-3ds's remaster layout
    (`REMASTER.md`, "The lower screen as a menu") as GPU quads: a panel with
    the DS's own lower screen at 15/16 (the Poketch, or the Poké Ball before
    the player has one), a column of eight buttons with icons and names, and
    two registered-item squares. The panel is the 2D interpreter through a
    view (`kj_screen_draw_view`); the chrome is one batch of tinted white
    atlas tiles, the font and icons are procedural 4bpp DS tiles in the same
    atlas as the game's layers. No CPU surface, no per-frame texture work.
  - `patches/pokeplatinum/0012`: the Poketch's bottom-screen handlers turn
    the menu on in their init and off in their end (pokeplatinum-3ds patch
    0031's hook points), so the title sequence, opening, battles, underground
    and Union Room keep the DS's lower screen.
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
- Lower-screen menu gated by the game (`build/azahar/glue1`, `titlecheck`):
  loading the real save reaches the field and logs
  `11.622 [menu] field lower screen on`; the held field capture shows the
  panel with the DS's lower screen (the Poké Ball: this save has no
  Pokétch), the eight buttons and the two registered-item squares. The same
  build's title capture (`t005`, `t010`) shows the copyright screen and the
  DS's ESRB lower screen with no menu chrome, and its log has no
  `field lower screen on` line.
- The menu's chrome renders (`build/azahar/chrome1`, `chrome_title`): the
  field capture's panel border is `(88,96,120)` and its buttons `(40,44,56)`
  at the laid-out pixels, with the selected button `(104,68,32)` and its
  accent bar `(240,168,64)`; the title capture has zero pixels of the
  border colour.
- The chrome is drawn as tinted atlas tiles because the 2D engine's
  untextured `REPLACE(PRIMARY)` batch draws nothing in Azahar while the
  textured tile path draws. GDB on the fill batch: `C3D_DrawElements` is
  called with 102 indices (17 quads), vertices
  `(0,0)(320,0)(0,240)(320,240)` colour `18,18,24,255`, the 2D arena as
  vertex buffer (stride 12, 3 attributes, permutation 0x210), TEV stage 0
  `REPLACE(PRIMARY)`, cull none, full scissor, 320x240 viewport. The batch
  stays invisible with the TEV constant, with the atlas bound, with alpha
  test and depth state identical to the working tile batch, with non-zero
  UVs, and as the last draw of the frame. The menu therefore uses the
  textured path; `kj_g2d_fill_rects` remains for screen clearing only.
- `PROFILE=1` field run (`build/azahar/perf1`, 130 s, no freeze so the
  publish loop keeps running; the field and the menu are up from 11.6 s).
  Windows 2-5 are steady field state, 600 publishes each:

  | stage | p50 | p95 | p99 | max |
  |---|---|---|---|---|
  | logic | 3162-3167 | 4302-4365 | 5273-5525 | 6908-7531 |
  | publish | 1507 | 2549-2721 | 2745-2811 | 2778-2885 |
  | g2d | 364 | 454 | 1499-1593 | 1627-1697 |
  | g3d | 603 | 693 | 1724-1855 | 1873-1942 |
  | submit | 294 | 346-353 | 1298-1512 | 1552-1672 |
  | gpu_wait | 3 | 3 | 3 | 3-93 |

  (microseconds; logic and active include preemption and exclude the
  V-blank wait). Active logic+publish p50 4685-4688, p99 6780-7033. Frame
  time p50 33441 us, p99 34633-34680. Emulated publish interval p50 and max
  2 V-blanks, 0 deadline misses, 0 skipped presents, 0 hitches in every
  steady window. Window 1 covers boot and the opening: max logic 190 ms at
  frames 2-195, i.e. transitions, not steady state. That build's chrome was
  the untextured fill batch (one draw, 17 quads); the tinted-tile chrome is
  also one draw and the same quads, so the stage costs stand.

## Verified facts

- Bootstrap: 3 checkouts and 44 patches (12 pokeplatinum, 27 NitroSDK, 5
  NitroSystem).
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
  authority: its O3DS profile does not model instruction cache, service-core
  contention, SD stalls or VRAM hazards, so the field numbers above are
  `AZAHAR_PASS` only.
- The measurement covers one interior field scene (the player's room, via the
  real save). The acceptance corpus wants the worst-case outdoor scenes and a
  10-minute run; neither exists yet.
- The 3D wide camera is unverified in the field. The lower-screen start menu
  is built and drawn; its tap routing and every app it can open still need a
  run through, and the panel apps (map, bag, party, trainer case) are absent.
- The screens pokeplatinum-3ds lays out in parts are not implemented.

## Next

1. 3D wide view: verify the enabled box test in a 3D field scene; the
   projection's clip x scaled by 0.8 and the top target's fixup mapping the
   DS's 256-pixel clip range across 400 px (320 DS px visible), gated on the
   top screen; the reference's `NitroPort_Gx3dSetWideView(320)`.
2. The start menu as the lower menu (reference patch 0032): the cursor is
   the lower screen's buttons, its window and icons hidden, its task still
   opening the apps. Built; exercise a tap on each usable button, the
   cursor's wrap, and every app's return.
3. Measure the worst-case scenes (outdoor routes, battle) the same way, then
   a 10-minute steady run. The interior field has ~28 ms of headroom per
   frame, so cost removal there is not justified by data.
