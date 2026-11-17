#!/usr/bin/env bash
# build.sh: build the Sinjoh Platinum HOME Menu forwarder (CIA) on Linux/macOS.
#
#   tools/forwarder/build.sh
#   OUT_DIR=/tmp/fw tools/forwarder/build.sh
#
# Needs devkitARM (devkitPro), makerom and bannertool on PATH. The Windows
# equivalent is tools/forwarder/build.ps1; both produce the same CIA.
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)
cd "$repo"
out=${OUT_DIR:-build/forwarder}
src=tools/forwarder
mkdir -p "$out"

devkitpro=${DEVKITPRO:-/opt/devkitpro}
devkitarm=${DEVKITARM:-$devkitpro/devkitARM}
gcc=${CC:-arm-none-eabi-gcc}
specs=$devkitarm/arm-none-eabi/lib/3dsx.specs
libctru=$devkitpro/libctru

for tool in "$gcc" makerom bannertool; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "missing $tool: install devkitPro devkitARM, and put makerom and bannertool on PATH" >&2
        exit 1
    }
done

"$gcc" -march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft -O2 -D__3DS__ \
    -I"$libctru/include" -specs="$specs" -L"$libctru/lib" \
    "$src/main.c" -lctru -lm -o "$out/sinjoh-forwarder.elf"

bannertool makebanner -i "$src/banner.png" -a "$src/silence.wav" -o "$out/banner.bnr"
bannertool makesmdh -s "Sinjoh Platinum" -l "Sinjoh Platinum" -p sinjoh \
    -i "$src/icon.png" -o "$out/icon.smdh"

makerom -f cia -o "$out/sinjoh-platinum.cia" -target t -exefslogo \
    -rsf "$src/forwarder.rsf" \
    -elf "$out/sinjoh-forwarder.elf" \
    -banner "$out/banner.bnr" \
    -icon "$out/icon.smdh" \
    -major 0 -minor 0 -micro 1

echo "built $out/sinjoh-platinum.cia ($(wc -c <"$out/sinjoh-platinum.cia") bytes)"
