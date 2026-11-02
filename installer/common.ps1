# 公共函数库（安装、检查、启动共用）
# 注意：本文件以 UTF-8 BOM 保存，兼容 Windows PowerShell 5.1 的中文解析。

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    [完成] $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    [注意] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "    [失败] $msg" -ForegroundColor Red }
function Write-Info2($msg) { Write-Host "    $msg" -ForegroundColor Gray }

function Get-PackageRoot {
    # installer\common.ps1 -> 包根目录
    return (Split-Path -Parent (Split-Path -Parent $PSCommandPath))
}

function Resolve-InstallRoot {
    # 不传 -Root 时，按本脚本自身位置推断安装根，不再一律回退到固定目录。
    # 依次尝试：<Root>\installer\*.ps1、<Root>\*.ps1、<Root>\bin\*.ps1、当前目录。
    $candidates = New-Object System.Collections.ArrayList
    if ($PSScriptRoot) {
        [void]$candidates.Add((Split-Path -Parent $PSScriptRoot))
        [void]$candidates.Add($PSScriptRoot)
        [void]$candidates.Add((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
    }
    [void]$candidates.Add((Get-Location).Path)
    foreach ($c in $candidates) {
        if ([string]::IsNullOrWhiteSpace($c)) { continue }
        if (Test-Path -LiteralPath (Join-Path $c 'config\paths.json')) {
            return [string]([System.IO.Path]::GetFullPath($c)).TrimEnd('\')
        }
    }
    return $null
}

function Get-DefaultRoot {
    if (Test-Path -LiteralPath 'D:\') {
        return 'D:\XHSWork'
    }
    return $null
}

function Read-Config($root) {
    # 明确按 UTF-8 解码：Get-Content 在部分环境会按 ANSI 读，中文目录会被读坏
    $p = Join-Path $root 'config\paths.json'
    if (-not (Test-Path -LiteralPath $p)) { return $null }
    $text = [System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8)
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    return $text | ConvertFrom-Json
}

function Save-ConfigUtf8($path, $obj) {
    $dir = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $json = $obj | ConvertTo-Json -Depth 6
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $json, $utf8)
}

function Copy-TreeSafely($src, $dst) {
    # 复制目录；同名文件内容不同则先备份再覆盖；不删除目标目录里的其他文件
    if (-not (Test-Path -LiteralPath $src)) { return }
    if (-not (Test-Path -LiteralPath $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Get-ChildItem -LiteralPath $src -Force | ForEach-Object {
        $target = Join-Path $dst $_.Name
        if ($_.PSIsContainer) {
            Copy-TreeSafely $_.FullName $target
        }
        else {
            if (Test-Path -LiteralPath $target) {
                $a = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                $b = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
                if ($a -eq $b) { return }
                $bak = "$target.bak-$stamp"
                Copy-Item -LiteralPath $target -Destination $bak -Force
                Write-Warn2 "已备份原有文件：$target -> $(Split-Path -Leaf $bak)"
            }
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

function Copy-FileSafely($src, $dst) {
    # 单文件复制：内容不同才覆盖，覆盖前先备份
    if (-not (Test-Path -LiteralPath $src)) { return }
    $dir = Split-Path -Parent $dst
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    if (Test-Path -LiteralPath $dst) {
        $a = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
        $b = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
        if ($a -eq $b) { return }
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        Copy-Item -LiteralPath $dst -Destination "$dst.bak-$stamp" -Force
        Write-Warn2 "已备份原有文件：$dst -> $(Split-Path -Leaf "$dst.bak-$stamp")"
    }
    Copy-Item -LiteralPath $src -Destination $dst -Force
}

function Find-Uv($root) {
    $local = Join-Path $root 'bin\uv.exe'
    if (Test-Path -LiteralPath $local) { return $local }
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Install-Uv($root) {
    $bin = Join-Path $root 'bin'
    New-Item -ItemType Directory -Path $bin -Force | Out-Null
    $tmp = Join-Path $root 'tmp'
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    $zip = Join-Path $tmp 'uv-windows.zip'
    $url = 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'
    Write-Info2 '正在下载 uv（约 20MB，来源 GitHub Releases）...'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    try {
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 600
        Expand-Archive -LiteralPath $zip -DestinationPath $bin -Force
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
    }
    catch {
        throw ("下载 uv 失败：$($_.Exception.Message)　可手动下载 uv-x86_64-pc-windows-msvc.zip，解压出 uv.exe 放到 $bin 后重新运行安装。官方说明：https://docs.astral.sh/uv/getting-started/installation/")
    }
    $exe = Join-Path $bin 'uv.exe'
    if (-not (Test-Path -LiteralPath $exe)) { throw "uv 解压后未找到 uv.exe（$bin）" }
    return $exe
}

function Set-ProjectEnv($root) {
    $cfg = Read-Config $root
    $values = @{
        UV_CACHE_DIR = 'cache\uv'; UV_PYTHON_INSTALL_DIR = 'runtime\python'
        UV_PYTHON_BIN_DIR = 'runtime\bin'; TEMP = 'tmp'; TMP = 'tmp'
        PLAYWRIGHT_BROWSERS_PATH = 'browsers'
    }
    $fields = @{ UV_CACHE_DIR = 'uv_cache_dir'; UV_PYTHON_INSTALL_DIR = 'python_install_dir'; TEMP = 'tmp_dir'; TMP = 'tmp_dir'; PLAYWRIGHT_BROWSERS_PATH = 'playwright_browsers' }
    foreach ($key in $values.Keys) {
        $value = Join-Path $root $values[$key]
        if ($cfg -and $fields.ContainsKey($key) -and $cfg.($fields[$key])) { $value = [string]$cfg.($fields[$key]) }
        [Environment]::SetEnvironmentVariable($key, $value, 'Process')
        if (-not (Test-Path -LiteralPath $value)) { New-Item -ItemType Directory -Path $value -Force | Out-Null }
    }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
}

function Get-PortOwner($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { return $null }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
    return [pscustomobject]@{
        Pid            = $conn.OwningProcess
        Name           = if ($proc) { $proc.Name } else { 'unknown' }
        ExecutablePath = if ($proc) { $proc.ExecutablePath } else { '' }
        CommandLine    = if ($proc) { $proc.CommandLine } else { '' }
    }
}

function Get-BridgeScriptPath($root, $cfg) {
    # 以配置里的服务脚本完整路径为准，而不是把路径字符串截一段去拼层级
    if ($cfg -and $cfg.xhs_repo) {
        return (Join-Path ([string]$cfg.xhs_repo) 'scripts\bridge_server.py')
    }
    return (Join-Path $root 'tools\xiaohongshu-skills\scripts\bridge_server.py')
}

function Test-BridgeProbe($root, $port, $cfg, $observedScript = '') {
    # 只读探测：连上 ws 问服务自己是谁。不启动、不关闭、不改动任何进程。
    if (-not $cfg) { $cfg = Read-Config $root }
    if (-not $cfg) { return $null }
    $py = $cfg.xhs_python
    if (-not $py -or -not (Test-Path -LiteralPath $py)) { return $null }
    $probe = Join-Path $PSScriptRoot 'bridge_probe.py'
    if (-not (Test-Path -LiteralPath $probe)) { return $null }
    # Argument binding preserves spaces/Chinese without cmd.exe quote stripping.
    $probeArgs = @($probe, '--port', $port, '--root', $root, '--script', (Get-BridgeScriptPath $root $cfg))
    if ($observedScript) { $probeArgs += @('--observed-script', $observedScript) }
    $raw = & $py @probeArgs 2>$null
    if (-not $raw) { return $null }
    try { return (($raw | Select-Object -Last 1) | ConvertFrom-Json) } catch { return $null }
}

function Test-BridgeOfRoot($root, $port, $cfg) {
    # State: stopped / running / occupied
    # SameRoot: $true 本安装实例 / $false 其他安装目录 / $null 归属不明
    # Extension: $true / $false / $null（复用前据此判断能否直接出稿）
    if (-not $port) { $port = 9333 }
    $owner = Get-PortOwner $port
    if (-not $owner) {
        return [pscustomobject]@{ State = 'stopped'; Owner = $null; SameRoot = $null; ScriptPath = ''; Extension = $null; Healthy = $false; Via = '' }
    }

    $cmdline = ''
    if ($owner.CommandLine) { $cmdline = [string]$owner.CommandLine }
    if ($cmdline -notmatch 'bridge_server\.py') {
        return [pscustomobject]@{ State = 'occupied'; Owner = $owner; SameRoot = $false; ScriptPath = ''; Extension = $null; Healthy = $false; Via = 'cmdline' }
    }

    $expected = Get-BridgeScriptPath $root $cfg
    $scriptPath = ''
    # Remove the executable first so an unquoted python.exe cannot be
    # greedily captured as part of the script path. Keep spaces/Chinese in scripts.
    $arguments = $cmdline
    $exe = [string]$owner.ExecutablePath
    if ($exe -and $arguments.StartsWith(('"' + $exe + '"'), [StringComparison]::OrdinalIgnoreCase)) {
        $arguments = $arguments.Substring($exe.Length + 2).TrimStart()
    } elseif ($exe -and $arguments.StartsWith(($exe + ' '), [StringComparison]::OrdinalIgnoreCase)) {
        $arguments = $arguments.Substring($exe.Length).TrimStart()
    } else {
        $arguments = [regex]::Replace($arguments, '^\s*(?:"[^"]*"|\S+)\s+', '')
    }
    $m = [regex]::Match($arguments, '^\s*(?:"((?:[A-Za-z]:\\|\\\\)[^"]*?bridge_server\.py)"|((?:[A-Za-z]:\\|\\\\).*?bridge_server\.py)(?=\s|$))', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($m.Success) {
        if ($m.Groups[1].Success) { $scriptPath = $m.Groups[1].Value }
        else { $scriptPath = $m.Groups[2].Value }
    }

    $sameRoot = $null
    $via = 'cmdline'
    if ($scriptPath) {
        # 以配置里记录的服务脚本完整路径为准：能对上就是本安装实例
        if ($scriptPath.TrimEnd('\').ToLower() -eq ([string]$expected).TrimEnd('\').ToLower()) { $sameRoot = $true }
        else { $sameRoot = $false }
    }

    # 只读探测服务：补扩展连接状态；命令行判不出归属时才用服务自报的安装根
    $probe = Test-BridgeProbe $root $port $cfg $scriptPath
    # Canonicalize the parsed command path locally; a foreign root claim cannot
    # override an absolute script belonging to another installation.
    if ($scriptPath -and $probe -and $probe.observed_script_path -and $probe.expected_script_path) {
        $sameRoot = ([string]$probe.observed_script_path).TrimEnd('\').Equals(
            ([string]$probe.expected_script_path).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)
    }
    $healthy = [bool]($probe -and $probe.reachable)
    if ($healthy -and $null -ne $probe.pid -and $null -ne $owner.Pid -and ([string]$probe.pid -ne [string]$owner.Pid)) {
        $healthy = $false
    }
    $ext = $null
    if ($healthy) {
        if ($null -ne $probe.extension) { $ext = [bool]$probe.extension }
        if (-not $scriptPath) { $via = 'ping' }
        if ($null -eq $sameRoot) {
            if ($probe.root) {
                $pr = ([string]$probe.root).TrimEnd('\').ToLower()
                $expectedRoot = $root
                if ($probe.expected_root) { $expectedRoot = $probe.expected_root }
                $er = ([string]$expectedRoot).TrimEnd('\').ToLower()
                if ($pr -eq $er) { $sameRoot = $true } else { $sameRoot = $false }
                $scriptPath = [string]$probe.root
                $via = 'ping'
            }
        }
    }
    return [pscustomobject]@{ State = 'running'; Owner = $owner; SameRoot = $sameRoot; ScriptPath = $scriptPath; Extension = $ext; Healthy = $healthy; Via = $via }
}

function Test-PyImport($py, $code) {
    # 用 cmd 包装，避免原生命令 stderr 在 PowerShell 5.1 里被当成异常抛出
    $null = cmd /c "`"$py`" -c `"$code`" >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

function Invoke-Logged($exe, $argLine) {
    # 运行外部命令：合并 stderr、逐行回显（进 transcript 日志），返回退出码
    $out = cmd /c "`"$exe`" $argLine 2>&1"
    $code = $LASTEXITCODE
    foreach ($line in ($out -split "`r?`n")) {
        if ($line.Trim()) { Write-Info2 $line.TrimEnd() }
    }
    return $code
}


