# build.ps1: build sinjoh on Windows.
#
#   pwsh tools/build.ps1                  release build (instrumentation off)
#   pwsh tools/build.ps1 -Profile 1       measurement build (perf counters on)
#   pwsh tools/build.ps1 -All             both, side by side
#   pwsh tools/build.ps1 -Jobs 8
#
# The two profiles use separate build trees: build/game/3ds for the release
# (sinjoh-platinum.3dsx) and build/game/3ds-prof for the instrumented debug
# build (sinjoh-platinum-dbg.3dsx), as do libnitro and libnitrosystem. That is
# what keeps a later build from reusing objects compiled under the other
# profile's flags.
#
# Runs make inside devkitPro's MSYS2 shell, with Git for Windows first on
# PATH: MSYS2's own git cannot fetch over HTTPS, and the build regenerates
# headers with git-backed tools.
param(
  [int]$Profile = 0,
  [int]$Jobs = 8,
  [switch]$Clean,
  [switch]$WideArtDebug,
  [switch]$All
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$bash = "C:\devkitPro\msys2\usr\bin\bash.exe"
if (-not (Test-Path -LiteralPath $bash)) { throw "devkitPro MSYS2 bash not found at $bash" }
$unix = (& $bash -lc "cygpath -u '$repo'").Trim()
$wideart = if ($WideArtDebug) { " WIDEART_DEBUG=1" } else { "" }
$profiles = if ($All) { @(0, 1) } else { @($Profile) }
foreach ($p in $profiles) {
  $suffix = if ($p -eq 1) { "-prof" } else { "" }
  # tools/build.sh takes the per-tree build lock (#14) around make.
  $cleanEnv = if ($Clean) { "SINJOH_CLEAN=1 " } else { "" }
  $cmd = 'export PATH="/c/Program Files/Git/cmd:$PATH"; cd ' + "'" + $unix + "'" + " && ${cleanEnv}sh tools/build.sh $p$wideart -j$Jobs"
  & $bash -lc $cmd
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
foreach ($p in $profiles) {
  $suffix = if ($p -eq 1) { "-prof" } else { "" }
  $name = if ($p -eq 1) { "sinjoh-platinum-dbg" } else { "sinjoh-platinum" }
  Write-Output "built $repo\build\game\3ds$suffix\$name.3dsx"
}
