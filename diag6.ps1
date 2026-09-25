# Reads the live schema tables inside this client.dll: locates each field's
# name string, finds the pointer to it in the schema field structs, and uses
# known-good fields (m_fFlags=0x3F4, m_pMovementServices=0x1248,
# m_hPlayerPawn=0x914) to calibrate which struct word holds the offset —
# then reports m_nButtons' offset and type from the user's own binary.
# Usage: powershell -File diag6.ps1

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

$snap = [P]::CreateToolhelp32Snapshot(0x8, $game.Id)
$me = New-Object P+MEPM
$me.dwSize = [Runtime.InteropServices.Marshal]::SizeOf($me)
$base = [IntPtr]::Zero; $size = 0
if ([P]::Module32FirstW($snap, [ref]$me)) {
  do {
    if ($me.szModule -ieq "client.dll") { $base = $me.modBaseAddr; $size = $me.ModBaseSize; break }
  } while ([P]::Module32NextW($snap, [ref]$me))
}
if ($base -eq [IntPtr]::Zero) { Write-Output "client.dll not found"; exit 1 }
$b = $base.ToInt64()
Write-Output ("client.dll = 0x{0:X} size=0x{1:X}" -f $b, $size)

# read the image in 1 MB chunks; unreadable chunks become zeros
$img = New-Object byte[] $size
$CH = 0x100000
for ($off = 0; $off -lt $size; $off += $CH) {
  $n = [math]::Min($CH, $size - $off)
  $c = ReadB ($b + $off) $n
  if ($null -ne $c) { [Array]::Copy($c, 0, $img, $off, $n) }
}
Write-Output "image loaded"

$ascii = [System.Text.Encoding]::ASCII.GetString($img)

# collect NUL-terminated occurrences of each field name
$names = "m_fFlags", "m_pMovementServices", "m_hPlayerPawn", "m_nButtons", "m_nImpulse", "m_iHealth", "m_vecAbsVelocity", "m_vecAbsOrigin"
$strIdx = @{}   # name -> list of file offsets
foreach ($nm in $names) {
  $hits = @()
  $p = $ascii.IndexOf($nm)
  while ($p -ge 0) {
    $end = $p + $nm.Length
    if ($end -ge $img.Length -or $img[$end] -eq 0) { $hits += $p }
    $p = $ascii.IndexOf($nm, $p + 1)
    if ($hits.Count -gt 6) { break }
  }
  $strIdx[$nm] = $hits
  Write-Output ("string '{0}': {1}" -f $nm, (($hits | ForEach-Object { "0x{0:X}" -f ($b + $_) }) -join " "))
}

# one pass over 8-aligned qwords collecting pointers to those strings
$want = @{}   # target address -> @{ name=; positions=@() }
foreach ($nm in $names) {
  foreach ($p in $strIdx[$nm]) {
    $addr = [uint64]($b + $p)
    if (-not $want.ContainsKey($addr)) { $want[$addr] = @{ name = $nm; positions = @() } }
  }
}
$pos = 0
$limit = $size - 8
while ($pos -le $limit) {
  if (($pos % 8) -ne 0) { $pos += 8; continue }
  $q = [BitConverter]::ToUInt64($img, $pos)
  if ($want.ContainsKey($q)) { $want[$q].positions += $pos }
  $pos += 8
}

function ReadStr($addr) {
  if ($addr -lt $b -or $addr -ge ($b + $size)) { return $null }
  $raw = ReadB $addr 64
  if ($null -eq $raw) { return $null }
  $end = [Array]::IndexOf($raw, [byte]0)
  if ($end -lt 0) { $end = 63 }
  return [System.Text.Encoding]::ASCII.GetString($raw, 0, $end)
}

foreach ($nm in $names) {
  $addrs = @()
  foreach ($p in $strIdx[$nm]) { $a = [uint64]($b + $p); if ($want.ContainsKey($a)) { $addrs += $a } }
  foreach ($a in $addrs) {
    foreach ($hitPos in $want[$a].positions) {
      $fb = $b + $hitPos          # field struct address
      $words = @()
      $tailU32 = @()
      for ($i = 0; $i -lt 0x40; $i += 8) {
        $w = ReadB ($fb + $i) 8
        if ($null -eq $w) { $words += "?"; continue }
        $words += ("{0:X16}" -f [BitConverter]::ToUInt64($w, 0))
      }
      for ($i = 0; $i -lt 0x40; $i += 4) {
        $w = ReadB ($fb + $i) 4
        if ($null -ne $w) { $tailU32 += ("+{0:X2}={1}" -f $i, [BitConverter]::ToUInt32($w, 0)) }
      }
      $typeStr = $null; $modStr = $null
      $t8 = ReadB ($fb + 8) 8
      $m10 = ReadB ($fb + 0x10) 8
      if ($null -ne $t8) { $typeStr = ReadStr ([BitConverter]::ToUInt64($t8, 0)) }
      if ($null -ne $m10) { $modStr = ReadStr ([BitConverter]::ToUInt64($m10, 0)) }
      Write-Output ("field struct for '{0}' @ 0x{1:X}" -f $nm, $fb)
      Write-Output ("    type = '{0}'  module = '{1}'" -f $typeStr, $modStr)
      Write-Output ("    u32 tail: " + ($tailU32 -join " "))
    }
  }
}
Write-Output "done"
