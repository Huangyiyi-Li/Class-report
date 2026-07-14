param(
  [Parameter(Mandatory = $true)]
  [string]$AppPath,
  [string]$TestRoot = "",
  [int]$TimeoutSeconds = 45
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
  throw "Packaged normal-start verification requires Windows."
}

$app = (Resolve-Path -LiteralPath $AppPath).Path
$workerExe = Join-Path (Split-Path $app -Parent) "resources\worker\ClassroomRecorderWorker.exe"
if (-not (Test-Path -LiteralPath $workerExe -PathType Leaf)) {
  throw "Packaged worker is missing: $workerExe"
}

$systemDriveValue = if ($env:SystemDrive) { $env:SystemDrive } else { "C:" }
$systemDrive = ($systemDriveValue.TrimEnd("\")).ToUpperInvariant()
if (-not $TestRoot) {
  $testDrive = Get-PSDrive -PSProvider FileSystem |
    Where-Object { $_.Root -and $_.Name.ToUpperInvariant() -ne $systemDrive.TrimEnd(":") -and $_.Free -gt 6GB } |
    Sort-Object Free -Descending |
    Select-Object -First 1
  if (-not $testDrive) {
    throw "No writable non-system drive with at least 6 GiB is available for the packaged normal-start fixture."
  }
  $TestRoot = Join-Path $testDrive.Root "classroom-recorder-normal-start-$([guid]::NewGuid().ToString('N'))"
}

$testRootFull = [IO.Path]::GetFullPath($TestRoot)
$testDriveRoot = [IO.Path]::GetPathRoot($testRootFull).TrimEnd("\").ToUpperInvariant()
if ($testDriveRoot -eq $systemDrive) {
  throw "Packaged normal-start fixture must not use the system drive: $testRootFull"
}
if (Test-Path -LiteralPath $testRootFull) {
  throw "Packaged normal-start fixture already exists: $testRootFull"
}

$dataRoot = Join-Path $testRootFull "data"
$userData = Join-Path $testRootFull "user-data"
$configDir = Join-Path $dataRoot ".classroom-recorder"
$configPath = Join-Path $configDir "worker-config.json"
$runtimeDir = Join-Path $dataRoot "runtime"
$stdout = Join-Path $testRootFull "electron.stdout.log"
$stderr = Join-Path $testRootFull "electron.stderr.log"
$utf8NoBom = New-Object Text.UTF8Encoding($false)
$initialAppIds = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $app } | ForEach-Object Id)
$initialWorkerIds = @(Get-Process -Name ClassroomRecorderWorker -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $workerExe } | ForEach-Object Id)
$tcp = $null

try {
  New-Item -ItemType Directory -Force -Path $configDir, $runtimeDir, $userData | Out-Null
  $config = [ordered]@{
    data_root = $dataRoot
    base_url = "https://rest.xxt.cn"
    device_no = ""
    school_id = $null
    location_id = ""
    location_name = ""
    segment_seconds = 300
    checkpoint_seconds = 10
    auto_record_enabled = $false
    input_device = ""
    username = ""
    password = ""
    mirror_server_url = ""
  }
  [IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json), $utf8NoBom)
  $locator = [ordered]@{ configPath = $configPath; dataRoot = $dataRoot }
  [IO.File]::WriteAllText((Join-Path $userData "worker-config-locator.json"), ($locator | ConvertTo-Json), $utf8NoBom)

  Remove-Item Env:ELECTRON_SMOKE_TEST -ErrorAction SilentlyContinue
  $process = Start-Process -FilePath $app -ArgumentList "--user-data-dir=$userData", "--enable-logging" -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $endpointPath = Join-Path $runtimeDir "worker-endpoint.json"
  $tokenPath = Join-Path $runtimeDir "worker-token"
  do {
    if ($process.HasExited) {
      throw "Packaged application exited before the real worker became ready (exit $($process.ExitCode))."
    }
    $workers = @(Get-Process -Name ClassroomRecorderWorker -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $workerExe -and $_.Id -notin $initialWorkerIds })
    if ($workers.Count -gt 0 -and (Test-Path -LiteralPath $endpointPath) -and (Test-Path -LiteralPath $tokenPath)) { break }
    Start-Sleep -Milliseconds 200
  } while ((Get-Date) -lt $deadline)

  if ($workers.Count -eq 0) { throw "Real packaged worker did not start." }
  if (-not (Test-Path -LiteralPath $endpointPath) -or -not (Test-Path -LiteralPath $tokenPath)) {
    throw "Real packaged worker did not publish its authenticated endpoint."
  }

  $endpoint = Get-Content -Raw -Encoding utf8 $endpointPath | ConvertFrom-Json
  if ($endpoint.host -ne "127.0.0.1" -or -not ($endpoint.port -as [int])) {
    throw "Worker endpoint is not a valid loopback endpoint."
  }
  $token = (Get-Content -Raw -Encoding utf8 $tokenPath).Trim()
  if ($token.Length -lt 32) { throw "Worker control token is invalid." }

  $tcp = New-Object Net.Sockets.TcpClient
  $connect = $tcp.ConnectAsync($endpoint.host, [int]$endpoint.port)
  if (-not $connect.Wait([Math]::Min($TimeoutSeconds * 1000, 10000))) {
    throw "Timed out connecting to the real packaged worker."
  }
  $stream = $tcp.GetStream()
  $stream.ReadTimeout = 10000
  $writer = New-Object IO.StreamWriter($stream, $utf8NoBom, 1024, $true)
  $writer.AutoFlush = $true
  $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8, $false, 1024, $true)
  $writer.WriteLine((@{ token = $token } | ConvertTo-Json -Compress))
  $ready = $reader.ReadLine() | ConvertFrom-Json
  if ($ready.event -ne "ready") { throw "Worker authentication did not return a ready snapshot." }

  Start-Sleep -Seconds 1
  $workers = @(Get-Process -Name ClassroomRecorderWorker -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $workerExe -and $_.Id -notin $initialWorkerIds })
  $visibleWorkers = @($workers | Where-Object { $_.MainWindowHandle -ne 0 })
  if ($visibleWorkers.Count -gt 0) { throw "Packaged worker opened a visible console window." }

  Write-Host "Packaged normal start passed: Electron PID $($process.Id), worker PID(s) $($workers.Id -join ','), authenticated state $($ready.payload.health)."
} finally {
  if ($tcp) { $tcp.Dispose() }
  $cleanupDeadline = (Get-Date).AddSeconds(10)
  do {
    $testProcesses = @(Get-Process -ErrorAction SilentlyContinue |
      Where-Object { ($_.Path -eq $app -and $_.Id -notin $initialAppIds) -or ($_.Path -eq $workerExe -and $_.Id -notin $initialWorkerIds) } |
      Sort-Object StartTime -Descending)
    foreach ($testProcess in $testProcesses) {
      Stop-Process -Id $testProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($testProcesses.Count -gt 0) { Start-Sleep -Milliseconds 250 }
  } while ($testProcesses.Count -gt 0 -and (Get-Date) -lt $cleanupDeadline)
  $leaf = Split-Path $testRootFull -Leaf
  if ((Test-Path -LiteralPath $testRootFull) -and $leaf.StartsWith("classroom-recorder-normal-start-")) {
    do {
      Remove-Item -LiteralPath $testRootFull -Recurse -Force -ErrorAction SilentlyContinue
      if (Test-Path -LiteralPath $testRootFull) { Start-Sleep -Milliseconds 250 }
    } while ((Test-Path -LiteralPath $testRootFull) -and (Get-Date) -lt $cleanupDeadline)
    if (Test-Path -LiteralPath $testRootFull) {
      throw "Packaged normal-start fixture cleanup timed out: $testRootFull"
    }
  }
}
