# XHS 工作台 · 启动助手
# 检查并在独立窗口启动本项目 Bridge（localhost:9333）。
# 规则：本安装目录的 Bridge 直接复用；被其他程序占用时只说明情况，不结束别人进程、不换端口。

param([string]$Root = '')

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'common.ps1')

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '  XHS 工作台 启动助手' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan

if (-not $Root) {
    # 不再回退到固定目录：按本脚本所在位置找真正的安装根（含 config\paths.json 的那一层）
    $Root = Resolve-InstallRoot
    if (-not $Root) {
        Write-Err '没有找到安装目录：本脚本必须放在安装目录内运行（安装目录下的 installer\ 或根目录）。'
        Write-Host '    还没安装：双击安装包里的「安装.cmd」。' -ForegroundColor Yellow
        Write-Host '    已经安装：请直接双击安装目录里的「启动助手.cmd」/「检查环境.cmd」，不要把单个脚本复制到别处运行。' -ForegroundColor Yellow
        exit 1
    }
}
$Root = $Root.TrimEnd('\')
$cfg = Read-Config $Root
Set-ProjectEnv $Root
if (-not $cfg) {
    Write-Err "未找到配置：$(Join-Path $Root 'config\paths.json')"
    Write-Host '    这台电脑还没有安装，请先运行「安装.cmd」。' -ForegroundColor Yellow
    exit 1
}

$port = 9333
if ($cfg.bridge_port) { $port = [int]$cfg.bridge_port }
$xhsPy = $cfg.xhs_python
$server = Join-Path $cfg.xhs_repo 'scripts\bridge_server.py'

if (-not (Test-Path -LiteralPath $xhsPy)) {
    Write-Err "缺少程序环境：$xhsPy"
    Write-Host '    请先运行「安装.cmd」补齐依赖。' -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path -LiteralPath $server)) {
    Write-Err "缺少 Bridge 服务文件：$server"
    exit 1
}

# ---------- 端口检查 ----------
Write-Step "检查端口 $port"
$bridge = Test-BridgeOfRoot $Root $port $cfg
if ($bridge.State -eq 'running' -and $bridge.SameRoot -eq $true) {
    # 归属已确认：再看连接状态，不能直接就说出稿
    Write-Ok "Bridge 已在运行（PID $($bridge.Owner.Pid)），属于本安装目录，直接复用，不再重复启动"
    Write-Step '当前连接状态'
    $adapter = Join-Path $Root 'app\adapters\xhs_daily.py'
    $raw = cmd /c "`"$xhsPy`" `"$adapter`" env-probe 2>nul"
    $probe = $null
    try { $probe = (($raw | Select-Object -Last 1) | ConvertFrom-Json) } catch { $probe = $null }
    if ($probe -and $probe.extension) {
        Write-Ok '浏览器扩展已连接'
        if ($probe.login -eq $true) { Write-Ok '小红书已登录' }
        elseif ($probe.login -eq $false) {
            Write-Warn2 '尚未登录小红书'
            Write-Host '    请在这个 Chrome 中手动登录 https://www.xiaohongshu.com' -ForegroundColor Yellow
        }
        else { Write-Warn2 '登录状态暂时读不到，可稍后运行「检查环境.cmd」' }
        Write-Host ''
        Write-Host '现在可以回到扣子对话，发送「开始今天的工作」。' -ForegroundColor Cyan
    }
    else {
        Write-Warn2 'Bridge 在运行，但浏览器扩展尚未连接（此时还不能出稿）'
        Write-Host "    在 Chrome 加载扩展：$(Join-Path $cfg.xhs_repo 'extension')" -ForegroundColor Yellow
        Write-Host '    chrome://extensions -> 开发者模式 -> 加载已解压的扩展程序 -> 选择上面的目录' -ForegroundColor Yellow
        Write-Host '    连上之后再运行「检查环境.cmd」确认。' -ForegroundColor Yellow
    }
    Write-Host ''
    exit 0
}
if ($bridge.State -eq 'running' -and $bridge.SameRoot -eq $false) {
    Write-Warn2 "端口 $port 上的 Bridge 属于另一个安装目录：$($bridge.ScriptPath)"
    Write-Host '    为了不弄乱两套环境：本次不启动、不结束那个进程、也不换端口。' -ForegroundColor Yellow
    Write-Host '    处理：关闭那个安装目录的「启动助手」窗口（或重启电脑），再双击本目录的「启动助手.cmd」。' -ForegroundColor Yellow
    exit 3
}
if ($bridge.State -eq 'running') {
    Write-Warn2 "端口 $port 上有 Bridge 在运行（PID $($bridge.Owner.Pid)），但无法确认它属于本安装目录"
    Write-Host "    启动命令行：$($bridge.Owner.CommandLine)" -ForegroundColor DarkGray
    Write-Host '    可能是旧版本（不回报归属）或相对路径启动的实例。为安全起见：' -ForegroundColor Yellow
    Write-Host '    本次不启动、不结束已有进程、不换端口。' -ForegroundColor Yellow
    Write-Host '    处理：确认那个窗口是不是你从这个目录启动的；不确定就先关掉它，再双击本目录的「启动助手.cmd」。' -ForegroundColor Yellow
    exit 3
}
if ($bridge.State -eq 'occupied') {
    Write-Warn2 "端口 $port 已被其他程序占用：$($bridge.Owner.Name)（PID $($bridge.Owner.Pid)）"
    Write-Host '    这不是本工具的 Bridge。为安全起见：不结束别人的进程，也不自动换端口。' -ForegroundColor Yellow
    Write-Host '    处理办法：关闭占用该端口的程序，或重启电脑后再双击「启动助手.cmd」。' -ForegroundColor Yellow
    Write-Host '    提示：如果你之前在别的目录装过同一套工具，请只保留一个在运行。' -ForegroundColor DarkGray
    exit 2
}
Write-Ok "端口 $port 空闲"

# ---------- 启动 ----------
Write-Step '启动 Bridge（独立窗口）'
$runner = Join-Path $PSScriptRoot 'run_bridge.ps1'
$argLine = '-NoExit -NoLogo -ExecutionPolicy Bypass -File "' + $runner + '" -Root "' + $Root + '"'
try {
    Start-Process -FilePath 'powershell.exe' -ArgumentList $argLine -WorkingDirectory $cfg.xhs_repo | Out-Null
}
catch {
    Write-Err "启动失败：$($_.Exception.Message)"
    exit 1
}

# ---------- 确认服务真的起来了（不只看启动命令） ----------
Write-Step '确认服务持续运行'
$up = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    if (Get-PortOwner $port) { $up = $true; break }
}
if (-not $up) {
    Write-Err "等待 30 秒后，端口 $port 仍未监听"
    Write-Host '    可能原因：Python 依赖缺失、端口被拦截、杀毒软件阻止。' -ForegroundColor Yellow
    Write-Host "    请查看最新日志：$(Join-Path $Root 'logs')" -ForegroundColor Yellow
    exit 1
}

Start-Sleep -Seconds 3
$still = Get-PortOwner $port
if (-not $still) {
    Write-Err 'Bridge 启动后又退出了（服务未能保持运行）'
    Write-Host "    请查看日志：$(Join-Path $Root 'logs')" -ForegroundColor Yellow
    exit 1
}
Write-Ok "Bridge 正在运行（PID $($still.Pid)，端口 $port）"

# ---------- 当前连接状态 ----------
Write-Step '当前连接状态'
$adapter = Join-Path $Root 'app\adapters\xhs_daily.py'
$raw = cmd /c "`"$xhsPy`" `"$adapter`" env-probe 2>nul"
$probe = $null
try { $probe = (($raw | Select-Object -Last 1) | ConvertFrom-Json) } catch { $probe = $null }

if ($probe) {
    if ($probe.extension) { Write-Ok '浏览器扩展已连接' }
    else {
        Write-Warn2 '浏览器扩展尚未连接'
        Write-Host "    在 Chrome 加载扩展：$(Join-Path $cfg.xhs_repo 'extension')" -ForegroundColor Yellow
        Write-Host '    chrome://extensions -> 开发者模式 -> 加载已解压的扩展程序 -> 选择上面的目录' -ForegroundColor Yellow
    }
    if ($probe.login -eq $true) { Write-Ok '小红书已登录' }
    elseif ($probe.login -eq $false) {
        Write-Warn2 '尚未登录小红书'
        Write-Host '    请在这个 Chrome 中手动登录 https://www.xiaohongshu.com' -ForegroundColor Yellow
    }
    else { Write-Warn2 '登录状态暂时读不到（扩展连上后可再运行「检查环境.cmd」）' }
}
else { Write-Warn2 '暂时读不到扩展状态，可稍后运行「检查环境.cmd」' }

Write-Host ''
Write-Host '-----------------------------------------'
Write-Host '  Bridge 已在独立窗口运行，请保持该窗口开启。' -ForegroundColor Green
Write-Host '  下一步：在扣子对话里发送「开始今天的工作」。'
Write-Host '  如需复查环境：双击「检查环境.cmd」。'
Write-Host '-----------------------------------------'
Write-Host ''
exit 0

