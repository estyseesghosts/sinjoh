/*
 * lowermenu.c: the field's lower screen as pokeplatinum-3ds lays it out
 * (docs/REMASTER.md, "The lower screen as a menu").
 *
 *   +--------------------------------------------------------------+
 *   | POKEMON PLATINUM                                             |
 *   |  +------------------------+  +---------------------------+   |
 *   |  |                        |  | [icon] MAP                |   |
 *   |  |   the DS's own lower   |  | [icon] POKEMON            |   |
 *   |  |   screen (Poketch)     |  | [icon] BAG                |   |
 *   |  |   224x168 (15/16)      |  | ...                       |   |
 *   |  +------------------------+  +---------------------------+   |
 *   |                              [item] [item]                   |
 *   +--------------------------------------------------------------+
 *
 * Everything is drawn with the same atlas and the same 2D program as the
 * game's layers: the panel is the 2D interpreter through a view, the chrome
 * is batched vertex-coloured quads, and the font and icons are procedural
 * 4bpp DS tiles converted once into atlas slots. No CPU surface, no texture
 * uploads, no per-frame readback: two fill batches, one tile batch and the
 * panel's own layers per frame.
 */

#include "graphics/menu/lowermenu.h"

#include "diagnostics/log.h"
#include "graphics/g2d/g2d.h"
#include "graphics/pica/targets.h"
#include "graphics/resources/atlas.h"

#include <stdio.h>
#include <string.h>

#define SCREEN KJ_SCREEN_BOTTOM

/* The panel and the button column, in the lower screen's 320x240 pixels. */
#define PANEL_X 7
#define PANEL_Y 29
#define PANEL_W 224 /* the DS's 256 at 15/16 */
#define PANEL_H 168 /* the DS's 192 at 15/16 */
#define BTN_X 238
#define BTN_Y0 26
#define BTN_W 78
#define BTN_H 20
#define BTN_STEP 21
#define BTN_COUNT 8
#define ITEM_Y 203
#define ITEM_W 34

#define RGBA(r, g, b) ((uint32_t)(r) | ((uint32_t)(g) << 8) | ((uint32_t)(b) << 16) | 0xFF000000u)

#define COL_BG RGBA(18, 18, 24)
#define COL_HEADER RGBA(28, 34, 52)
#define COL_BORDER RGBA(88, 96, 120)
#define COL_PANEL RGBA(8, 8, 8)
#define COL_BTN RGBA(40, 44, 56)
#define COL_BTN_SEL RGBA(104, 68, 32)
#define COL_ACCENT RGBA(240, 168, 64)

static bool s_enabled = true; /* the remaster layout (menu.txt "off" disables it) */
static bool s_field_on;        /* the game says the Poketch is the lower screen */
static int s_selection;

/* ------------------------------------------------------------- the font */

/*
 * 5x7 glyphs in the top five bits of an 8-pixel row, centred in an 8x8 DS
 * tile. The order matches GLYPHS.
 */
static const char GLYPHS[] = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./:";
static const uint8_t GLYPH_ROWS[][8] = {
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }, /* space */
    { 0x70, 0x88, 0x88, 0xF8, 0x88, 0x88, 0x88, 0x00 }, /* A */
    { 0xF0, 0x88, 0x88, 0xF0, 0x88, 0x88, 0xF0, 0x00 }, /* B */
    { 0x70, 0x88, 0x80, 0x80, 0x80, 0x88, 0x70, 0x00 }, /* C */
    { 0xE0, 0x90, 0x88, 0x88, 0x88, 0x90, 0xE0, 0x00 }, /* D */
    { 0xF8, 0x80, 0x80, 0xF0, 0x80, 0x80, 0xF8, 0x00 }, /* E */
    { 0xF8, 0x80, 0x80, 0xF0, 0x80, 0x80, 0x80, 0x00 }, /* F */
    { 0x70, 0x88, 0x80, 0xB8, 0x88, 0x88, 0x78, 0x00 }, /* G */
    { 0x88, 0x88, 0x88, 0xF8, 0x88, 0x88, 0x88, 0x00 }, /* H */
    { 0xF8, 0x20, 0x20, 0x20, 0x20, 0x20, 0xF8, 0x00 }, /* I */
    { 0x38, 0x10, 0x10, 0x10, 0x10, 0x90, 0x60, 0x00 }, /* J */
    { 0x88, 0x90, 0xA0, 0xC0, 0xA0, 0x90, 0x88, 0x00 }, /* K */
    { 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0xF8, 0x00 }, /* L */
    { 0x88, 0xD8, 0xA8, 0xA8, 0x88, 0x88, 0x88, 0x00 }, /* M */
    { 0x88, 0xC8, 0xA8, 0x98, 0x88, 0x88, 0x88, 0x00 }, /* N */
    { 0x70, 0x88, 0x88, 0x88, 0x88, 0x88, 0x70, 0x00 }, /* O */
    { 0xF0, 0x88, 0x88, 0xF0, 0x80, 0x80, 0x80, 0x00 }, /* P */
    { 0x70, 0x88, 0x88, 0x88, 0xA8, 0x90, 0x68, 0x00 }, /* Q */
    { 0xF0, 0x88, 0x88, 0xF0, 0xA0, 0x90, 0x88, 0x00 }, /* R */
    { 0x78, 0x80, 0x80, 0x70, 0x08, 0x08, 0xF0, 0x00 }, /* S */
    { 0xF8, 0x20, 0x20, 0x20, 0x20, 0x20, 0x20, 0x00 }, /* T */
    { 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x70, 0x00 }, /* U */
    { 0x88, 0x88, 0x88, 0x88, 0x88, 0x50, 0x20, 0x00 }, /* V */
    { 0x88, 0x88, 0x88, 0xA8, 0xA8, 0xD8, 0x88, 0x00 }, /* W */
    { 0x88, 0x88, 0x50, 0x20, 0x50, 0x88, 0x88, 0x00 }, /* X */
    { 0x88, 0x88, 0x50, 0x20, 0x20, 0x20, 0x20, 0x00 }, /* Y */
    { 0xF8, 0x08, 0x10, 0x20, 0x40, 0x80, 0xF8, 0x00 }, /* Z */
    { 0x70, 0x88, 0x98, 0xA8, 0xC8, 0x88, 0x70, 0x00 }, /* 0 */
    { 0x20, 0x60, 0x20, 0x20, 0x20, 0x20, 0x70, 0x00 }, /* 1 */
    { 0x70, 0x88, 0x08, 0x30, 0x40, 0x80, 0xF8, 0x00 }, /* 2 */
    { 0xF8, 0x10, 0x20, 0x10, 0x08, 0x88, 0x70, 0x00 }, /* 3 */
    { 0x10, 0x30, 0x50, 0x90, 0xF8, 0x10, 0x10, 0x00 }, /* 4 */
    { 0xF8, 0x80, 0xF0, 0x08, 0x08, 0x88, 0x70, 0x00 }, /* 5 */
    { 0x30, 0x40, 0x80, 0xF0, 0x88, 0x88, 0x70, 0x00 }, /* 6 */
    { 0xF8, 0x08, 0x10, 0x20, 0x40, 0x40, 0x40, 0x00 }, /* 7 */
    { 0x70, 0x88, 0x88, 0x70, 0x88, 0x88, 0x70, 0x00 }, /* 8 */
    { 0x70, 0x88, 0x88, 0x78, 0x08, 0x10, 0x60, 0x00 }, /* 9 */
    { 0x00, 0x00, 0x00, 0x70, 0x00, 0x00, 0x00, 0x00 }, /* - */
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x60, 0x60, 0x00 }, /* . */
    { 0x08, 0x10, 0x10, 0x20, 0x40, 0x40, 0x80, 0x00 }, /* / */
    { 0x00, 0x60, 0x60, 0x00, 0x60, 0x60, 0x00, 0x00 }, /* : */
};

/* The eight buttons, in order. */
static const char *const LABELS[BTN_COUNT] = { "MAP",   "POKEMON", "BAG",     "TRAINER",
                                               "POKEDEX", "POKETCH", "SAVE", "OPTIONS" };

/* 8x8 button icons: map, Poké Ball, bag, trainer, Pokédex, Pokétch, save,
 * options. */
static const uint8_t ICONS[BTN_COUNT][8] = {
    { 0x00, 0x7C, 0x44, 0x54, 0x44, 0x7C, 0x00, 0x00 }, /* map */
    { 0x3C, 0x7E, 0xFF, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C }, /* ball */
    { 0x18, 0x3C, 0x66, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C }, /* bag */
    { 0x18, 0x18, 0x7E, 0xFF, 0x7E, 0x3C, 0x66, 0x66 }, /* trainer */
    { 0x7E, 0x42, 0x7E, 0x42, 0x7E, 0x42, 0x7E, 0x00 }, /* dex */
    { 0x3C, 0x42, 0x99, 0xA1, 0xA1, 0x99, 0x42, 0x3C }, /* poketch */
    { 0xFF, 0x81, 0xBD, 0xBD, 0x81, 0xB5, 0x81, 0xFF }, /* save */
    { 0x24, 0x7E, 0xFF, 0xDB, 0xDB, 0xFF, 0x7E, 0x24 }, /* options */
};

#define GLYPH_COUNT ((int)(sizeof(GLYPHS) - 1))
static uint8_t s_glyph_tiles[sizeof(GLYPHS) - 1][32];
static uint8_t s_icon_tiles[BTN_COUNT][32];
static bool s_tiles_built;

/* Index 1 is the glyph's ink; index 0 is transparent (the atlas clears
 * alpha for palette entry 0). */
static uint16_t s_palette_colors[16] = { 0x0000, 0x7FFF };
static kj_palette s_pal = { .colors = s_palette_colors, .count = 16 };

/* ------------------------------------------------------------ the tiles */

/* A DS 4bpp tile from an 8x8 bitmap: two pixels per byte, low nibble first. */
static void expand_tile(uint8_t out[32], const uint8_t rows[8])
{
    memset(out, 0, 32);
    for (int r = 0; r < 8; ++r) {
        for (int c = 0; c < 8; ++c) {
            if (rows[r] & (0x80u >> c)) {
                out[r * 4 + c / 2] |= (uint8_t)(1u << ((c & 1) * 4));
            }
        }
    }
}

static void build_tiles(void)
{
    if (s_tiles_built) {
        return;
    }
    for (int i = 0; i < GLYPH_COUNT; ++i) {
        expand_tile(s_glyph_tiles[i], GLYPH_ROWS[i]);
    }
    for (int i = 0; i < BTN_COUNT; ++i) {
        expand_tile(s_icon_tiles[i], ICONS[i]);
    }
    s_tiles_built = true;
}

static uint16_t glyph_slot(int g)
{
    kj_palette_check(&s_pal);
    const kj_tile_ref t =
        kj_atlas_tile(0xF2u, s_glyph_tiles[g], (uint32_t)g, false, &s_pal, 0xF201u);
    return (t.valid && !t.transparent) ? t.slot : (uint16_t)0xFFFF;
}

static uint16_t icon_slot(int i)
{
    kj_palette_check(&s_pal);
    const kj_tile_ref t =
        kj_atlas_tile(0xF3u, s_icon_tiles[i], (uint32_t)i, false, &s_pal, 0xF202u);
    return (t.valid && !t.transparent) ? t.slot : (uint16_t)0xFFFF;
}

static int glyph_index(char ch)
{
    if (ch >= 'a' && ch <= 'z') {
        ch = (char)(ch - 'a' + 'A');
    }
    const char *p = strchr(GLYPHS, ch);
    return p != NULL ? (int)(p - GLYPHS) : 0;
}

static void push_text(kj_g2d_tile_rect *tiles, int *count, int x, int y, const char *text)
{
    for (; *text != '\0'; ++text, x += 8) {
        const int g = glyph_index(*text);
        if (g == 0) {
            continue;
        }
        const uint16_t slot = glyph_slot(g);
        if (slot == (uint16_t)0xFFFF) {
            continue;
        }
        tiles[(*count)++] = (kj_g2d_tile_rect){ x, y, x + 8, y + 8, slot };
    }
}

/* --------------------------------------------------------------- public */

bool kj_lowermenu_init(const char *root)
{
    build_tiles();
    s_selection = 0;
    s_field_on = false;

    /* The game turns the menu on and off where the DS's lower screen is the
     * field's (the Poketch's bottom-screen handlers); this file only lets a
     * run opt out for comparison. */
    char path[160];
    snprintf(path, sizeof(path), "%s/menu.txt", root);
    FILE *f = fopen(path, "r");
    if (f != NULL) {
        char line[16] = { 0 };
        if (fgets(line, sizeof(line), f) != NULL &&
            (strncmp(line, "off", 3) == 0 || strncmp(line, "0", 1) == 0)) {
            s_enabled = false;
        }
        fclose(f);
    }
    kj_log("[menu] lower-screen field menu %s (%s)", s_enabled ? "enabled" : "off", path);
    return true;
}

bool kj_lowermenu_active(void)
{
    return s_enabled && s_field_on;
}

void kj_lowermenu_set_active(bool on)
{
    if (s_field_on != on) {
        kj_log("[menu] field lower screen %s", on ? "on" : "off");
    }
    s_field_on = on;
}

void kj_lowermenu_set_selection(int index)
{
    if (index < 0) {
        index = 0;
    }
    if (index >= BTN_COUNT) {
        index = BTN_COUNT - 1;
    }
    s_selection = index;
}

int kj_lowermenu_selection(void)
{
    return s_selection;
}

void kj_lowermenu_draw(const kj_frame_input *in, int engine)
{
    if (!kj_lowermenu_active()) {
        return;
    }

    /* Chrome first: one fill batch. */
    kj_g2d_rect fills[24];
    int nf = 0;
    fills[nf++] = (kj_g2d_rect){ 0, 0, 320, 240, COL_BG };
    fills[nf++] = (kj_g2d_rect){ 0, 0, 320, 24, COL_HEADER };
    fills[nf++] = (kj_g2d_rect){ PANEL_X - 2, PANEL_Y - 2, PANEL_X + PANEL_W + 2,
                                PANEL_Y + PANEL_H + 2, COL_BORDER };
    fills[nf++] = (kj_g2d_rect){ PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H,
                                COL_PANEL };
    for (int i = 0; i < BTN_COUNT; ++i) {
        const int y = BTN_Y0 + i * BTN_STEP;
        fills[nf++] = (kj_g2d_rect){ BTN_X, y, BTN_X + BTN_W, y + BTN_H,
                                     i == s_selection ? COL_BTN_SEL : COL_BTN };
        if (i == s_selection) {
            fills[nf++] = (kj_g2d_rect){ BTN_X, y, BTN_X + 3, y + BTN_H, COL_ACCENT };
        }
    }
    for (int i = 0; i < 2; ++i) {
        const int x = BTN_X + i * (ITEM_W + 4);
        fills[nf++] = (kj_g2d_rect){ x, ITEM_Y, x + ITEM_W, ITEM_Y + ITEM_W, COL_BORDER };
        fills[nf++] = (kj_g2d_rect){ x + 2, ITEM_Y + 2, x + ITEM_W - 2, ITEM_Y + ITEM_W - 2,
                                     COL_BTN };
    }
    kj_g2d_fill_rects(SCREEN, fills, nf);

    /* The DS's own lower screen (the Poketch in the field) inside the panel,
     * at 15/16 of its size: the same 2D interpreter, a smaller view. */
    const kj_g2d_view panel = { (float)PANEL_W / 256.0f,
                                (float)PANEL_H / 192.0f,
                                (float)PANEL_X,
                                (float)PANEL_Y,
                                PANEL_X,
                                PANEL_Y,
                                PANEL_X + PANEL_W,
                                PANEL_Y + PANEL_H };
    kj_screen_draw_view(SCREEN, engine, in, &panel);

    /* Text and icons: one tile batch over everything. */
    kj_g2d_tile_rect tiles[128];
    int nt = 0;
    push_text(tiles, &nt, 8, 8, "POKEMON PLATINUM");
    for (int i = 0; i < BTN_COUNT; ++i) {
        const int y = BTN_Y0 + i * BTN_STEP;
        const uint16_t icon = icon_slot(i < BTN_COUNT ? i : 0);
        if (icon != (uint16_t)0xFFFF) {
            tiles[nt++] = (kj_g2d_tile_rect){ BTN_X + 4, y + 6, BTN_X + 12, y + 14, icon };
        }
        push_text(tiles, &nt, BTN_X + 16, y + 6, LABELS[i]);
    }
    /* Registered items: a Poké Ball and the bag. */
    const uint16_t reg_a = icon_slot(1), reg_b = icon_slot(2);
    if (reg_a != (uint16_t)0xFFFF) {
        tiles[nt++] = (kj_g2d_tile_rect){ BTN_X + 9, ITEM_Y + 9, BTN_X + 25, ITEM_Y + 25,
                                          reg_a };
    }
    if (reg_b != (uint16_t)0xFFFF) {
        tiles[nt++] = (kj_g2d_tile_rect){ BTN_X + ITEM_W + 13, ITEM_Y + 9, BTN_X + ITEM_W + 29,
                                          ITEM_Y + 25, reg_b };
    }
    kj_g2d_tiles(SCREEN, tiles, nt);
}
