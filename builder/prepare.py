#!/usr/bin/env python3
"""Turn your own retail Pokemon Platinum dump into sinjoh's SD-card files.

    python builder/prepare.py                    # finds a .nds in this folder
    python builder/prepare.py your-game.nds      # or name it (drag and drop works)
    python builder/prepare.py your-game.nds --sd E:\\    # write straight to the card

The ROM is only read, never modified, and nothing is uploaded. The script
checks the dump, extracts its files to a temporary folder, writes
platinum.pak and platinum.manifest.json, checks the pack back, and (when the
builds exist) stages sinjoh-platinum.3dsx and sinjoh-platinum-dbg.3dsx beside
them. The result is an SD-card root: copy its 3ds/ folder to the card's root,
or pass --sd to write there directly. The programs go to 3ds/ and the data to
3ds/sinjoh/:

The .pak contains your game's data: do not share it, and never commit a ROM,
a pack, a save or extracted data.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

# Run from anywhere: the sibling modules live next to this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_rom  # noqa: E402
import pack  # noqa: E402
import verify_rom  # noqa: E402

EDITION = "platinum"
BUILD_ID = pack.DEFAULT_BUILD_ID  # what the program checks at boot
APPS_DIR = Path("3ds")
DATA_ROOT = APPS_DIR / "sinjoh"
SD_DATA_DIR = DATA_ROOT / "data"
APPS = (  # file name, build tree relative to the repo
    ("sinjoh-platinum.3dsx", Path("build") / "game" / "3ds"),
    ("sinjoh-platinum-dbg.3dsx", Path("build") / "game" / "3ds-prof"),
)
REPO = Path(__file__).resolve().parent.parent


def find_roms() -> list[Path]:
    """.nds files next to this script, in the current folder, or at the repo root."""
    seen: dict[Path, Path] = {}
    for folder in (Path.cwd(), Path(__file__).resolve().parent, REPO):
        for rom in sorted(folder.glob("*.nds")):
            seen[rom.resolve()] = rom
    return list(seen)


def check_pak(path: Path, digest: str) -> None:
    """Re-read the finished pack's header and make sure it matches the program."""
    with path.open("rb") as f:
        magic, version, raw_build_id, sha1, count = pack.HEADER.unpack(f.read(pack.HEADER.size))
    build_id = raw_build_id.rstrip(b"\0").decode()
    if (magic != pack.MAGIC or version != pack.VERSION or sha1.hex() != digest
            or build_id != BUILD_ID or not count):
        raise ValueError(f"{path.name} did not come out right; please try again")


def prepare(rom: Path, outdir: Path) -> None:
    print(f"Checking {rom.name} ...")
    digest = verify_rom.sha1_of(rom)
    name = verify_rom.SUPPORTED.get(digest)
    if name is None:
        raise ValueError(
            "unsupported ROM (modified, trimmed or another region).\n"
            "Supported: " + "; ".join(verify_rom.SUPPORTED.values()))
    print(f"  {name}: OK")
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sinjoh-") as tmp:
        data = Path(tmp)
        print("Reading the game files ...")
        entries = extract_rom.extract(rom, data, verify=False)  # verified above
        total = sum(entry["size"] for entry in entries)
        print(f"  {len(entries)} files, {total / (1 << 20):.1f} MiB")
        print("Building the data pack ...")
        pak = outdir / f"{EDITION}.pak"
        pack.pack(data, pak, build_id=BUILD_ID, rom_sha1=digest,
                  supported=verify_rom.SUPPORTED)
        check_pak(pak, digest)
        shutil.copyfile(data / "manifest.json", outdir / f"{EDITION}.manifest.json")


def stage_apps(dest: Path) -> list[str]:
    """Copy the built programs beside the data; report what is missing."""
    dest.mkdir(parents=True, exist_ok=True)
    missing = []
    for name, tree in APPS:
        source = REPO / tree / name
        if source.is_file():
            shutil.copyfile(source, dest / name)
            print(f"  staged {name} ({source.stat().st_size / (1 << 20):.1f} MiB)")
        else:
            missing.append(name)
    return missing


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")  # legacy Windows consoles
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rom", type=Path, nargs="*",
                        help="your unmodified Platinum .nds; default: any .nds found")
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--sd", type=Path, metavar="SD_ROOT",
                       help="SD card root (e.g. E:\\); writes 3ds/sinjoh-platinum*.3dsx and 3ds/sinjoh/ on it")
    where.add_argument("-o", "--output", type=Path, default=Path("sinjoh-sd"),
                       help="output SD-card root (default: sinjoh-sd)")
    parser.add_argument("--no-apps", action="store_true",
                        help="pack the data only; do not stage the .3dsx files")
    args = parser.parse_args(argv)

    roms = args.rom or find_roms()
    if not roms:
        print("No ROM given and no .nds file found here.\n"
              "Pass your dump: python builder/prepare.py your-game.nds\n")
        for digest, name in verify_rom.SUPPORTED.items():
            print(f"  {name}: {digest}")
        return 2
    if args.sd is not None:
        if not args.sd.is_dir():
            print(f"SD card folder not found: {args.sd}")
            return 2
        root = args.sd
    else:
        root = args.output

    data_dir = root / SD_DATA_DIR
    failed = 0
    for rom in roms:
        try:
            if not rom.is_file():
                raise OSError(f"not a file: {rom}")
            prepare(rom, data_dir)
        except (OSError, ValueError) as exc:
            print(f"\n{rom.name}: failed: {exc}\n")
            failed += 1
    if failed == len(roms):
        return 1
    if not args.no_apps:
        print("Staging the programs ...")
        missing = stage_apps(root / APPS_DIR)
        if missing:
            print("  (not built yet: " + ", ".join(missing)
                  + "; run pwsh tools/build.ps1 -All)")
    print(f"\nDone -> {root.resolve()}")
    if args.sd is None:
        print(f"Copy the contents of {root} (the 3ds folder) onto your SD card root.")
    else:
        print("The card is ready; run sinjoh-platinum from the homebrew launcher.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
