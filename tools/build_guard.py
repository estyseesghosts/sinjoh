#!/usr/bin/env python3
"""Per-output-tree build lock, freshness check and provenance record (#14).

    build_guard.py lock --tree DIR -- COMMAND...
        Hold an exclusive OS lock on DIR/.build.lock while COMMAND runs.
        A second holder fails at once with exit 75 and names the owner.
        The OS drops the lock when the holder exits or crashes, so no
        stale-lock cleanup exists or is needed.

    build_guard.py verify --tree DIR[=CWD] ...
        Fail if any object's .d file names a prerequisite newer than the
        object, or names a prerequisite that no longer exists. Relative
        prerequisites are resolved against CWD, the directory the
        compiler ran in (the sub-make's -C directory); it defaults to
        the current directory.

    build_guard.py provenance --tree DIR --artifact FILE [--elf FILE]
                              [--profile N] [--cc CC] [--flags FILE]
        Write FILE.build-info.json: commit, dirty state, profile,
        toolchain, generated-header and object-dependency signatures,
        build ID and artifact SHA-256.

The lock uses fcntl.flock on POSIX (Linux, devkitPro MSYS2/Cygwin) and
msvcrt.locking on native Windows Python. Both are released by the OS on
process exit. A lock is only visible to holders using the same lock
family; every Sinjoh build entry point runs make from one environment
(devkitPro MSYS2 on Windows, the native shell on Linux), so they agree.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

EX_TEMPFAIL = 75


def _try_lock(handle):
    if sys.platform == "win32":
        import msvcrt
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def cmd_lock(args):
    tree = Path(args.tree).resolve()
    tree.mkdir(parents=True, exist_ok=True)
    lock_path = tree / ".build.lock"
    owner_path = tree / ".build.owner"
    # The lock file itself is never rewritten or deleted: its byte 0 is
    # what is locked. Owner details live in a separate file.
    handle = open(lock_path, "a+b")
    if not _try_lock(handle):
        try:
            owner = owner_path.read_text(encoding="utf-8").strip()
        except OSError:
            owner = "unknown"
        print(f"build_guard: another build holds {tree}\n"
              f"build_guard: owner: {owner}\n"
              f"build_guard: wait for it to finish; separate trees can build in parallel",
              file=sys.stderr)
        return EX_TEMPFAIL
    owner = (f"pid {os.getpid()} on {platform.node()}, started "
             f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}: "
             + " ".join(args.command))
    try:
        owner_path.write_text(owner + "\n", encoding="utf-8")
    except OSError:
        pass
    env = dict(os.environ)
    # Mark this tree as locked so nested makes of the same tree do not
    # try to take the lock again (they would fail against their parent).
    held = env.get("SINJOH_LOCKED_TREES", "").split()
    env["SINJOH_LOCKED_TREES"] = " ".join(held + [str(tree)])
    # close_fds=False keeps the make jobserver descriptors inherited.
    result = subprocess.run(args.command, env=env, close_fds=False)
    return result.returncode


def parse_depfile(path):
    """Yield (target, prerequisites) from a GCC .d file."""
    text = path.read_text(encoding="utf-8", errors="replace").replace("\\\n", " ")
    for line in text.splitlines():
        # Split on the first ": " or ":" after a target; Windows drive
        # letters ("C:/x") are not followed by whitespace.
        m = re.match(r"^(.*?[^\s:]):(?:\s|$)(.*)$", line)
        if not m:
            continue
        prereqs = re.split(r"(?<!\\)\s+", m.group(2).strip())
        yield m.group(1).strip(), [p.replace("\\ ", " ") for p in prereqs if p]


def native(path):
    """Map an MSYS '/c/x' spelling to 'c:/x' when running native Python."""
    if sys.platform == "win32":
        m = re.match(r"^/([a-zA-Z])/(.*)$", path)
        if m:
            return f"{m.group(1)}:/{m.group(2)}"
    return path


def cmd_verify(args):
    stale = []
    missing = []
    checked = 0
    mtimes = {}

    def mtime(p):
        if p not in mtimes:
            try:
                mtimes[p] = Path(native(p)).stat().st_mtime_ns
            except OSError:
                mtimes[p] = None
        return mtimes[p]

    for spec in args.tree:
        tree, _, cwd = spec.partition("=")
        tree = Path(native(tree)).resolve()
        base = native(cwd or os.getcwd())
        for dep in sorted(tree.rglob("*.d")):
            obj = dep.with_suffix(".o")
            if not obj.is_file():
                continue
            obj_mtime = obj.stat().st_mtime_ns
            for target, prereqs in parse_depfile(dep):
                # -MP adds a phony "header:" line per header; skip those.
                if not target.endswith(".o"):
                    continue
                for p in prereqs:
                    if not (p.startswith("/") or re.match(r"^[a-zA-Z]:", p)):
                        p = os.path.join(base, p)
                    m = mtime(p)
                    if m is None:
                        missing.append((obj, p))
                    elif m > obj_mtime:
                        stale.append((obj, p))
                checked += 1
    for obj, p in stale[:20]:
        print(f"build_guard: stale object {obj} is older than {p}", file=sys.stderr)
    for obj, p in missing[:20]:
        print(f"build_guard: {obj} depends on missing {p}", file=sys.stderr)
    if stale or missing:
        print(f"build_guard: {len(stale)} stale and {len(missing)} missing prerequisites; "
              f"refusing to link a mixed build", file=sys.stderr)
        return 1
    print(f"   [fresh] {checked} objects agree with their dependency records")
    return 0


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_signature(paths, root):
    h = hashlib.sha256()
    count = 0
    for p in sorted(paths):
        h.update(str(p.relative_to(root)).replace("\\", "/").encode())
        h.update(b"\0")
        h.update(bytes.fromhex(sha256_file(p)))
        count += 1
    return h.hexdigest(), count


def git(repo, *argv):
    try:
        return subprocess.run(["git", "-C", str(repo), *argv], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def cmd_provenance(args):
    tree = Path(args.tree).resolve()
    artifact = Path(args.artifact).resolve()
    repo = Path(__file__).resolve().parents[1]
    gen_sig, gen_count = tree_signature([p for p in (tree / "gen").rglob("*.h")], tree)
    dep_sig, dep_count = tree_signature(list(tree.rglob("*.d")), tree)
    obj_sig, obj_count = tree_signature(list(tree.rglob("*.o")), tree)
    build_id = None
    bid = tree / "gen/build_id.h"
    if bid.is_file():
        m = re.search(r'#define HGSS_BUILD_ID "([^"]+)"', bid.read_text(encoding="utf-8"))
        build_id = m.group(1) if m else None
    toolchain = None
    if args.cc:
        try:
            toolchain = subprocess.run([args.cc, "--version"], capture_output=True,
                                       text=True).stdout.splitlines()[0]
        except (OSError, IndexError):
            toolchain = None
    flags_sig = sha256_file(args.flags) if args.flags and Path(args.flags).is_file() else None
    status = git(repo, "status", "--porcelain")
    record = {
        "schema": "sinjoh-build-info/1",
        "artifact": artifact.name,
        "artifact_sha256": sha256_file(artifact),
        "elf_sha256": sha256_file(args.elf) if args.elf else None,
        "build_id": build_id,
        "commit": git(repo, "rev-parse", "HEAD"),
        "dirty": bool(status) if status is not None else None,
        "profile": args.profile,
        "toolchain": toolchain,
        "flags_signature": flags_sig,
        "generated_headers": {"count": gen_count, "sha256": gen_sig},
        "dependency_records": {"count": dep_count, "sha256": dep_sig},
        "objects": {"count": obj_count, "sha256": obj_sig},
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": f"{platform.system()} {platform.machine()}",
    }
    out = artifact.with_name(artifact.stem + ".build-info.json")
    tmp = out.with_suffix(".json.new")
    tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    print(f"   build info: {out.name} (sha256 {record['artifact_sha256'][:16]})")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lock")
    p.add_argument("--tree", required=True)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p = sub.add_parser("verify")
    p.add_argument("--tree", required=True, action="append")
    p = sub.add_parser("provenance")
    p.add_argument("--tree", required=True)
    p.add_argument("--artifact", required=True)
    p.add_argument("--elf")
    p.add_argument("--profile")
    p.add_argument("--cc")
    p.add_argument("--flags")
    args = ap.parse_args(argv)
    if args.cmd == "lock":
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        if not args.command:
            ap.error("lock needs a command after --")
        return cmd_lock(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    return cmd_provenance(args)


if __name__ == "__main__":
    sys.exit(main())
