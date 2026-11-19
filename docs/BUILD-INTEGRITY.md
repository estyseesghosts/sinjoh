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

This is part of [#14](https://github.com/estyseesghosts/sinjoh/issues/14),
not the complete build-integrity solution. Build-tree locking, independent
coordination of shared generators, artifact/toolchain provenance, flag/content
signatures and stronger cross-platform validation remain open. Dependency files
track included headers by modification time; they do not independently verify
content hashes, compiler flags, environment changes or externally edited
object files. Do not infer hardware performance from a successful build; see
[Coffeepot's hardware test guidance](https://github.com/estyseesghosts/coffeepot/blob/main/ctr/engineering/testing-on-hardware.md).
