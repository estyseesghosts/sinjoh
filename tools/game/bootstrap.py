#!/usr/bin/env python3
"""Fetch the pinned pokeplatinum decompilation and the SDK sources, apply patches.

Adapted from kohjoh/tools/game/bootstrap.py and pokeplatinum-3ds/tools/bootstrap.py
(both GPL-3.0). One difference matters: pokeplatinum fetches NitroSDK and
NitroSystem as meson subprojects at their own revisions, while HGSS carries them
in-tree, so this script reads the revisions from the decomp's subprojects/*.wrap.

Result:
    build/upstream/    pret/pokeplatinum at upstream.lock, then
                       patches/pokeplatinum/*.patch at the repository root
    build/NitroSDK/    the SDK decompilation at its pinned revision, then
                       patches/NitroSDK/*.patch
    build/NitroSystem/ likewise

Usage:
    python tools/game/bootstrap.py
    python tools/game/bootstrap.py --clean
"""

from __future__ import annotations

import argparse
import configparser
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BUILD = ROOT / "build"
UPSTREAM = BUILD / "upstream"
PATCH_ROOT = ROOT / "patches"
SUBPROJECTS = ("NitroSDK", "NitroSystem")

GIT_IDENT = {
    "GIT_COMMITTER_NAME": "sinjoh bootstrap",
    "GIT_COMMITTER_EMAIL": "bootstrap@invalid",
}


def git(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=False, text=True, capture_output=capture,
        env={**os.environ, **GIT_IDENT},
    )
    if result.returncode != 0:
        detail = (result.stderr or "").strip() if capture else ""
        sys.exit(f"git {' '.join(args)} failed{': ' + detail if detail else ''}")
    return (result.stdout or "").strip() if capture else ""


def read_lock(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = raw.split("#", 1)[0].split()
        if not fields:
            continue
        if fields[0] in ("decomp", "kohjoh", "pokeplatinum-3ds", "coffeepot"):
            if len(fields) != 3:
                sys.exit(f"{path.name}:{line_no}: expected 'name url commit'")
            values[fields[0]] = fields[2]
            if fields[0] == "decomp":
                values["decomp_url"] = fields[1]
        elif fields[0] == "url" and len(fields) == 2:
            values["decomp_url"] = fields[1]
    if "decomp" not in values or "decomp_url" not in values:
        sys.exit(f"{path.name}: no 'decomp <url> <commit>' pin")
    return values


def read_wrap(name: str) -> tuple[str, str]:
    wrap = UPSTREAM / "subprojects" / f"{name}.wrap"
    if not wrap.is_file():
        sys.exit(f"{wrap.relative_to(ROOT)} not found; is build/upstream complete?")
    parser = configparser.ConfigParser()
    parser.read(wrap, encoding="utf-8")
    section = parser["wrap-git"]
    return section["url"], section["revision"]


def current_commit(repo: Path) -> str | None:
    if not (repo / ".git").exists():
        return None
    return git("rev-parse", "HEAD", cwd=repo, capture=True)


def fetch(dest: Path, url: str, commit: str) -> None:
    print(f"Fetching {url} @ {commit[:12]} ...")
    dest.mkdir(parents=True, exist_ok=True)
    git("init", "--quiet", cwd=dest)
    git("remote", "add", "origin", url, cwd=dest)
    git("fetch", "--quiet", "--depth", "1", "origin", commit, cwd=dest)
    git("checkout", "--quiet", "--detach", "FETCH_HEAD", cwd=dest)


def apply_patches(dest: Path, patch_dir: Path) -> int:
    if not patch_dir.is_dir():
        return 0
    patches = sorted(patch_dir.glob("*.patch"))
    for patch in patches:
        print(f"  applying {patch_dir.name}/{patch.name}")
        git("apply", "--check", str(patch), cwd=dest)
        git("apply", str(patch), cwd=dest)
    return len(patches)


def prepare(name: str, dest: Path, url: str, commit: str, patch_dir: Path) -> None:
    have = current_commit(dest)
    if have is None:
        fetch(dest, url, commit)
    elif have != commit:
        sys.exit(f"{dest.relative_to(ROOT)} is at {have[:12]}, wanted {commit[:12]}.\n"
                 "Run with --clean to re-fetch.")
    else:
        if git("status", "--porcelain", cwd=dest, capture=True):
            sys.exit(f"{dest.relative_to(ROOT)} has local changes.\nRun with --clean.")
    count = apply_patches(dest, patch_dir)
    print(f"{name}: {commit[:12]}, {count} patches")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if shutil.which("git") is None:
        sys.exit("Git is not installed or not on PATH.")
    # devkitPro's MSYS2 git cannot fetch over HTTPS; Git for Windows can.
    git_for_windows = Path(r"C:\Program Files\Git\cmd")
    if git_for_windows.is_dir():
        os.environ["PATH"] = str(git_for_windows) + os.pathsep + os.environ["PATH"]

    if args.clean:
        for d in (UPSTREAM, *(BUILD / n for n in SUBPROJECTS)):
            if d.exists():
                print(f"Removing {d.relative_to(ROOT)}")
                shutil.rmtree(d)

    lock = read_lock(ROOT / "upstream.lock")
    prepare("pokeplatinum", UPSTREAM, lock["decomp_url"], lock["decomp"],
            PATCH_ROOT / "pokeplatinum")

    for name in SUBPROJECTS:
        url, revision = read_wrap(name)
        prepare(name, BUILD / name, url, revision, PATCH_ROOT / name)

    print("Done: build/upstream, build/NitroSDK, build/NitroSystem")


if __name__ == "__main__":
    main()
