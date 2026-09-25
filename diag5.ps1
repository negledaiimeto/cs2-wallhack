# Probe v2: hold synthetic Space (IN_JUMP = 2) and diff every service-cluster
# object on the pawn; reports origin delta as proof the game consumed input.
# Usage: powershell -File diag5.ps1

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class P {
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern IntPtr OpenProcess(int dwDesiredAccess, bool bInheritHandle, int dwProcessId);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer, int nSize, out int lpNumberOfBytesRead);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern IntPtr CreateToolhelp32Snapshot(uint dwFlags, uint th32ProcessID);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool Module32FirstW(IntPtr hSnapshot, ref MEPM lpme);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool Module32NextW(IntPtr hSnapshot, ref MEPM lpme);
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct MEPM {
    public uint dwSize;
    public uint th32ModuleID;
    public uint th32ProcessID;
    public uint GlblcntUsage;
    public uint PtrcntUsage;
    public IntPtr modBaseAddr;
    public uint ModBaseSize;
    public IntPtr hModule;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string szModule;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szExePath;
  }
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

$game = Get-Process cs2 -ErrorAction Stop
$script:h = [P]::OpenProcess(0x10, $false, $game.Id)
if ($script:h -eq [IntPtr]::Zero) { Write-Output "OpenProcess failed"; exit 1 }

function ReadB($addr, $n) {
  $buf = New-Object byte[] $n
  $read = 0
  $ok = [P]::ReadProcessMemory($script:h, [IntPtr]([int64]$addr), $buf, $n, [ref]$read)
  if (-not $ok -or $read -ne $n) { return $null }
  return $buf
}
function U64($a) { $b = ReadB $a 8; if ($null -eq $b) { return $null }; [BitConverter]::ToUInt64($b,0) }
function U8($a)  { $b = ReadB $a 1; if ($null -eq $b) { return $null }; [int]$b[0] }
function F32($a) { $b = ReadB $a 4; if ($null -eq $b) { return $null }; [BitConverter]::ToSingle($b,0) }
function Hex($v) { if ($null -eq $v) { return "null" }; ("0x{0:X}" -f [int64]$v) }

$snap = [P]::CreateToolhelp32Snapshot(0x8, $game.Id)
$me = New-Object P+MEPM
$me.dwSize = [Runtime.InteropServices.Marshal]::SizeOf($me)
$base = [IntPtr]::Zero
if ([P]::Module32FirstW($snap, [ref]$me)) {
  do { if ($me.szModule -ieq "client.dll") { $base = $me.modBaseAddr; break } }
  while ([P]::Module32NextW($snap, [ref]$me))
}
if ($base -eq [IntPtr]::Zero) { Write-Output "client.dll not found"; exit 1 }
$client = $base.ToInt64()

$ctrl = U64 ($client + 0x23A78D0)
if ($null -eq $ctrl -or $ctrl -eq 0) { Write-Output "controller null"; exit 1 }
$alive = U8 ($ctrl + 0x91C)
$handle = $null
$hb = ReadB ($ctrl + 0x914) 4
if ($null -ne $hb) { $handle = [BitConverter]::ToUInt32($hb, 0) }
Write-Output ("alive=$alive handle=" + (Hex $handle))
if ($alive -ne 1) { Write-Output "NOT ALIVE - the probe needs a spawned player"; exit 1 }

$list = U64 ($client + 0x2577BE0)
$idx = ($handle -band 0x7FFF)
$chunk = U64 ($list + 0x10 + 8 * ($idx -shr 9))
$pawn = U64 ($chunk + 0x70 * ($idx -band 0x1FF))
Write-Output ("pawn = " + (Hex $pawn))
if ($null -eq $pawn -or $pawn -eq 0) { Write-Output "pawn walk failed"; exit 1 }

function Origin($pw) {
  $node = U64 ($pw + 0x330)
  if ($null -eq $node -or $node -eq 0) { return $null }
  ,@((F32 ($node + 0xC8)), (F32 ($node + 0xCC)), (F32 ($node + 0xD0)))
}

$offsets = @(0x11F0..0x1280 | Where-Object { ($_ -band 7) -eq 0 })
$ptrs = @{}
foreach ($o in $offsets) {
  $p = U64 ($pawn + $o)
  if ($null -ne $p -and $p -gt 0x10000 -and $p -lt 0x00007FFFFFFFFFFF -and (($p -band 7) -eq 0)) { $ptrs[$o] = $p }
}
Write-Output ("service ptrs: " + (($ptrs.Keys | Sort-Object | ForEach-Object { "0x{0:X}" -f $_ }) -join " "))

function Snap([hashtable]$map, $len) {
  $s = @{}
  foreach ($k in $map.Keys) { $s[$k] = ReadB $map[$k] $len }
  return $s
}
$LEN = 0x100
$org0 = Origin $pawn
$before = Snap $ptrs $LEN

$prev = [P]::GetForegroundWindow()
[void][P]::SetForegroundWindow($game.MainWindowHandle)
Start-Sleep -Milliseconds 300

[P]::keybd_event(0x20, 0, 0, [UIntPtr]::Zero)     # Space down (IN_JUMP)
Start-Sleep -Milliseconds 700
$mid = Snap $ptrs $LEN
[P]::keybd_event(0x20, 0, 2, [UIntPtr]::Zero)     # Space up
Start-Sleep -Milliseconds 300
$org1 = Origin $pawn
[void][P]::SetForegroundWindow($prev)

Write-Output ("origin0 = (" + ($org0 -join ", ") + ")")
Write-Output ("origin1 = (" + ($org1 -join ", ") + ")")
if ($null -ne $org0 -and $null -ne $org1) {
  $dx = [math]::Abs($org1[0] - $org0[0]); $dy = [math]::Abs($org1[1] - $org0[1]); $dz = [math]::Abs($org1[2] - $org0[2])
  Write-Output ("origin delta = ($dx, $dy, $dz)")
}

foreach ($o in ($before.Keys | Sort-Object)) {
  $a = $before[$o]; $b = $mid[$o]
  if ($null -eq $a -or $null -eq $b) { continue }
  $changed = @()
  for ($i = 0; $i -lt $LEN; $i += 4) {
    $va = [BitConverter]::ToUInt32($a, $i)
    $vb = [BitConverter]::ToUInt32($b, $i)
    if ($va -ne $vb) { $changed += ("+0x{0:X2}: {1} -> {2}  (low16 {3} -> {4})" -f $i, (Hex $va), (Hex $vb), (Hex ($va -band 0xFFFF)), (Hex ($vb -band 0xFFFF))) }
  }
  if ($changed.Count -gt 0) {
    Write-Output ("obj@pawn+0x{0:X} = {1} RESPONDS:" -f $o, (Hex $ptrs[$o]))
    $changed | ForEach-Object { Write-Output ("    " + $_) }
  }
}

# explicit window of interest on the movement-services object
if ($ptrs.ContainsKey(0x1248)) {
  $a = $before[0x1248]; $b = $mid[0x1248]
  if ($null -ne $a -and $null -ne $b) {
    Write-Output "obj@1248 u32[0x40..0x6C] before -> during:"
    for ($i = 0x40; $i -le 0x6C; $i += 4) {
      $va = [BitConverter]::ToUInt32($a, $i)
      $vb = [BitConverter]::ToUInt32($b, $i)
      $mark = if ($va -ne $vb) { "  <== CHANGED" } else { "" }
      Write-Output ("    +0x{0:X2}: {1} -> {2}{3}" -f $i, (Hex $va), (Hex $vb), $mark)
    }
  }
}
Write-Output "done"
