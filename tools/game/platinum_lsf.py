#!/usr/bin/env python3
"""Normalize pokeplatinum's linker spec for the kohjoh/ sinjoh overlay tools.

`platinum.us/main.lsf` names objects the way Meson mangles them
(`main.nef.p/src_battle_battle_main.c.o`). kohjoh's `game_overlays.py` expects
checkout paths (`src/battle/battle_main.c.o`) because that is how HGSS's spec
names them. This tool rewrites the spec into that shape using the actual meson
source inventory, leaving genuinely generated objects (trainer_ai_script.o)
and library lines untouched.

Usage:
    python tools/game/platinum_lsf.py --root build/upstream --out build/lsf/normalized.lsf
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import platinum_sources as ps  # noqa: E402


def normalize(root: Path) -> tuple[str, dict[str, int]]:
    sources, _ = ps.meson_sources(root)
    index = ps.build_index(sources)
    lsf = root / "platinum.us" / "main.lsf"
    if not lsf.is_file():
        sys.exit(f"{lsf} not found; run tools/game/bootstrap.py first")
    text = lsf.read_text(encoding="utf-8", errors="replace")
    stats = {"mapped": 0, "kept": 0, "libraries": 0}
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^Object\s+(\S+)(\s+\([^)]*\))?$", line)
        if not m:
            if line.startswith("Library "):
                stats["libraries"] += 1
            out.append(raw)
            continue
        obj, section = m.group(1), m.group(2) or ""
        source = ps.object_source(obj, index)
        if source is None:
            stats["kept"] += 1
            out.append(raw)
        else:
            stats["mapped"] += 1
            out.append(f"\tObject {source}.o{section}")
    return "\n".join(out) + "\n", stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("build/upstream"))
    ap.add_argument("--out", type=Path, default=Path("build/lsf/normalized.lsf"))
    a = ap.parse_args()
    text, stats = normalize(a.root.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8")
    print(f"{a.out}: {stats['mapped']} objects mapped to checkout paths, "
          f"{stats['kept']} generated/unknown kept, {stats['libraries']} library lines")


if __name__ == "__main__":
    main()
