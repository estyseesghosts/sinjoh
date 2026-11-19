# Build dependency tracking

The Make build generates GCC dependency files for game, engine, Nitro and
NitroSystem C objects and the preprocessed trainer AI assembly. A change to an
included project header should rebuild its dependent objects before archiving
and linking. ARM7 renamed objects depend on their raw compiler objects; their
dependency files belong to the raw objects.

A versioned stamp in each output tree forces one rebuild when dependency
tracking is introduced, including objects with an old dependency file whose
target uses an incompatible path spelling. The stamp also depends on the owning
Makefile and shared `engine/compat/common.mk`; editing build rules refreshes
that tree. If a dependency file is removed later, its object is rebuilt to
recreate it. The release and profile trees keep independent stamps.

Under devkitPro MSYS, devkitARM GCC is a native Windows executable. In a lead
probe, its default `.d` target was `C:/...`, while Make's target was `/c/...`;
a header edit then failed to rebuild the target. Supplying `-MQ"$@"` and
excluding the attached `-MQ` argument from MSYS path conversion preserved
Make's target spelling. The header prerequisites remained native Windows paths;
the probe rebuilt after a header edit and reused the object on the next run.
The remaining command arguments still undergo normal MSYS conversion.

Run the synthetic recipe regression in devkitPro MSYS with
`CC=gcc python tests/native/test_build_dependencies.py`. It extracts production
recipes and dependency wiring and uses invented sources and headers. It checks
old-target migration, reuse, transitive header changes, removed headers and
missing `.d` recovery. Target builds and runtime checks are separate evidence.

## One build per output tree

`tools/build.sh <0|1> [make args]` (called by `tools/build.ps1` and CI) runs
make under `tools/build_guard.py lock`, which holds an OS lock on
`<tree>/.build.lock`: `fcntl.flock` under MSYS2/Cygwin and Linux,
`msvcrt.locking` under native Windows Python. A second build of the same
tree exits 75 at once and prints the holder from `<tree>/.build.owner`; it
never waits or deletes anything. The release (`build/game/3ds`) and profile
(`build/game/3ds-prof`) trees lock separately and build in parallel. The OS
drops the lock when the holder exits or is killed, so there is no stale-lock
cleanup. `engine/game.mk` refuses a 3DS build whose tree is not listed in
`SINJOH_LOCKED_TREES`, the marker the guard exports, so a bare `make` cannot
bypass the lock. The lock covers everything that build writes: generated
headers, the libnitro/libnitrosystem trees of that profile and the link.
Locks are only seen by holders of the same family (Cygwin `flock` versus
Win32 byte-range locks); every build entry point runs from the same shell.

## Freshness and provenance

`$(OUT)/.compile-flags` holds the compile flags of the tree and is rewritten
only when they change; every object depends on it, so toggling
`WIDEART_DEBUG` in one tree rebuilds instead of mixing objects. Before the
link, `build_guard.py verify` reads every `.d` file of the game and both
library trees and refuses to link if an object is older than any header it
was compiled against, or names a header that no longer exists.

After `3dsxtool`, `build_guard.py provenance` writes
`<program>.build-info.json` beside the `.3dsx`: commit, dirty flag, profile,
toolchain version, compile-flag signature, SHA-256 signatures of the
generated headers, dependency records and objects, the build ID compiled
into the program (`HGSS_BUILD_ID`, also printed in the guest log) and the
SHA-256 of the `.3dsx` and `.elf`. A LOTUS log names the build ID; the record
with that ID and the artifact hash identifies the exact executable.

`tests/native/test_build_guard.py` covers same-tree refusal, parallel
separate trees, release after the holder is killed, stale/missing header
detection and the provenance record. Run it under both MSYS and native
Windows Python (and Linux in CI).

Dependency files track headers by modification time, not content hashes.
Do not infer hardware performance from a successful build; see
[Coffeepot's hardware test guidance](https://github.com/estyseesghosts/coffeepot/blob/main/ctr/engineering/testing-on-hardware.md).
