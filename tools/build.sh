#!/bin/sh
# build.sh: build one sinjoh profile under the per-tree build lock (#14).
#
#   tools/build.sh 0 [make args...]        release  -> build/game/3ds
#   tools/build.sh 1 [make args...]        profile  -> build/game/3ds-prof
#   SINJOH_CLEAN=1 tools/build.sh 0        remove the trees first (locked)
#
# tools/build_guard.py holds an OS lock on <tree>/.build.lock while make
# runs; a second build of the same tree fails at once and names the holder.
# The release and profile trees lock separately and can build in parallel.
# The lock is released by the OS when make exits or is killed.
set -eu
profile=${1:?usage: tools/build.sh <0|1> [make args...]}
shift
root=$(cd "$(dirname "$0")/.." && pwd)
suffix=
[ "$profile" = 1 ] && suffix=-prof
tree="$root/build/game/3ds$suffix"
cd "$root"
clean=:
if [ "${SINJOH_CLEAN:-0}" = 1 ]; then
    clean="rm -rf build/game/3ds$suffix/* engine/compat/nitro/build/3ds$suffix engine/compat/nitrosystem/build/3ds$suffix"
fi
exec python3 tools/build_guard.py lock --tree "$tree" -- \
    sh -c "$clean && exec make -f engine/game.mk TARGET=3ds program PROFILE=$profile \"\$@\"" sh "$@"
