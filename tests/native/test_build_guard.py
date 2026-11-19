#!/usr/bin/env python3
"""Tests for tools/build_guard.py: per-tree lock, freshness check, provenance.

Run with the Python that runs the build (devkitPro MSYS on Windows, the
native one on Linux), and once with native Windows Python for msvcrt:
    python tests/native/test_build_guard.py
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/build_guard.py"
HOLD = [sys.executable, "-c", "import sys, time; print('held', flush=True); time.sleep(float(sys.argv[1]))"]


def guard(*args, **kw):
    return subprocess.run([sys.executable, str(GUARD), *args], capture_output=True, text=True, **kw)


def start_holder(tree, seconds="30"):
    p = subprocess.Popen([sys.executable, str(GUARD), "lock", "--tree", str(tree), "--", *HOLD, seconds],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "held"
    return p


class Lock(unittest.TestCase):
    def test_same_tree_refused_other_tree_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp, "a"), Path(tmp, "b")
            holder = start_holder(a)
            try:
                r = guard("lock", "--tree", str(a), "--", sys.executable, "-c", "pass")
                self.assertEqual(r.returncode, 75, r.stderr)
                self.assertIn("another build holds", r.stderr)
                self.assertIn(f"pid {holder.pid}", r.stderr)
                r = guard("lock", "--tree", str(b), "--", sys.executable, "-c", "pass")
                self.assertEqual(r.returncode, 0, r.stderr)
            finally:
                holder.kill()
                holder.wait()

    def test_killed_holder_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp, "t")
            holder = start_holder(tree)
            holder.kill()
            holder.wait()
            # The child sleeper may outlive the killed guard on some hosts;
            # the lock belongs to the guard's open handle, not the child.
            time.sleep(0.5)
            r = guard("lock", "--tree", str(tree), "--", sys.executable, "-c", "pass")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((tree / ".build.lock").exists())

    def test_exit_status_and_marker_passed_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp, "t")
            r = guard("lock", "--tree", str(tree), "--", sys.executable, "-c",
                      "import os, sys; print(os.environ['SINJOH_LOCKED_TREES']); sys.exit(3)")
            self.assertEqual(r.returncode, 3)
            self.assertIn(str(tree), r.stdout)


class Verify(unittest.TestCase):
    def test_stale_and_missing_prerequisites_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            hdr = t / "a.h"
            hdr.write_text("x")
            obj = t / "o" / "a.o"
            obj.parent.mkdir()
            obj.write_bytes(b"o")
            dep = obj.with_suffix(".d")
            dep.write_text(f"{obj.as_posix()}: {hdr.as_posix()} \\\n {hdr.as_posix()}\n{hdr.as_posix()}:\n")
            now = time.time()
            os.utime(hdr, (now - 10, now - 10))
            os.utime(obj, (now - 5, now - 5))
            self.assertEqual(guard("verify", "--tree", str(t / "o")).returncode, 0)
            os.utime(hdr, (now, now))
            r = guard("verify", "--tree", str(t / "o"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("stale object", r.stderr)
            hdr.unlink()
            r = guard("verify", "--tree", str(t / "o"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("missing", r.stderr)

    def test_relative_prerequisites_resolve_against_tree_cwd(self):
        # Sub-makes write .d paths relative to their own directory, so
        # verify resolves them against the CWD given with --tree DIR=CWD.
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            src = t / "lib" / "inc"
            src.mkdir(parents=True)
            (src / "a.h").write_text("x")
            obj = t / "lib" / "build" / "a.o"
            obj.parent.mkdir()
            obj.write_bytes(b"o")
            obj.with_suffix(".d").write_text("build/a.o: inc/a.h\ninc/a.h:\n")
            now = time.time()
            os.utime(src / "a.h", (now - 10, now - 10))
            os.utime(obj, (now - 5, now - 5))
            tree = str(t / "lib" / "build")
            r = guard("verify", "--tree", tree, cwd=str(t))
            self.assertEqual(r.returncode, 1)
            self.assertIn("missing", r.stderr)
            r = guard("verify", "--tree", f"{tree}={t / 'lib'}", cwd=str(t))
            self.assertEqual(r.returncode, 0, r.stderr)
            os.utime(src / "a.h", (now, now))
            r = guard("verify", "--tree", f"{tree}={t / 'lib'}", cwd=str(t))
            self.assertEqual(r.returncode, 1)
            self.assertIn("stale object", r.stderr)


class Provenance(unittest.TestCase):
    def test_record_names_artifact_hash_and_signatures(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "gen").mkdir()
            (t / "gen/build_id.h").write_text('#define HGSS_BUILD_ID "sinjoh-abc"\n')
            (t / "x.o").write_bytes(b"obj")
            (t / "x.d").write_text("x.o: gen/build_id.h\n")
            art = t / "game.3dsx"
            art.write_bytes(b"3dsx")
            flags = t / ".compile-flags"
            flags.write_text("cc|-O2")
            r = guard("provenance", "--tree", str(t), "--artifact", str(art), "--profile", "1",
                      "--flags", str(flags))
            self.assertEqual(r.returncode, 0, r.stderr)
            rec = json.loads((t / "game.build-info.json").read_text())
            self.assertEqual(rec["build_id"], "sinjoh-abc")
            self.assertEqual(rec["artifact_sha256"], hashlib.sha256(b"3dsx").hexdigest())
            self.assertEqual(rec["generated_headers"]["count"], 1)
            self.assertEqual(rec["objects"]["count"], 1)
            self.assertEqual(rec["profile"], "1")
            self.assertIsNotNone(rec["flags_signature"])


if __name__ == "__main__":
    unittest.main()
