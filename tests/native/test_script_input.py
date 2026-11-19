#!/usr/bin/env python3
"""Compile the real script parser and check ownership at V-blank boundaries.

Run from the repository root: python tests/native/test_script_input.py
Set CC to a host C compiler if `cc` is not on PATH.
"""

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r"""
#include "app/script.h"
#include <stdio.h>
#include <stdlib.h>

void kj_log(const char *fmt, ...) { (void)fmt; }

int main(int argc, char **argv)
{
    kj_script_load(argv[1]);
    printf("meta %u %lu %lu %lu %u\n", (unsigned)kj_script_active(),
           (unsigned long)kj_script_debug(), (unsigned long)kj_script_end(),
           (unsigned long)kj_script_freeze(7), (unsigned)kj_script_dump(7));
    for (int i = 2; i < argc; ++i) {
        uint32_t vb = (uint32_t)strtoul(argv[i], NULL, 10);
        uint16_t keys = 0xaaaau, tx = 333, ty = 444;
        bool touch = true;
        bool owned = kj_script_input(vb, &keys, &touch, &tx, &ty);
        printf("input %u %u %u %u %u\n", (unsigned)owned, (unsigned)keys,
               (unsigned)touch, (unsigned)tx, (unsigned)ty);
    }
    return 0;
}
"""


def main():
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        harness = work / "script_input_harness.c"
        executable = work / ("script_input.exe" if os.name == "nt" else "script_input")
        harness.write_text(HARNESS, encoding="utf-8")
        subprocess.run([
            os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-I", str(ROOT / "engine"), str(harness),
            str(ROOT / "engine/app/script.c"), "-o", str(executable),
        ], check=True)

        def run(script, vblanks, *, missing=False):
            source = work / "script.txt"
            if missing:
                source.unlink(missing_ok=True)
            else:
                source.write_text(script, encoding="utf-8")
            result = subprocess.run([str(executable), str(source), *map(str, vblanks)],
                                    check=True, capture_output=True, text=True)
            return [tuple(map(int, line.split()[1:])) for line in result.stdout.splitlines()]

        live = (0, 0xAAAA, 1, 333, 444)
        idle = (1, 0, 0, 333, 444)
        assert run("", [0], missing=True) == [(0, 0, 0, 0, 0), live]
        assert run("", [0]) == [(1, 0, 0, 0, 0), live]
        assert run("every: 5\ndebug: 0x2 0x8\nend: 50\nfreeze 7 3\ndump 7\n", [0, 20]) == [
            (1, 10, 50, 3, 1), live, live,
        ]
        # Gaps are neutral, not live; key overlaps OR together; touch follows file order.
        assert run("every: 3\n5 A\n6-9 B TOUCH:11,22\n7-8 TOUCH:33,44\n12 -\n",
                   [0, 5, 6, 7, 8, 9, 11, 12, 14, 15]) == [
            (1, 0, 0, 0, 0), idle, (1, 1, 0, 333, 444),
            (1, 3, 1, 11, 22), (1, 3, 1, 33, 44), (1, 2, 1, 11, 22),
            idle, idle, idle, idle, live,
        ]
        # A later every: applies to all implicit-length events, as in the runtime.
        assert run("4 A\nevery: 2\n", [3, 4, 5, 6]) == [
            (1, 0, 0, 0, 0), idle, (1, 1, 0, 333, 444), (1, 1, 0, 333, 444), live,
        ]
        # Reject malformed event/range fields, including overflow and empty durations.
        malformed = ("oops A\n-1 A\n4294967296 A\n3- A\n3-3 A\n3-2 A\n"
                     "3-4294967296 A\n3x A\n4 TYPO\n")
        assert run(malformed, [0, 3, 20]) == [(1, 0, 0, 0, 0), live, live, live]
        # Bad every: leaves the previous valid/default duration intact.
        assert run("every: 2\nevery: 0\nevery: 4294967296\nevery: 3x\n5 A\n",
                   [4, 5, 6, 7]) == [
            (1, 0, 0, 0, 0), idle, (1, 1, 0, 333, 444), (1, 1, 0, 333, 444), live,
        ]
        # Endpoint addition must not wrap near the maximum representable V-blank.
        assert run("every: 3\n4294967294 A\n", [4294967293, 4294967294, 4294967295]) == [
            (1, 0, 0, 0, 0), idle, (1, 1, 0, 333, 444), (1, 1, 0, 333, 444),
        ]
    print("script input ownership: all cases passed")


if __name__ == "__main__":
    main()
