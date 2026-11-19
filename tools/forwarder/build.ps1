# build.ps1: build the Sinjoh Platinum HOME Menu forwarder (CIA).
#
#   pwsh tools/forwarder/build.ps1
#   pwsh tools/forwarder/build.ps1 -Makerom C:\tools\makerom.exe -Bannertool C:\tools\bannertool.exe
#
# Needs devkitARM + libctru (devkitPro), makerom and bannertool. The two
# packagers are not part of devkitPro: pass them, put them on PATH, or set
# SINJOH_CIA_TOOLS to the folder that holds both.
param(
  [string]$Makerom = "",
  [string]$Bannertool = "",
  [string]$OutDir = "build/forwarder"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $repo

$devkit = "C:\devkitPro"
if ($env:DEVKITPRO -and (Test-Path -LiteralPath $env:DEVKITPRO)) { $devkit = $env:DEVKITPRO }
$gcc = Join-Path $devkit "devkitARM\bin\arm-none-eabi-gcc.exe"
$libctru = Join-Path $devkit "libctru"
foreach ($p in $gcc, $libctru) {
  if (-not (Test-Path -LiteralPath $p)) { throw "missing $p; install devkitPro devkitARM" }
}

function Find-Tool([string]$name, [string]$given) {
  if ($given) {
    if (-not (Test-Path -LiteralPath $given)) { throw "no $name at $given" }
    return (Resolve-Path -LiteralPath $given).Path
  }
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  if ($env:SINJOH_CIA_TOOLS) {
    $candidate = Join-Path $env:SINJOH_CIA_TOOLS "$name.exe"
    if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
  }
  throw "$name not found; pass -$(if ($name -eq 'makerom') {'Makerom'} else {'Bannertool'}), put it on PATH, or set SINJOH_CIA_TOOLS"
}

$makerom = Find-Tool "makerom" $Makerom
$bannertool = Find-Tool "bannertool" $Bannertool
$src = Join-Path $repo "tools\forwarder"
$out = Join-Path $repo $OutDir
New-Item -ItemType Directory -Force -Path $out | Out-Null

$elf = Join-Path $out "sinjoh-forwarder.elf"
$specs = Join-Path $devkit "devkitARM\arm-none-eabi\lib\3dsx.specs"
& $gcc -march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft -O2 -D__3DS__ `
  "-I$libctru\include" "-specs=$specs" "-L$libctru\lib" `
  (Join-Path $src "main.c") -lctru -lm -o $elf
if ($LASTEXITCODE -ne 0) { throw "compile failed" }

$banner = Join-Path $out "banner.bnr"
$icon = Join-Path $out "icon.smdh"
& $bannertool makebanner -i (Join-Path $src "banner.png") -a (Join-Path $src "silence.wav") -o $banner
if ($LASTEXITCODE -ne 0) { throw "banner failed" }
& $bannertool makesmdh -s "Sinjoh Platinum" -l "Sinjoh Platinum" -p sinjoh `
  -i (Join-Path $src "icon.png") -o $icon
if ($LASTEXITCODE -ne 0) { throw "icon failed" }

$cia = Join-Path $out "sinjoh-platinum.cia"
& $makerom -f cia -o $cia -target t -exefslogo -rsf (Join-Path $src "forwarder.rsf") `
  -elf $elf -banner $banner -icon $icon -major 0 -minor 0 -micro 2
if ($LASTEXITCODE -ne 0) { throw "makerom failed" }

$size = (Get-Item -LiteralPath $cia).Length
Write-Output "built $cia ($size bytes)"
