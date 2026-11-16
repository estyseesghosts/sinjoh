# probe_touch.ps1: run sinjoh and click the emulator window with the real
# mouse, to prove whether the guest receives touch positions at all.
# Screenshots stay in build/azahar/<Tag>/.
param(
  [string]$Artifact = "build/game/3ds/sinjoh.3dsx",
  [string]$Tag = "touchprobe",
  [int]$WaitSeconds = 70,
  [int]$Clicks = 12,
  [int]$ClickX = 396,
  [int]$ClickY = 760,
  [int]$IntervalMs = 2500
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
Add-Type -AssemblyName System.Drawing
$sig = @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
[DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int x, int y, int w, int h, bool repaint);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
public struct RECT { public int Left, Top, Right, Bottom; }
'@
if (-not ("P.T" -as [type])) { Add-Type -MemberDefinition $sig -Name "T" -Namespace "P" | Out-Null }
[P.T]::SetProcessDPIAware() | Out-Null
$out = Join-Path $repo (Join-Path "build/azahar" $Tag)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$p = Start-Process -FilePath "C:\Program Files\Azahar\azahar.exe" -ArgumentList "`"$repo\$Artifact`"" -PassThru
try {
  $h = [IntPtr]::Zero
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 100
    $p.Refresh()
    if ($p.MainWindowHandle -ne 0) { $h = $p.MainWindowHandle; break }
  }
  if ($h -eq [IntPtr]::Zero) { throw "no emulator window" }
  [P.T]::MoveWindow($h, 0, 0, 840, 1100, $true) | Out-Null
  [void][P.T]::SetForegroundWindow($h)
  function Shot([string]$name) {
    $r = New-Object P.T+RECT
    [P.T]::GetWindowRect($h, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
    $bmp = New-Object System.Drawing.Bitmap $w, $hh
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $dc = $g.GetHdc(); [P.T]::PrintWindow($h, $dc, 2) | Out-Null
    $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save((Join-Path $out "$name.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output "shot $name"
  }
  Start-Sleep -Seconds $WaitSeconds
  Shot "before"
  $r = New-Object P.T+RECT
  [P.T]::GetWindowRect($h, [ref]$r) | Out-Null
  for ($i = 0; $i -lt $Clicks; $i++) {
    [void][P.T]::SetCursorPos($r.Left + $ClickX, $r.Top + $ClickY)
    [P.T]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)  # left down
    Start-Sleep -Milliseconds 120
    [P.T]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)  # left up
    Start-Sleep -Milliseconds $IntervalMs
    if ($i -eq 2 -or $i -eq 7) { Shot ("click{0}" -f $i) }
  }
  Shot "after"
} finally {
  if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
}
