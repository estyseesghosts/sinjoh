#!/usr/bin/env python3
"""Stage sinjoh's SD files into a LOTUS primary card.

    python tools/lotus/stage_card.py --card sinjoh
    python tools/lotus/stage_card.py --card sinjoh --script tests/inputs/save_field.txt

Copies build/sd-card/3ds/kohjoh (programs, data pack, manifest, save) into
LOTUS's persistent card for `--card`, and optionally stages a script.txt so
the run is deterministic. Run the windowed session with tools/lotus/run_sinjoh.py.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

LOTUS = Path(r"C:\Users\terezi\workdir\LOTUS-v0.0.3-windows-x64")
REPO = Path(__file__).resolve().parent.parent.parent
SD_SOURCE = REPO / "build" / "sd-card" / "3ds" / "kohjoh"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True)
    ap.add_argument("--backend", default="citnlo")
    ap.add_argument("--script", type=Path,
                    help="input script to stage as sdmc:/3ds/kohjoh/script.txt")
    ap.add_argument("--keep-script", action="store_true",
                    help="leave an existing script.txt in place when none is given")
    a = ap.parse_args()
    if not SD_SOURCE.is_dir():
        raise SystemExit(f"missing {SD_SOURCE}; run builder/prepare.py first")
    card = (LOTUS / "data" / a.backend / "sessions" / "cards" / a.card /
            "sdmc" / "3ds" / "kohjoh")
    card.mkdir(parents=True, exist_ok=True)
    for item in SD_SOURCE.iterdir():
        target = card / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copyfile(item, target)
    script = card / "script.txt"
    if a.script is not None:
        shutil.copyfile(a.script, script)
        print(f"scripted: {a.script}")
    elif not a.keep_script:
        script.unlink(missing_ok=True)
    # Fresh logs make the last run's output unambiguous.
    shutil.rmtree(card / "logs", ignore_errors=True)
    print(f"card {a.card} -> {card}")
    print("run: python tools/lotus/run_sinjoh.py --card " + a.card)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
