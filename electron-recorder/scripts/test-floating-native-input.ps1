param([Parameter(Mandatory=$true)][string]$PointsJson)
$ErrorActionPreference = "Stop"
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RecorderNativePointer {
  [StructLayout(LayoutKind.Sequential)] public struct Point { public int X; public int Y; }
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(Point point);
  [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr window, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);
}
'@
[void][RecorderNativePointer]::SetThreadDpiAwarenessContext([IntPtr](-4))
$results = @()
foreach ($item in ($PointsJson | ConvertFrom-Json)) {
  [void][RecorderNativePointer]::SetCursorPos([int]$item.x, [int]$item.y)
  Start-Sleep -Milliseconds 80
  $point = [RecorderNativePointer+Point]::new()
  $point.X = [int]$item.x; $point.Y = [int]$item.y
  $window = [RecorderNativePointer]::WindowFromPoint($point)
  $root = [RecorderNativePointer]::GetAncestor($window, 2)
  $packed = (([long]$item.y -band 65535) -shl 16) -bor ([long]$item.x -band 65535)
  $hit = [RecorderNativePointer]::SendMessage($root, 0x84, [IntPtr]::Zero, [IntPtr]$packed)
  $results += @{ x=$item.x; y=$item.y; root=$root.ToInt64().ToString(); hitTest=$hit.ToInt64() }
  if ($item.button -eq "down") { [RecorderNativePointer]::mouse_event(2,0,0,0,[UIntPtr]::Zero) }
  if ($item.button -eq "up") { [RecorderNativePointer]::mouse_event(4,0,0,0,[UIntPtr]::Zero) }
  Start-Sleep -Milliseconds 80
}
$results | ConvertTo-Json -Compress
