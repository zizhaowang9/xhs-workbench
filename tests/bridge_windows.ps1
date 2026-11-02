param([Parameter(Mandatory = $true)][string]$Root)
$ErrorActionPreference = 'Stop'
. (Join-Path $Root 'installer\common.ps1')

function Assert-Bridge($condition, [string]$message) {
    if (-not $condition) { throw $message }
}

$cfgPath = Join-Path $Root 'config\paths.json'
$originalConfig = [IO.File]::ReadAllBytes($cfgPath)
$cfg = Read-Config $Root
$runner = $null
$serverPid = $null
$port = $null
$logDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$runnerOut = Join-Path $logDir 'bridge-smoke-runner.out.log'
$runnerErr = Join-Path $logDir 'bridge-smoke-runner.err.log'

try {
    # Only use a free test port. Never take over a running workbench or browser.
    $listener = New-Object System.Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    $cfg.bridge_port = $port
    $cfg.bridge_url = 'ws://localhost:' + $port
    Save-ConfigUtf8 $cfgPath $cfg

    $runnerFile = Join-Path $Root 'installer\run_bridge.ps1'
    $arguments = '-NoProfile -NoLogo -ExecutionPolicy Bypass -File "' + $runnerFile + '" -Root "' + $Root + '" -NoPause'
    $runner = Start-Process powershell.exe -ArgumentList $arguments -PassThru -RedirectStandardOutput $runnerOut -RedirectStandardError $runnerErr
    $deadline = (Get-Date).AddSeconds(25)
    $probe = $null
    do {
        Start-Sleep -Milliseconds 300
        if ($runner.HasExited) { break }
        $probe = Test-BridgeProbe $Root $port $cfg
        if ($probe -and $probe.reachable) { break }
    } while ((Get-Date) -lt $deadline)
    Assert-Bridge ($probe -and $probe.reachable) 'Actual run_bridge.ps1 did not start a healthy Bridge.'
    $serverPid = [int]$probe.pid
    Assert-Bridge ($serverPid -gt 0) 'Bridge did not return its PID.'
    Assert-Bridge ($probe.root -eq $Root) 'Bridge root did not preserve the Chinese/space installation path.'
    Assert-Bridge ($probe.script_path -eq (Get-BridgeScriptPath $Root $cfg)) 'Bridge script identity differs from installation.'
    Assert-Bridge ($probe.extension -eq $false) 'No browser extension should be attached in CI.'
    $owned = Test-BridgeOfRoot $Root $port $cfg
    Assert-Bridge ($owned.SameRoot -eq $true -and $owned.Healthy -eq $true) 'Healthy installed Bridge was not recognized.'
    Assert-Bridge ([int]$owned.Owner.Pid -eq $serverPid) 'Ping PID differs from the actual Windows listener.'

    # A real second launcher invocation must reuse this PID, not create another server.
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'installer\start_bridge.ps1') -Root $Root
    Assert-Bridge ($LASTEXITCODE -eq 0) 'Second launcher invocation failed to reuse the actual Bridge.'
    $again = Test-BridgeProbe $Root $port $cfg
    Assert-Bridge ($again.reachable -and [int]$again.pid -eq $serverPid) 'Second launcher replaced or lost the original Bridge.'

    # Compare the same real service against another expected installation.
    $otherCfg = $cfg | ConvertTo-Json -Depth 6 | ConvertFrom-Json
    $otherCfg.xhs_repo = Join-Path ($Root + '-other') 'tools\xiaohongshu-skills'
    $foreign = Test-BridgeOfRoot ($Root + '-other') $port $otherCfg
    Assert-Bridge ($foreign.SameRoot -eq $false -and $foreign.Healthy -eq $true) 'Foreign installation was not rejected.'
    Write-Host 'PASS: actual Windows runner, healthy ping, Chinese/space path, same/foreign identity and repeated launcher reuse.'

    # Exercise a real argparse failure: the runner must return native exit code 2.
    $badRoot = Join-Path $Root 'tmp\Bridge 参数失败'
    $badCfg = $cfg | ConvertTo-Json -Depth 6 | ConvertFrom-Json
    $badCfg.root = $badRoot
    $badCfg.bridge_port = 'not-a-port'
    $badCfg.logs_dir = Join-Path $badRoot 'logs'
    Save-ConfigUtf8 (Join-Path $badRoot 'config\paths.json') $badCfg
    $badArgs = '-NoProfile -NoLogo -ExecutionPolicy Bypass -File "' + $runnerFile + '" -Root "' + $badRoot + '" -NoPause'
    $bad = Start-Process powershell.exe -ArgumentList $badArgs -PassThru -Wait -RedirectStandardOutput (Join-Path $logDir 'bridge-smoke-failure.out.log') -RedirectStandardError (Join-Path $logDir 'bridge-smoke-failure.err.log')
    Assert-Bridge ($bad.ExitCode -eq 2) ('Runner hid the native failure: ' + $bad.ExitCode)
    Write-Host 'PASS: actual invalid-port process returns exit code 2 through the shipped runner.'
}
catch {
    foreach ($file in @($runnerOut, $runnerErr)) {
        if (Test-Path -LiteralPath $file) { Get-Content -LiteralPath $file -Tail 60 -Encoding UTF8 | Write-Host }
    }
    throw
}
finally {
    # Stop only the test-owned listener and runner. Restore the original config.
    if ($port) {
        $owner = Get-PortOwner $port
        $expected = Get-BridgeScriptPath $Root $cfg
        if ($owner -and $owner.CommandLine -and ([string]$owner.CommandLine).Contains($expected)) {
            Stop-Process -Id $owner.Pid -ErrorAction SilentlyContinue
        }
    }
    if ($runner -and -not $runner.HasExited) {
        if (-not $runner.WaitForExit(5000)) { Stop-Process -Id $runner.Id -ErrorAction SilentlyContinue }
    }
    [IO.File]::WriteAllBytes($cfgPath, $originalConfig)
}

# Explicit local fixtures for parser edges and unknown/unhealthy ownership.
# These fixtures are separate from the actual subprocess assertions above.
function Get-PortOwner($port) { return $script:fixtureOwner }
function Test-BridgeProbe($root, $port, $cfg) { return $script:fixtureProbe }
$fixtureRoot = 'D:\中文 工作台'
$fixtureCfg = [pscustomobject]@{ xhs_repo = ($fixtureRoot + '\tools\xiaohongshu-skills') }
$fixtureScript = Get-BridgeScriptPath $fixtureRoot $fixtureCfg
$fixtureExe = 'C:\Python 环境\python.exe'
$fixtureOwner = [pscustomobject]@{ Pid = 12345; Name = 'python.exe'; ExecutablePath = $fixtureExe; CommandLine = '' }
$fixtureProbe = [pscustomobject]@{ reachable = $true; root = $null; extension = $false }
foreach ($line in @(
    ($fixtureExe + ' ' + $fixtureScript + ' --port 9333'),
    ('"' + $fixtureExe + '" "' + $fixtureScript + '" --port 9333')
)) {
    $fixtureOwner.CommandLine = $line
    $result = Test-BridgeOfRoot $fixtureRoot 9333 $fixtureCfg
    Assert-Bridge ($result.SameRoot -eq $true -and $result.ScriptPath -eq $fixtureScript) 'Quoted/unquoted script parser failed.'
}
$fixtureOwner.CommandLine = '"' + $fixtureExe + '" "' + $fixtureScript.Replace('中文 工作台', '中文 工作台-other') + '"'
Assert-Bridge ((Test-BridgeOfRoot $fixtureRoot 9333 $fixtureCfg).SameRoot -eq $false) 'Neighbour installation matched as own.'
$fixtureOwner.CommandLine = '"' + $fixtureExe + '" scripts\bridge_server.py --port 9333'
Assert-Bridge ($null -eq (Test-BridgeOfRoot $fixtureRoot 9333 $fixtureCfg).SameRoot) 'Unknown relative script was treated as own.'
$fixtureProbe.root = $fixtureRoot
Assert-Bridge ((Test-BridgeOfRoot $fixtureRoot 9333 $fixtureCfg).SameRoot -eq $true) 'Relative-script ping root fallback failed.'
$fixtureOwner.CommandLine = '"' + $fixtureExe + '" "' + $fixtureScript + '"'
$fixtureProbe.reachable = $false
$unhealthy = Test-BridgeOfRoot $fixtureRoot 9333 $fixtureCfg
Assert-Bridge ($unhealthy.SameRoot -eq $true -and $unhealthy.Healthy -eq $false) 'Unreachable service was treated as healthy.'
Write-Host 'PASS: separate ownership fixtures (quoted, unquoted, neighbour, unknown, ping fallback, unhealthy).'
