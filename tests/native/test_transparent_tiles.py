"""Exercise the production retained BG/OBJ code with a host atlas stub.

Run with a host C compiler on PATH: python tests/native/test_transparent_tiles.py
The 3DS GPU is not exercised; the atlas stub distinguishes blank tiles and
models an atlas-full result so the retained-cache decisions can be checked.
"""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "engine/graphics/g2d/g2d.c").read_text(encoding="utf-8")


def section(start, end):
    return SOURCE[SOURCE.index(start):SOURCE.index(end, SOURCE.index(start))]


def function(signature):
    start = 0
    while True:
        start = SOURCE.index(signature, start)
        opening = SOURCE.index("{", start)
        semicolon = SOURCE.find(";", start, opening)
        if semicolon == -1:
            break
        start = semicolon + 1
    depth = 1
    pos = opening + 1
    while depth:
        if SOURCE[pos] == "{":
            depth += 1
        elif SOURCE[pos] == "}":
            depth -= 1
        pos += 1
    return SOURCE[start:pos] + "\n"


PREAMBLE = r'''
#include "runtime/kj_bridge.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int unused; } kj_target;
typedef struct { int16_t x,y,u,v; uint8_t r,g,b,a; } kj_v2d;
typedef struct { const uint16_t *colors; uint16_t count; } kj_palette;
typedef struct { uint16_t slot; uint8_t transparent, valid; } kj_tile_ref;
typedef struct { unsigned dropped_quads, unsupported_modes; } kj_g2d_stats;
static int atlas_full;
static void kj_palette_check(kj_palette *p) { (void)p; }
static kj_tile_ref kj_atlas_tile(uint32_t source, const uint8_t *p, uint32_t off,
                                 bool bpp8, kj_palette *pal, uint32_t pal_id)
{
    (void)source; (void)pal; (void)pal_id;
    bool blank = true;
    for (unsigned i = 0; i < (bpp8 ? 64u : 32u); ++i) {
        if (p[i]) { blank = false; }
    }
    kj_tile_ref result = { (uint16_t)(off / 32 + 1), blank, !atlas_full || blank };
    return result;
}
static void kj_atlas_slot_uv(uint16_t slot, int16_t *u0, int16_t *v0,
                             int16_t *u1, int16_t *v1)
{
    *u0 = *v0 = *u1 = *v1 = (int16_t)slot;
}
static kj_v2d *kj_gpu_quads_alloc(uint32_t n, uint32_t *first)
{ (void)n; (void)first; return NULL; }
static void kj_gpu_quads_reset_to(uint32_t n) { (void)n; }
static void *linearAlloc(size_t n) { return malloc(n); }
static int kj_wideart_count(void) { return 0; }
'''

BODY = [
    section("enum {\n    PAL_4BPP", "/* ------------------------------------------------------------ registers */"),
    section("static uint16_t r16", "/* ------------------------------------------------------------ quad emit */"),
    section("static inline void put_quad", "/* ------------------------------------------------------------ text BGs */"),
    function("static uint32_t text_bg("),
    section("static const uint8_t OBJ_W", "/* Emit the OBJs"),
    function("static uint32_t objs("),
    section("typedef struct drawable", "} drawable;") + "} drawable;\n",
    section("#define CACHE_QUADS", "typedef struct screen_memo"),
    "static uint32_t s_reused_layers, s_rebuilt_layers;\n",
    function("static bool cache_alloc("),
    "static uint32_t s_char_bytes_compared;\n",
    function("static bool chars_same("),
    function("static void chars_keep("),
    function("static void text_key("),
    function("static void text_map_range("),
    function("static const uint8_t *text_ext_src("),
    "static uint64_t bg_art_key(const ctx *c, int bg) { (void)c; (void)bg; return 0; }\n",
    function("static bool text_bg_retained("),
    function("static bool objs_retained("),
]

TEST = r'''
static uint8_t palettes[0x800], oam[0x800], regs[0x70];
static uint8_t bg[0x80000], obj[0x40000], lcdc[0xA4000];

static void write16(uint8_t *p, uint16_t v) { p[0] = v; p[1] = v >> 8; }

static void exercise(int engine)
{
    memset(palettes, 0, sizeof(palettes));
    memset(oam, 0, sizeof(oam));
    memset(regs, 0, sizeof(regs));
    memset(bg, 0, sizeof(bg));
    memset(obj, 0, sizeof(obj));
    for (int e = 0; e < 2; ++e) {
        for (int i = 0; i < 128; ++i) { write16(oam + e * 0x400 + i * 8, 0x200); }
    }
    kj_ds_memory mem = { .pltt = palettes, .oam = oam, .lcdc_vram = lcdc };
    kj_frame_input input = { .mem = &mem };
    ctx c = { .in = &input, .engine = engine, .regs = regs,
              .bg_vram = bg, .bg_vram_size = engine ? 0x20000 : 0x80000,
              .obj_vram = obj, .obj_vram_size = engine ? 0x20000 : 0x40000,
              .y0 = 0, .y1 = 192 };
    drawable draw, sub[8];
    uint64_t art_key;
    unsigned before;

    /* Map every visible BG position to a blank tile outside the map. */
    write16(regs + 8, 0x0100);
    for (int i = 0; i < 1024; ++i) { write16(bg + 0x800 + i * 2, 7); }
    s_bg_cache[engine][0].slots[0] = 0xffff;
    before = s_rebuilt_layers;
    assert(text_bg_retained(&c, 0, &draw, &art_key) && draw.count == 0);
    assert(s_bg_cache[engine][0].slots[0] == 0xffff);
    assert(s_rebuilt_layers == before + 1);
    assert(text_bg_retained(&c, 0, &draw, &art_key) && draw.count == 0);
    assert(s_rebuilt_layers == before + 1);
    bg[7 * 32] = 1;
    assert(text_bg_retained(&c, 0, &draw, &art_key) && draw.count == 32 * 24);
    assert(s_rebuilt_layers == before + 2);
    assert(s_bg_cache[engine][0].slots[0] == 8);
    assert(text_bg_retained(&c, 0, &draw, &art_key));
    assert(s_rebuilt_layers == before + 2);
    palettes[engine * 0x400 + 2] = 1;
    assert(text_bg_retained(&c, 0, &draw, &art_key));
    assert(s_rebuilt_layers == before + 3);
    bg[7 * 32] = 0;
    assert(text_bg_retained(&c, 0, &draw, &art_key) && draw.count == 0);
    bg[7 * 32] = 1;
    atlas_full = 1;
    assert(text_bg_retained(&c, 0, &draw, &art_key) && draw.count == 0);
    assert(!s_bg_cache[engine][0].valid);
    atlas_full = 0;
    assert(text_bg_retained(&c, 0, &draw, &art_key) && draw.count == 32 * 24);

    /* An all-blank priority group must still contribute its watched range. */
    uint8_t *sprite = oam + engine * 0x400;
    write16(sprite, 0);
    write16(sprite + 2, 0);
    write16(sprite + 4, 7);
    s_obj_cache[engine].slots[0] = 0xffff;
    before = s_rebuilt_layers;
    assert(objs_retained(&c, sub) && sub[0].count == 0);
    assert(s_obj_cache[engine].slots[0] == 0xffff);
    assert(objs_retained(&c, sub) && sub[0].count == 0);
    assert(s_rebuilt_layers == before + 1);
    obj[7 * 32] = 1;
    assert(objs_retained(&c, sub) && sub[0].count == 1);
    assert(s_rebuilt_layers == before + 2);
    assert(s_obj_cache[engine].slots[0] == 8);
    assert(objs_retained(&c, sub) && s_rebuilt_layers == before + 2);
    palettes[engine * 0x400 + 0x202] = 1;
    assert(objs_retained(&c, sub) && s_rebuilt_layers == before + 3);
    obj[7 * 32] = 0;
    assert(objs_retained(&c, sub) && sub[0].count == 0);

    /* Allocation failure must not retain an incomplete picture forever. */
    obj[7 * 32] = 1;
    atlas_full = 1;
    assert(objs_retained(&c, sub) && sub[0].count == 0);
    assert(!s_obj_cache[engine].valid);
    atlas_full = 0;
    assert(objs_retained(&c, sub) && sub[0].count == 1);
    assert(s_obj_cache[engine].valid);
}

int main(void)
{
    exercise(0);
    exercise(1);
    puts("transparent tile retained-cache checks passed");
    return 0;
}
'''


def main():
    compiler = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc")
    if not compiler:
        raise SystemExit("A host C compiler (cc or gcc) is required")
    with tempfile.TemporaryDirectory(prefix="sinjoh-tiles-") as directory:
        path = Path(directory)
        source = path / "transparent_tiles.c"
        executable = path / "transparent_tiles"
        source.write_text(PREAMBLE + "\n".join(BODY) + TEST, encoding="utf-8")
        subprocess.run([compiler, "-std=c11", "-O0", "-I", str(ROOT / "engine"),
                        str(source), "-lm", "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
