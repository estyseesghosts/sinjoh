from pathlib import Path

p = Path(r"C:\Users\terezi\workdir\sinjoh\build\upstream\src\system.c")
t = p.read_text(encoding="utf-8")
if "DIAG touch" not in t:
    needle = '#include "system.h"\n'
    insert = needle + '\n#ifdef SDK_PORT_3DS\n/* DIAG touch: temporary debugging line */\nextern void NitroPort_Log(const char *, ...);\n#endif\n'
    t = t.replace(needle, insert, 1)
    needle2 = "    gSystem.touchPressed = (u16)(tp.touch & (tp.touch ^ gSystem.touchHeld));\n"
    insert2 = needle2 + '#ifdef SDK_PORT_3DS\n    if (gSystem.touchPressed) NitroPort_Log("[game] touch down %u,%u raw %u,%u valid %d", gSystem.touchX, gSystem.touchY, tpRaw.x, tpRaw.y, (int)tp.validity);\n#endif\n'
    t = t.replace(needle2, insert2, 1)
    p.write_text(t, encoding="utf-8")
    print("patched")
else:
    print("already")
