#!/usr/bin/env python3
"""Inventory the pokeplatinum decompilation for the sinjoh build.

pokeplatinum is meson-based and its linker spec lives at
`platinum.us/main.lsf`. HGSS (kohjoh's target) derives sources from makefile
wildcards and reads `main.lsf` at the repository root. The two differ, so this
tool reads the actual meson `files()` lists plus `platinum.us/main.lsf` and
never globs the tree.

Usage:
    python tools/game/platinum_sources.py --root build/upstream --sources
    python tools/game/platinum_sources.py --root build/upstream --overlay-map
    python tools/game/platinum_sources.py --root build/upstream --verify
    python tools/game/platinum_sources.py --root build/upstream --json

Object names in the linker spec are flattened: `main.nef.p/src_foo_bar.c.o`
means `src/foo/bar.c` (or any filename whose path flattens to that key). The
flatten map is built from the meson source lists, so an object with no source
is reported as build-generated or unknown instead of guessed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SOURCE_SUFFIXES = (".c", ".cpp", ".s", ".S", ".cc")
OBJECT_PREFIXES = ("main.nef.p/",)


def meson_sources(root: Path) -> tuple[list[str], list[str]]:
    """Return (sources, subdirs-without-meson) from every meson.build."""
    sources: list[str] = []
    skipped: list[str] = []
    for meson in sorted(root.rglob("meson.build")):
        rel = meson.relative_to(root)
        if rel.parts[0] not in ("src", "lib", "asm"):
            continue
        text = meson.read_text(encoding="utf-8", errors="replace")
        # `files('a.c', 'sub/b.cpp')` across continuations.
        for call in re.finditer(r"files\s*\((.*?)\)", text, re.S):
            for literal in re.findall(r"'([^']+)'", call.group(1)):
                if literal.endswith(SOURCE_SUFFIXES):
                    candidate = (meson.parent / literal).resolve()
                    if candidate.is_file():
                        sources.append(str(candidate.relative_to(root.resolve())))
                    else:
                        skipped.append(str(candidate.relative_to(root.resolve())))
    return sorted(set(sources)), sorted(set(skipped))


def parse_lsf(root: Path) -> list[dict]:
    lsf = root / "platinum.us" / "main.lsf"
    if not lsf.is_file():
        sys.exit(f"{lsf} not found; run tools/game/bootstrap.py first")
    sections: list[dict] = []
    current: dict | None = None
    for raw in lsf.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        m = re.match(r"^(Static|Autoload|Overlay)\s+(\S+)", line)
        if m:
            current = {"kind": m.group(1), "name": m.group(2), "after": [],
                       "objects": [], "address": None}
            sections.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"^Object\s+(\S+)", line)
        if m:
            current["objects"].append(m.group(1))
            continue
        m = re.match(r"^After\s+(\S+)", line)
        if m:
            current["after"].append(m.group(1))
            continue
        m = re.match(r"^Address\s+(\S+)", line)
        if m:
            current["address"] = m.group(1)
    return sections


def flatten(path: str) -> str:
    return path.replace("/", "_").replace("\\", "_")


def build_index(sources: list[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for source in sources:
        index[flatten(source)] = source
    return index


def object_source(obj: str, index: dict[str, str]) -> str | None:
    name = obj
    for prefix in OBJECT_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    if not name.endswith(".o"):
        return None
    name = name[:-2]
    return index.get(name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("build/upstream"))
    ap.add_argument("--sources", action="store_true")
    ap.add_argument("--overlay-map", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = a.root.resolve()

    sources, missing = meson_sources(root)
    sections = parse_lsf(root)
    index = build_index(sources)

    assigned: dict[str, list[str]] = {}
    unknown: list[str] = []
    for section in sections:
        for obj in section["objects"]:
            source = object_source(obj, index)
            if source is None:
                unknown.append(obj)
            else:
                assigned.setdefault(section["name"], []).append(source)

    if a.json:
        print(json.dumps({
            "sources": sources,
            "missing_meson_files": missing,
            "sections": sections,
            "assigned": assigned,
            "unknown_objects": unknown,
        }, indent=1))
        return
    if a.sources:
        print("\n".join(sources))
        return
    if a.overlay_map:
        for section in sections:
            print(f"{section['kind']} {section['name']}"
                  f"{' after ' + ','.join(section['after']) if section['after'] else ''}")
            for source in assigned.get(section["name"], []):
                print(f"  {source}")
        return
    # verify
    total_objects = sum(len(s["objects"]) for s in sections)
    print(f"sources: {len(sources)}")
    print(f"meson entries with no file: {len(missing)}")
    print(f"linker objects: {total_objects} in {len(sections)} sections")
    print(f"mapped: {sum(len(v) for v in assigned.values())}")
    print(f"unmapped objects: {len(unknown)}")
    if missing:
        print("missing meson entries:")
        for path in missing:
            print(f"  {path}")
    if unknown:
        print("unmapped (build-generated or missing from meson):")
        for obj in unknown[:40]:
            print(f"  {obj}")
        if len(unknown) > 40:
            print(f"  ... {len(unknown) - 40} more")
    raise SystemExit(0 if not missing else 1)


if __name__ == "__main__":
    main()
