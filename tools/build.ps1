# build.ps1: build sinjoh on Windows.
#
#   pwsh tools/build.ps1                  release build (instrumentation off)
#   pwsh tools/build.ps1 -Profile 1       measurement build (perf counters on)
#   pwsh tools/build.ps1 -Jobs 8
#
# Runs make inside devkitPro's MSYS2 shell, with Git for Windows first on
# PATH: MSYS2's own git cannot fetch over HTTPS, and the build regenerates
# headers with git-backed tools.
param(
  [int]$Profile = 0,
  [int]$Jobs = 8,
  [switch]$Clean,
  [switch]$WideArtDebug
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$bash = "C:\devkitPro\msys2\usr\bin\bash.exe"
if (-not (Test-Path -LiteralPath $bash)) { throw "devkitPro MSYS2 bash not found at $bash" }
$unix = (& $bash -lc "cygpath -u '$repo'").Trim()
$cleanCmd = if ($Clean) { "rm -rf build/game/3ds && " } else { "" }
$wideart = if ($WideArtDebug) { " WIDEART_DEBUG=1" } else { "" }
$cmd = 'export PATH="/c/Program Files/Git/cmd:$PATH"; cd ' + "'" + $unix + "'" + " && ${cleanCmd}make -f engine/game.mk TARGET=3ds program PROFILE=$Profile$wideart -j$Jobs"
& $bash -lc $cmd
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "built $repo\build\game\3ds\sinjoh.3dsx"
