#!/usr/bin/env python3
"""Exercise production compile recipes and dependency wiring with synthetic sources.

Run in devkitPro MSYS: CC=gcc python tests/native/test_build_dependencies.py
"""

import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "engine/game.mk"
NITRO = ROOT / "engine/compat/nitro/Makefile"
NNS = ROOT / "engine/compat/nitrosystem/Makefile"


def rule(text, target):
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(target + ":"))
    end = start + 1
    while end < len(lines) and (lines[end].startswith("\t") or lines[end - 1].rstrip().endswith("\\")):
        end += 1
    return "".join(lines[start:end])


def dependencies(text):
    start = text.index("DEP_OBJECTS :=")
    end = text.index("-include $(wildcard $(DEP_FILES))", start)
    return text[start : end + len("-include $(wildcard $(DEP_FILES))")]


# Each case extracts its actual recipe and the owning Makefile's dependency block.
CASES = [
    (GAME, "$(OUT)/src/%.o", "game/src/demo.c", "out/src/demo.o", "GAME_OBJS"),
    (GAME, "$(OUT)/lib/%.o", "game/lib/demo.c", "out/lib/demo.o", "GAME_OBJS"),
    (GAME, "$(TRAINER_AI_O)", "game/src/battle/trainer_ai/script.s", "out/src/battle/trainer_ai/script.o", "GAME_OBJS"),
    (GAME, "$(WIFI_STUBS_O)", "out/gen/wifi_stubs.c", "out/gen/wifi_stubs.o", "WIFI_STUBS_O"),
    (GAME, "$(OUT)/gen/overlay_table.o", "out/gen/overlay_table.c", "out/gen/overlay_table.o", None),
    (GAME, "$(OUT)/ds/%.o", "engine/ds.c", "out/ds/engine/ds.o", "ENGINE_DS_OBJS"),
    (GAME, "$(OUT)/ctr/%.o", "engine/ctr.c", "out/ctr/engine/ctr.o", "ENGINE_CTR_OBJS"),
    (NITRO, "$(OUT)/sdk/%.o", "sdk/libraries/demo.c", "out/sdk/demo.o", "SDK_OBJS"),
    (NITRO, "$(OUT)/port/%.o", "src/demo.c", "out/port/demo.o", "PORT_OBJS"),
    (NITRO, "$(OUT)/port/platform/3ds.o", "src/platform/3ds.c", "out/port/platform/3ds.o", "PORT_OBJS"),
    (NITRO, "$(PAK_READER_OBJ)", "../pak/src/pak.c", "out/port/pak_reader.o", "PORT_OBJS"),
    (NITRO, "$(OUT)/arm7_raw/%.o", "sdk/libraries/sound.c", "out/arm7_raw/sound.o", "ARM7_RAW"),
    (NNS, "$(OUT)/nns/%.o", "nns/libraries/demo.c", "out/nns/demo.o", "NNS_OBJS"),
    (NNS, "$(GEN)/nns_all_headers.o", "out/gen/nns_all_headers.c", "out/gen/nns_all_headers.o", None),
]


class Dependencies(unittest.TestCase):
    def test_compiler_rules_track_headers_and_regenerate_missing_depfiles(self):
        cc = os.environ.get("CC", "gcc")
        for filename, target, source, obj, list_var in CASES:
            with self.subTest(recipe=target), tempfile.TemporaryDirectory(prefix="sinjoh-deps-") as tmp:
                base = Path(tmp)
                # The pak recipe uses ../pak; keep it within the temporary tree.
                work = base / "work"
                work.mkdir()
                common = work / "engine/compat/common.mk"
                common.parent.mkdir(parents=True)
                common.write_text("")
                source_path = work / source
                source_path.parent.mkdir(parents=True, exist_ok=True)
                body = ".text\n.byte VALUE\n" if source.endswith(".s") else "int f(void) { return VALUE; }\n"
                source_path.write_text('#include "top.h"\n' + body)
                inc = work / "include"
                (inc / "nitro").mkdir(parents=True)
                (inc / "nitro/misc.h").write_text("")
                (inc / "stdint.h").write_text("")
                top = inc / "top.h"
                nested = inc / "nested.h"
                top.write_text('#include "nested.h"\n')
                nested.write_text("#define VALUE 1\n")
                (work / "src/platform").mkdir(parents=True, exist_ok=True)
                (work / "src/port_platform.h").write_text("")
                pak_header = base / "pak/include/pak.h"
                pak_header.parent.mkdir(parents=True, exist_ok=True)
                pak_header.write_text("")
                fx = work / "out/gen/nitro/fx/fx_const.h"
                fx.parent.mkdir(parents=True, exist_ok=True)
                fx.write_text("")
                old_object = work / obj
                old_object.parent.mkdir(parents=True, exist_ok=True)
                old_object.write_bytes(b"pre-dependency object")
                dep = old_object.with_suffix(".d")
                # Emulate an old native-Windows target spelling and an existing object.
                dep.write_text("out/old/wrong-target.o: include/nested.h\n")
                text = filename.read_text()
                variables = f"""OUT := out
ROOT := .
GAME := game
CONSTANTS_DIR := include
SDK := sdk
NNS := nns
GEN := out/gen
DEVKITPRO := missing-devkitpro
CC := {cc}
CFLAGS := -Iinclude
PORT_CFLAGS := -Iinclude
GAME_CFLAGS := -Iinclude
ENGINE_DS_CFLAGS := -Iinclude
ENGINE_CTR_CFLAGS := -Iinclude
WEAKEN_NNS_INLINE := true
TRAINER_AI_O := out/src/battle/trainer_ai/script.o
PAK_READER_OBJ := out/port/pak_reader.o
WIFI_STUBS_C := out/gen/wifi_stubs.c
OVERLAY_TABLE_C := out/gen/overlay_table.c
{list_var + ' := ' + obj if list_var else ''}
all: {obj}
.PHONY: libs libnitro
libs libnitro:
"""
                (work / "Makefile").write_text(variables + rule(text, target) + "\n" + dependencies(text) + "\n")

                def make():
                    result = subprocess.run(["make", "--no-print-directory", "all"], cwd=work,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout)

                make()
                self.assertNotEqual(old_object.read_bytes(), b"pre-dependency object")
                self.assertNotIn("old/wrong-target", dep.read_text())
                unchanged = old_object.stat().st_mtime_ns
                make()
                self.assertEqual(old_object.stat().st_mtime_ns, unchanged, "unchanged object rebuilt")

                now = time.time()
                os.utime(old_object, (now - 4, now - 4))
                os.utime(nested, (now - 2, now - 2))
                make()
                self.assertGreater(old_object.stat().st_mtime, now - 3, "transitive header did not rebuild")

                # -MP lets Make recover when a header is removed from the source.
                now = time.time()
                os.utime(old_object, (now - 4, now - 4))
                top.write_text("#define VALUE 2\n")
                os.utime(top, (now - 2, now - 2))
                nested.unlink()
                make()
                self.assertGreater(old_object.stat().st_mtime, now - 3, "removed header prevented rebuild")

                dep.unlink()
                now = time.time()
                os.utime(old_object, (now - 4, now - 4))
                make()
                self.assertTrue(dep.is_file(), "missing .d did not force regeneration")
                self.assertGreater(old_object.stat().st_mtime, now - 3)
                unchanged = old_object.stat().st_mtime_ns
                make()
                self.assertEqual(old_object.stat().st_mtime_ns, unchanged, "repeat rebuild after regeneration")

                # Compiler flags or recipes can change in either owning or shared Makefile.
                stamp = work / "out/.header-deps-v1"
                for build_rules in (work / "Makefile", common):
                    now = time.time()
                    os.utime(stamp, (now - 4, now - 4))
                    os.utime(old_object, (now - 4, now - 4))
                    os.utime(build_rules, (now - 2, now - 2))
                    make()
                    self.assertGreater(old_object.stat().st_mtime, now - 3, "changed build rules did not rebuild")


if __name__ == "__main__":
    unittest.main()
