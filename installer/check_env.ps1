# XHS 工作台 · 环境检查
# 分别显示：1 安装文件 / 2 运行依赖 / 3 Bridge 服务 / 4 浏览器扩展 / 5 小红书登录
# 用法：检查环境.cmd   或   powershell -File installer\check_env.ps1 -Root "D:\XHSWork"

param([string]$Root = '')

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'common.ps1')

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '  XHS 工作台 环境检查' -ForegroundColor Cyan
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
    Write-Err "未找到配置文件：$(Join-Path $Root 'config\paths.json')"
    Write-Host '    这台电脑还没有安装，请先运行「安装.cmd」。' -ForegroundColor Yellow
    exit 1
}

$state = [ordered]@{ files = $false; deps = $false; bridge = $false; extension = $false; login = $null }

# ---------- 1. 文件 ----------
Write-Step '1. 安装文件'
Write-Info2 "安装目录：$Root"
$xhsRepo = $cfg.xhs_repo
$renderRepo = $cfg.render_repo
$skillDir = Join-Path $cfg.skills_dir 'xhs-daily'
$adapter = Join-Path $Root 'app\adapters\xhs_daily.py'
$need = @(
    @{ P = $xhsRepo; N = '小红书操作项目' },
    @{ P = (Join-Path $xhsRepo 'scripts\cli.py'); N = '小红书 CLI' },
    @{ P = (Join-Path $xhsRepo 'uv.lock'); N = '依赖锁文件 uv.lock' },
    @{ P = (Join-Path $xhsRepo 'extension\manifest.json'); N = 'Chrome 扩展 manifest' },
    @{ P = $renderRepo; N = '图片渲染项目' },
    @{ P = (Join-Path $renderRepo 'scripts\render_xhs.py'); N = '渲染脚本' },
    @{ P = (Join-Path $renderRepo 'assets\cover_themes'); N = '封面主题样式（本地补丁）' },
    @{ P = $skillDir; N = '技能目录 xhs-daily' },
    @{ P = (Join-Path $skillDir 'SKILL.md'); N = '技能定义 SKILL.md' },
    @{ P = $adapter; N = '填稿适配脚本' }
)
$missFile = @()
foreach ($n in $need) {
    if (Test-Path -LiteralPath $n.P) { Write-Ok $n.N }
    else { Write-Err "$($n.N) 缺失：$($n.P)"; $missFile += $n.N }
}
$state.files = ($missFile.Count -eq 0)

# ---------- 2. 依赖 ----------
Write-Step '2. 运行依赖'
$xhsPy = $cfg.xhs_python
$renderPy = $cfg.render_python
$depsOk = $true
if (Test-Path -LiteralPath $xhsPy) {
    if (Test-PyImport $xhsPy 'import websockets, requests, python_socks') { Write-Ok '小红书项目依赖齐全' }
    else { Write-Err '小红书项目依赖不完整，请重新运行「安装.cmd」'; $depsOk = $false }
}
else { Write-Err "缺少小红书项目虚拟环境：$xhsPy"; $depsOk = $false }

if (Test-Path -LiteralPath $renderPy) {
    if (Test-PyImport $renderPy 'import playwright, markdown, yaml') { Write-Ok '渲染项目依赖齐全' }
    else { Write-Err '渲染项目依赖不完整，请重新运行「安装.cmd」'; $depsOk = $false }
}
else { Write-Err "缺少渲染项目虚拟环境：$renderPy"; $depsOk = $false }

$browsersDir = $cfg.playwright_browsers
if ($browsersDir -and (Test-Path -LiteralPath $browsersDir)) {
    $chromium = Get-ChildItem -LiteralPath $browsersDir -Directory -Filter 'chromium-*' -ErrorAction SilentlyContinue
    if ($chromium) { Write-Ok "渲染浏览器已就绪（$(@($chromium).Count) 个版本）" }
    else { Write-Err '渲染浏览器未安装（Chromium 缺失）'; $depsOk = $false }
}
else { Write-Err '渲染浏览器目录不存在'; $depsOk = $false }
$state.deps = $depsOk

# ---------- 3. Bridge ----------
$port = 9333
if ($cfg.bridge_port) { $port = [int]$cfg.bridge_port }
Write-Step "3. Bridge 服务（localhost:$port）"
$bridge = Test-BridgeOfRoot $Root $port $cfg
$bridgeOk = $false
if ($bridge.State -eq 'stopped') {
    Write-Warn2 "端口 $port 没有服务在监听 —— Bridge 未启动"
    Write-Host '    处理：双击「启动助手.cmd」，运行期间保留那个窗口。' -ForegroundColor Yellow
}
elseif ($bridge.State -eq 'occupied') {
    Write-Warn2 "端口 $port 被其他程序占用（PID $($bridge.Owner.Pid)：$($bridge.Owner.Name)）"
    Write-Host '    这不是本工具的 Bridge。本工具不会结束它，也不会自动换端口。' -ForegroundColor Yellow
    Write-Host '    处理：关闭占用该端口的程序，或重启电脑后再次双击「启动助手.cmd」。' -ForegroundColor Yellow
}
else {
    if ($bridge.SameRoot -eq $true -and $bridge.Healthy -eq $true) {
        Write-Ok "Bridge 正在运行（PID $($bridge.Owner.Pid)），属于本安装目录"
        $bridgeOk = $true
    }
    elseif ($bridge.SameRoot -eq $true) {
        Write-Warn2 "本安装目录的 Bridge 占用端口（PID $($bridge.Owner.Pid)），但服务状态探测失败"
        Write-Host '    请查看 Bridge 窗口及日志；端口开放不代表服务已经就绪。' -ForegroundColor Yellow
        $bridgeOk = $false
    }
    elseif ($bridge.SameRoot -eq $false) {
        Write-Warn2 "端口 $port 上的 Bridge 属于另一个安装目录：$($bridge.ScriptPath)"
        Write-Host '    本工具不结束它、不换端口；但这不是本安装的 Bridge，按未就绪处理。' -ForegroundColor Yellow
        Write-Host '    处理：关闭那个目录的 Bridge 窗口后，双击本目录的「启动助手.cmd」。' -ForegroundColor Yellow
        $bridgeOk = $false
    }
    else {
        Write-Warn2 "端口 $port 上有 Bridge 在运行（PID $($bridge.Owner.Pid)），但无法确认它属于本安装目录"
        Write-Host "    启动命令行：$($bridge.Owner.CommandLine)" -ForegroundColor DarkGray
        Write-Host '    处理：确认它是不是你从这个目录启动的；不确定就先关掉那个窗口，再双击本目录的「启动助手.cmd」。' -ForegroundColor Yellow
        $bridgeOk = $false
    }
}
$state.bridge = $bridgeOk

# ---------- 4 / 5. 扩展与登录 ----------
Write-Step '4. 浏览器扩展'
Write-Step '5. 小红书登录'
$extOk = $false
$loginState = $null
if (-not $bridgeOk) {
    Write-Warn2 'Bridge 未就绪，暂时无法检查扩展与登录'
    Write-Host '    这不代表扩展有问题，请先启动 Bridge 再看这两项。' -ForegroundColor DarkGray
}
elseif (-not (Test-Path -LiteralPath $xhsPy)) {
    Write-Err '缺少小红书项目 Python，无法检查'
}
else {
    $raw = cmd /c "`"$xhsPy`" `"$adapter`" env-probe 2>nul"
    $probe = $null
    try { $probe = (($raw | Select-Object -Last 1) | ConvertFrom-Json) } catch { $probe = $null }
    if (-not $probe) {
        Write-Err '无法获取 Bridge 状态（探测脚本返回异常）'
        Write-Host '    可重新运行「安装.cmd」补齐 app\adapters 后重试。' -ForegroundColor Yellow
    }
    else {
        if ($probe.extension) {
            Write-Ok 'XHS Bridge 扩展已连接'
            $extOk = $true
        }
        else {
            Write-Err '扩展未连接'
            Write-Host '    处理：Chrome 打开 chrome://extensions -> 开发者模式 -> 加载已解压的扩展程序' -ForegroundColor Yellow
            Write-Host "          选择：$(Join-Path $xhsRepo 'extension')" -ForegroundColor Yellow
            Write-Host '          然后刷新一次小红书页面，再运行本检查。' -ForegroundColor Yellow
        }
        if ($probe.login -eq $true) {
            Write-Ok '小红书已登录'
            $loginState = $true
        }
        elseif ($probe.login -eq $false) {
            Write-Warn2 '尚未登录小红书'
            Write-Host '    处理：在这个 Chrome 里打开 https://www.xiaohongshu.com 手动登录（含验证码）。' -ForegroundColor Yellow
            Write-Host '          本工具不代登录、不导出 Cookie、不生成二维码。' -ForegroundColor DarkGray
            $loginState = $false
        }
        else {
            Write-Warn2 '登录状态暂时读不到'
            if ($probe.error) { Write-Host "    原因：$($probe.error)" -ForegroundColor DarkGray }
            $loginState = $null
        }
    }
}
$state.extension = $extOk
$state.login = $loginState

# ---------- 结论 ----------
Write-Host ''
Write-Host '-----------------------------------------' -ForegroundColor DarkGray
if (-not $state.files) {
    Write-Host '  状态：安装不完整' -ForegroundColor Red
    Write-Host '  处理：重新运行「安装.cmd」，可续装，不会覆盖你的资料。'
}
elseif (-not $state.deps) {
    Write-Host '  状态：程序已装好，依赖未装全' -ForegroundColor Red
    Write-Host '  处理：重新运行「安装.cmd」补齐依赖。'
}
elseif (-not $state.bridge) {
    Write-Host '  状态：已安装完成，Bridge 未启动' -ForegroundColor Yellow
    Write-Host '  处理：双击「启动助手.cmd」并保留窗口，然后重新运行本检查。'
}
elseif (-not $state.extension) {
    Write-Host '  状态：已安装并启动，等待加载浏览器扩展' -ForegroundColor Yellow
    Write-Host '  处理：按上面第 4 项提示在 Chrome 加载扩展。'
}
elseif ($state.login -ne $true) {
    Write-Host '  状态：扩展已连接，等待登录小红书' -ForegroundColor Yellow
    Write-Host '  处理：在 Chrome 中手动登录，然后重新运行本检查。'
}
else {
    Write-Host '  状态：全部就绪，可以开始出稿' -ForegroundColor Green
    Write-Host '  下一步：在扣子对话里发送「开始今天的工作」。'
}
Write-Host '-----------------------------------------' -ForegroundColor DarkGray
Write-Host ''
Write-Host '提示：技能文件已复制到本机，但还需要在扣子桌面端完成启用：'
Write-Host '      开启本地文件访问 -> 添加扫描目录 -> 给目标 Agent 添加本机技能。'
Write-Host "      技能目录：$(Join-Path $cfg.skills_dir 'xhs-daily')"
Write-Host ''

if ($state.files -and $state.deps -and $state.bridge -and $state.extension -and ($state.login -eq $true)) { exit 0 }
exit 2


