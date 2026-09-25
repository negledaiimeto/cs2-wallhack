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
function U64($a) { $b = ReadB $a 8; if ($null -eq $b) { return $null }; [BitConverter]::ToUInt64($b,0) }
function U32($a) { $b = ReadB $a 4; if ($null -eq $b) { return $null }; [BitConverter]::ToUInt32($b,0) }
function U8($a)  { $b = ReadB $a 1; if ($null -eq $b) { return $null }; [int]$b[0] }
function F32($a) { $b = ReadB $a 4; if ($null -eq $b) { return $null }; [BitConverter]::ToSingle($b,0) }
function Hex($v) { if ($null -eq $v) { return "null" }; ("0x{0:X}" -f [int64]$v) }

# client.dll base
$snap = [P]::CreateToolhelp32Snapshot(0x8, $game.Id)
$me = New-Object P+MEPM
$me.dwSize = [Runtime.InteropServices.Marshal]::SizeOf($me)
$base = [IntPtr]::Zero
if ([P]::Module32FirstW($snap, [ref]$me)) {
  do {
    if ($me.szModule -ieq "client.dll") { $base = $me.modBaseAddr; break }
  } while ([P]::Module32NextW($snap, [ref]$me))
}
if ($base -eq [IntPtr]::Zero) { Write-Output "client.dll not found"; exit 1 }
$client = $base.ToInt64()
Write-Output ("client.dll base = " + (Hex $client))

# verified offsets
$listOff   = 0x2577BE0
$ctrlOff   = 0x23A78D0
$pawnOff   = 0x23CCC08
$isLocal   = 0x788
$aliveOff  = 0x91C
$handleOff = 0x914

function Walk($listBase, $idx) {
  $idx = $idx -band 0x7FFF
  if ($null -eq $listBase -or $listBase -eq 0 -or $idx -eq 0) { return $null }
  $chunk = U64 ($listBase + 0x10 + 8 * ($idx -shr 9))
  if ($null -eq $chunk -or $chunk -eq 0) { return $null }
  return (U64 ($chunk + 0x70 * ($idx -band 0x1FF)))
}

$list = U64 ($client + $listOff)
Write-Output ("dwEntityList global = " + (Hex $list))

$ctrl = U64 ($client + $ctrlOff)
Write-Output ("controller = " + (Hex $ctrl))
if ($null -eq $ctrl -or $ctrl -eq 0) { Write-Output "controller null (menu?)"; exit 0 }

$isLoc = U8 ($ctrl + $isLocal)
$alive = U8 ($ctrl + $aliveOff)
$handle = U32 ($ctrl + $handleOff)
Write-Output ("isLocal=$isLoc alive=$alive handle=" + (Hex $handle))
if ($alive -ne 1) { Write-Output "NOT ALIVE - spawn for a meaningful probe" }

$idx = if ($null -ne $handle) { $handle -band 0x7FFF } else { 0 }
Write-Output ("handle index = $idx")

$walked = Walk $list $idx
Write-Output ("walked pawn    = " + (Hex $walked))
$gpawn = U64 ($client + $pawnOff)
Write-Output ("global pawn    = " + (Hex $gpawn))
if ($null -ne $walked -and $walked -ne 0 -and $walked -eq $gpawn) {
  Write-Output "IDENTITY: MATCH (walk == global) => walk is the local pawn"
} else {
  Write-Output "IDENTITY: MISMATCH => walk returns a different entity than the local-pawn global"
}

$p = $walked
if ($null -eq $p -or $p -eq 0) { $p = $gpawn }
if ($null -eq $p -or $p -eq 0) { Write-Output "no pawn to inspect"; exit 0 }

$flags = U32 ($p + 0x3F4)
$life  = U8  ($p + 0x354)
$hpE   = U32 ($p + 0x34C)          # m_iHealth on C_BaseEntity (entity itself)
$node  = U64 ($p + 0x330)
$hpN   = if ($null -ne $node -and $node -ne 0) { U32 ($node + 0x34C) } else { $null }
Write-Output ("pawn: flags=" + (Hex $flags) + " lifeState=$life hp(entity)=$hpE hp(node+34C)=$hpN node=" + (Hex $node))
if ($null -ne $node -and $node -ne 0) {
  $ox = F32 ($node + 0xC8); $oy = F32 ($node + 0xCC); $oz = F32 ($node + 0xD0)
  Write-Output ("origin via node+0xC8 = ($ox, $oy, $oz)")
}

$ms = U64 ($p + 0x1248)
Write-Output ("movSvc ptr = " + (Hex $ms) + " aligned8=" + (($ms -band 7) -eq 0))
if ($null -ne $ms -and $ms -ne 0) {
  $btn = U32 ($ms + 0x50)
  Write-Output ("buttons at ms+0x50 = " + (Hex $btn))
  $dump = ReadB $ms 0x70
  if ($null -ne $dump) {
    for ($r = 0; $r -lt 7; $r++) {
      $row = ($dump[($r*16)..($r*16+15)] | ForEach-Object { "{0:X2}" -f $_ }) -join " "
      Write-Output ("ms+{0:X2}: {1}" -f ($r*16), $row)
    }
  } else { Write-Output "ms unreadable" }
}

# cross-check: what the local-pawn global itself points at
if ($null -ne $gpawn -and $gpawn -ne 0 -and $gpawn -ne $p) {
  $ms2 = U64 ($gpawn + 0x1248)
  $fl2 = U32 ($gpawn + 0x3F4)
  $hp2 = U32 ($gpawn + 0x34C)
  $lf2 = U8  ($gpawn + 0x354)
  $node2 = U64 ($gpawn + 0x330)
  Write-Output ("global pawn fields: flags=" + (Hex $fl2) + " life=$lf2 hp=$hp2 node=" + (Hex $node2))
  Write-Output ("global pawn movSvc = " + (Hex $ms2))
  if ($null -ne $ms2 -and $ms2 -ne 0) {
    $btn2 = U32 ($ms2 + 0x50)
    Write-Output ("global pawn buttons = " + (Hex $btn2))
    $d2 = ReadB $ms2 0x70
    if ($null -ne $d2) {
      for ($r = 0; $r -lt 7; $r++) {
        $row = ($d2[($r*16)..($r*16+15)] | ForEach-Object { "{0:X2}" -f $_ }) -join " "
        Write-Output ("gms+{0:X2}: {1}" -f ($r*16), $row)
      }
    }
  }
}
