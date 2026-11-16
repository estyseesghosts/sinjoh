#ifndef KJ_GRAPHICS_MENU_LOWERMENU_H
#define KJ_GRAPHICS_MENU_LOWERMENU_H

#include "runtime/kj_bridge.h"

#include <stdbool.h>

/*
 * The field's lower screen: pokeplatinum-3ds's remaster layout, drawn as
 * GPU quads instead of a CPU surface (REMASTER.md, "The lower screen as a
 * menu"): on the left a panel with the DS's own lower screen in it (the
 * Poketch in the field), on the right a column of eight buttons with their
 * icons and names, and two squares for the registered items.
 *
 * Engine side only: the panel reuses the 2D interpreter with a view, and
 * the chrome and the small font are procedural DS tiles in the same atlas
 * the game's layers use, so nothing is converted or uploaded per frame.
 */

/* `root` is the program's data root (sdmc:/3ds/sinjoh). The layout is on;
 * <root>/menu.txt containing "off" disables it for comparison. The game
 * turns it on and off where the Poketch is the field's lower screen
 * (patches/pokeplatinum/0012), so nothing else shows it. */
bool kj_lowermenu_init(const char *root);

bool kj_lowermenu_active(void);
void kj_lowermenu_set_active(bool on);

/* Which button the cursor is on (0..7, or -1 for none: the start menu is
 * closed). The game drives it from its own cursor. */
void kj_lowermenu_set_selection(int index);
int kj_lowermenu_selection(void);

/* Which of the eight buttons can be used, a bit each, as the game's start
 * menu says; the rest are drawn dimmed and ignore taps. */
void kj_lowermenu_set_buttons(uint32_t mask);
uint32_t kj_lowermenu_buttons(void);

/* A tap on a button, as that button's index (-1 for none). The game takes
 * it (clearing it) from its field input or its start menu; pending peeks
 * without clearing, so a tap can open the menu on that button. */
int kj_lowermenu_take_press(void);
int kj_lowermenu_press_pending(void);

/* Draw the whole lower screen: chrome, the DS engine's display in the
 * panel, and the buttons. Called instead of kj_screen_draw for the bottom
 * screen while the menu is on. */
void kj_lowermenu_draw(const kj_frame_input *in, int engine);

#endif
