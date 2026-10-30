# XHS 工作台 · Windows 联网安装器
# 用法：
#   安装.cmd                      默认安装到 D:\XHSWork（无 D 盘时提示选择目录）
#   安装.cmd -Root "E:\我的 目录"  指定安装根目录（支持中文和空格）
#   安装.cmd -Force               强制重装依赖（仍不删除已有资料）

param(
    [string]$Root = '',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
. (Join-Path $PSScriptRoot 'lib.ps1')

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '  XHS 工作台 安装程序 (Windows)' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '  首次安装需要联网：下载 uv、Python、依赖和渲染浏览器。'

# ---------- 1. 确定安装根目录 ----------
Write-Step '第 1 步 / 确认安装目录'

if (-not $Root) {
    $default = Get-DefaultRoot
    if ($default) {
        $Root = $default
        Write-Info2 "默认安装目录：$Root"
    }
    else {
        Write-Warn2 '未检测到 D 盘，请手动指定一个安装目录（不会自动装到 C 盘）。'
        Write-Info2 '建议使用非系统盘，例如 E:\XHSWork'
        $userInput = Read-Host '    请输入安装目录（直接回车退出）'
        if ([string]::IsNullOrWhiteSpace($userInput)) {
            Write-Err '未指定安装目录，已退出。'
            exit 1
        }
        $Root = $userInput.Trim('"').Trim()
    }
}

$invalid = [System.IO.Path]::GetInvalidPathChars()
foreach ($ch in $invalid) {
    if ($Root.Contains([string]$ch)) { Write-Err "安装目录包含非法字符：$ch"; exit 1 }
}
$Root = $Root.TrimEnd('\')
try {
    if (-not (Test-Path -LiteralPath $Root)) { New-Item -ItemType Directory -Path $Root -Force | Out-Null }
}
catch {
    Write-Err "无法创建安装目录：$Root"
    Write-Err $_.Exception.Message
    exit 1
}
Write-Ok "安装根目录：$Root"

$pkg = Get-PackageRoot
Write-Info2 "安装包目录：$pkg"

$logDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir ("install-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
Start-Transcript -Path $logFile -Append -Force | Out-Null
Write-Info2 "安装日志：$logFile"

function Fail($msg, $hint) {
    Write-Err $msg
    if ($hint) { Write-Host "    处理建议：$hint" -ForegroundColor Yellow }
    Write-Host "    安装日志：$logFile" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

try {

    # ---------- 2. 目录骨架 ----------
    Write-Step '第 2 步 / 建立目录结构'
    $dirs = @(
        'config', 'logs', 'tmp', 'cache', 'cache\uv', 'runtime', 'runtime\python',
        'runtime\bin', 'browsers', 'tools', 'skills', 'app', 'docs', 'workdir', 'bin', 'sample'
    )
    foreach ($d in $dirs) { New-Item -ItemType Directory -Path (Join-Path $Root $d) -Force | Out-Null }
    Write-Ok '目录结构就绪'

    # ---------- 3. 复制程序文件 ----------
    Write-Step '第 3 步 / 复制程序与技能文件'
    $map = @(
        @{ Src = 'tools\xiaohongshu-skills'; Dst = 'tools\xiaohongshu-skills' },
        @{ Src = 'tools\Auto-Redbook-Skills'; Dst = 'tools\Auto-Redbook-Skills' },
        @{ Src = 'tools\gpt-writer'; Dst = 'tools\gpt-writer' },
        @{ Src = 'app\adapters'; Dst = 'app\adapters' },
        @{ Src = 'app\constraints'; Dst = 'app\constraints' },
        @{ Src = 'installer'; Dst = 'installer' },
        @{ Src = 'config_template'; Dst = 'config_template' },
        @{ Src = 'docs'; Dst = 'docs' },
        @{ Src = 'docs\samples'; Dst = 'sample\cover-themes' },
        @{ Src = 'knowledge'; Dst = 'knowledge' },
        @{ Src = 'skills\xhs-daily'; Dst = 'skills\xhs-daily' }
    )
    foreach ($m in $map) {
        $s = Join-Path $pkg $m.Src
        if (-not (Test-Path -LiteralPath $s)) { Fail "安装包缺少目录：$($m.Src)" '请重新解压完整的安装包 ZIP' }
        $t = Join-Path $Root $m.Dst
        Copy-TreeSafely $s $t
        Write-Ok "$($m.Dst)"
    }

    # 三个入口和说明：装完之后只认安装目录里的入口，不再依赖原解压目录
    foreach ($f in @('安装.cmd', '启动助手.cmd', '检查环境.cmd', '更新工作台.cmd', '先看这里.md', 'VERSION')) {
        $src = Join-Path $pkg $f
        if (-not (Test-Path -LiteralPath $src)) { Fail "安装包缺少文件：$f" '请重新解压完整的安装包 ZIP' }
        Copy-FileSafely $src (Join-Path $Root $f)
    }
    Write-Ok '启动 / 检查 / 重装入口已放进安装目录'

    # 技能：程序文件随版本更新
    Copy-FileSafely (Join-Path $pkg 'skills\xhs-daily\SKILL.md') (Join-Path $Root 'skills\xhs-daily\SKILL.md')
    Write-Ok 'skills\xhs-daily\SKILL.md'

    # 用户资料：由 seed 目录初始化，只在缺失时写入；已存在的一律原样保留
    $seeded = Invoke-SeedApply $pkg $Root
    if ($seeded.Count -gt 0) {
        foreach ($rel in $seeded) { Write-Ok "初始化个人资料：$rel" }
    }
    else { Write-Info2 '个人资料已存在，全部保留' }

    # ---------- 4. 本机路径配置 ----------
    Write-Step '第 4 步 / 生成本机路径配置'
    $cfgPath = Join-Path $Root 'config\paths.json'
    $oldCfg = $null
    if (Test-Path -LiteralPath $cfgPath) {
        try { $oldCfg = Read-Config $Root } catch { $oldCfg = $null }
        Copy-Item -LiteralPath $cfgPath -Destination ("$cfgPath.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')) -Force
        Write-Info2 '原配置已备份为 paths.json.bak-*'
    }
    $cfg = [ordered]@{
        version             = (Get-PkgVersion $pkg)
        root                = $Root
        project_root        = $Root
        xhs_repo            = (Join-Path $Root 'tools\xiaohongshu-skills')
        repo_dir            = (Join-Path $Root 'tools\xiaohongshu-skills')
        render_repo         = (Join-Path $Root 'tools\Auto-Redbook-Skills')
        skills_dir          = (Join-Path $Root 'skills')
        workdir             = (Join-Path $Root 'workdir')
        knowledge_dir       = (Join-Path $Root 'knowledge')
        logs_dir            = (Join-Path $Root 'logs')
        tmp_dir             = (Join-Path $Root 'tmp')
        xhs_python          = (Join-Path $Root 'tools\xiaohongshu-skills\.venv\Scripts\python.exe')
        render_python       = (Join-Path $Root 'tools\Auto-Redbook-Skills\.venv\Scripts\python.exe')
        uv_cache_dir        = (Join-Path $Root 'cache\uv')
        python_install_dir  = (Join-Path $Root 'runtime\python')
        playwright_browsers = (Join-Path $Root 'browsers')
        bridge_url          = 'ws://localhost:9333'
        bridge_port         = 9333
        installed_at        = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    }
    if ($oldCfg) {
        # 自定义字段（以及用户改过的 bridge_port / bridge_url）不能无提示丢弃
        $known = @($cfg.Keys)
        $kept = New-Object System.Collections.ArrayList
        foreach ($prop in $oldCfg.PSObject.Properties) {
            if ($known -notcontains $prop.Name) {
                $cfg[$prop.Name] = $prop.Value
                [void]$kept.Add($prop.Name)
            }
        }
        foreach ($k in @('bridge_port', 'bridge_url')) {
            if ($oldCfg.PSObject.Properties.Name -contains $k) { $cfg[$k] = $oldCfg.$k }
        }
        if ($kept.Count -gt 0) { Write-Ok ("已保留原有自定义配置：" + ($kept -join ', ')) }
    }
    Save-ConfigUtf8 $cfgPath $cfg
    Write-Ok "配置文件：$cfgPath"
    $tpl = Join-Path $pkg 'config_template\paths.template.json'
    if (Test-Path -LiteralPath $tpl) {
        Copy-Item -LiteralPath $tpl -Destination (Join-Path $Root 'config\paths.template.json') -Force
    }
    $gtpl = Join-Path $pkg 'config_template\gpt.local.template.json'
    if (Test-Path -LiteralPath $gtpl) {
        Copy-Item -LiteralPath $gtpl -Destination (Join-Path $Root 'config\gpt.local.template.json') -Force
    }

    # ---------- 5. uv ----------
    Write-Step '第 5 步 / 准备 uv（依赖管理器）'
    $uv = Find-Uv $Root
    if ($uv -and -not $Force -and (Test-Path -LiteralPath $uv)) {
        Write-Ok "已找到 uv：$uv"
    }
    else {
        try { $uv = Install-Uv $Root; Write-Ok "已准备 uv：$uv" }
        catch { Fail "准备 uv 失败" $_.Exception.Message }
    }
    $uvVer = cmd /c "`"$uv`" --version 2>&1"
    if ($LASTEXITCODE -ne 0) { Fail 'uv 无法运行' '删除 bin\uv.exe 后重新运行安装' }
    Write-Info2 "$uvVer"

    Set-ProjectEnv $Root
    Write-Ok '缓存 / 临时 / 浏览器目录已指向安装根目录'

    # ---------- 6. Python ----------
    Write-Step '第 6 步 / 准备 Python 3.12（装在安装目录内）'
    # 重复安装时安装根内已有可用的 3.12 就直接复用，不重复建链接
    $pyExe = ((cmd /c "`"$uv`" python find 3.12 2>nul") | Select-Object -Last 1)
    if ($pyExe) { $pyExe = $pyExe.Trim() }
    $pyReady = $false
    if ($pyExe -and (Test-Path -LiteralPath $pyExe)) {
        $pv = (cmd /c "`"$pyExe`" -V 2>&1") -join ' '
        if ($pv -match '3\.12\.') { $pyReady = $true; Write-Ok "复用已有 Python：$pyExe（$pv）" }
    }
    if (-not $pyReady) {
        $code = Invoke-Logged $uv 'python install 3.12'
        if ($code -ne 0) {
            $pyExe = ((cmd /c "`"$uv`" python find 3.12 2>nul") | Select-Object -Last 1)
            if ($pyExe) { $pyExe = $pyExe.Trim() }
            $pv = ''
            if ($pyExe -and (Test-Path -LiteralPath $pyExe)) { $pv = (cmd /c "`"$pyExe`" -V 2>&1") -join ' ' }
            if ($pv -match '3\.12\.') { Write-Warn2 "uv 建链接失败，但安装根内已有可用 Python 3.12（$pv），继续安装" }
            else { Fail 'Python 3.12 安装失败' '检查网络；或先自行安装 Python 3.12 后重试' }
        }
        $pyExe = ((cmd /c "`"$uv`" python find 3.12 2>nul") | Select-Object -Last 1)
        if ($pyExe) { $pyExe = $pyExe.Trim() }
    }

    if (-not $pyExe -or -not (Test-Path -LiteralPath $pyExe)) { Fail '未能定位 Python 解释器' '重新运行安装' }
    Write-Ok "Python：$pyExe"

    # ---------- 7. 小红书项目环境 ----------
    Write-Step '第 7 步 / 同步小红书项目依赖（按 uv.lock 核对，不凭 import 猜）'
    $xhsRepo = Join-Path $Root 'tools\xiaohongshu-skills'
    $xhsPy = Join-Path $Root 'tools\xiaohongshu-skills\.venv\Scripts\python.exe'
    $depCheck = Join-Path $PSScriptRoot 'check_deps.py'
    $needSync = $true
    if ((Test-Path -LiteralPath $xhsPy) -and -not $Force -and (Test-Path -LiteralPath $depCheck)) {
        $rawDep = cmd /c "`"$xhsPy`" `"$depCheck`" --uv-lock `"$(Join-Path $xhsRepo 'uv.lock')`" --pyproject `"$(Join-Path $xhsRepo 'pyproject.toml')`" 2>nul"
        $dep = $null
        try { $dep = (($rawDep | Select-Object -Last 1) | ConvertFrom-Json) } catch { $dep = $null }
        if ($dep -and $dep.ok) {
            $needSync = $false
            Write-Ok ("小红书依赖与 uv.lock 一致（核对 " + $dep.checked + " 项）")
        }
        elseif ($dep) {
            $bad = @()
            if ($dep.missing) { $bad += $dep.missing }
            if ($dep.mismatch) { $bad += $dep.mismatch }
            Write-Warn2 ("小红书依赖与 uv.lock 不一致：" + ($bad -join ', '))
        }
    }
    if ($needSync) {
        $env:UV_PROJECT_ENVIRONMENT = (Join-Path $xhsRepo '.venv')
        Push-Location -LiteralPath $xhsRepo
        try {
            $code = Invoke-Logged $uv ("sync --frozen --python `"$pyExe`"")
            if ($code -ne 0) { throw 'uv sync 失败' }
        }
        catch {
            Pop-Location
            Remove-Item Env:\UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
            Fail '小红书项目依赖安装失败' '检查网络后重新运行安装（可续装）'
        }
        Pop-Location
        Remove-Item Env:\UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
        Write-Ok '小红书项目依赖已同步'
    }
    else { Write-Ok '小红书项目依赖已是最新，跳过' }
    if (-not (Test-Path -LiteralPath $xhsPy)) { Fail '未生成小红书项目虚拟环境' '查看上方输出与日志' }

    # ---------- 8. 渲染项目环境 ----------
    Write-Step '第 8 步 / 安装渲染项目依赖（锁定版本）'
    $renderRepo = Join-Path $Root 'tools\Auto-Redbook-Skills'
    $renderPy = Join-Path $Root 'tools\Auto-Redbook-Skills\.venv\Scripts\python.exe'
    $lock = Join-Path $Root 'app\constraints\render-requirements.lock.txt'
    if (-not (Test-Path -LiteralPath $lock)) { Fail "缺少渲染依赖锁定清单：$lock" '请重新解压安装包' }
    $needRender = $true
    if ((Test-Path -LiteralPath $renderPy) -and -not $Force -and (Test-Path -LiteralPath $depCheck)) {
        $rawR = cmd /c "`"$renderPy`" `"$depCheck`" --requirements `"$lock`" 2>nul"
        $depR = $null
        try { $depR = (($rawR | Select-Object -Last 1) | ConvertFrom-Json) } catch { $depR = $null }
        if ($depR -and $depR.ok) {
            $needRender = $false
            Write-Ok ("渲染依赖与锁定清单一致（核对 " + $depR.checked + " 项）")
        }
        elseif ($depR) {
            $badR = @()
            if ($depR.missing) { $badR += $depR.missing }
            if ($depR.mismatch) { $badR += $depR.mismatch }
            Write-Warn2 ("渲染依赖需要同步：" + ($badR -join ', '))
        }
    }
    if ($needRender) {
        if (-not (Test-Path -LiteralPath $renderPy)) {
            $code = Invoke-Logged $uv ("venv `"$(Join-Path $renderRepo '.venv')`" --python `"$pyExe`"")
            if ($code -ne 0) { Fail '创建渲染虚拟环境失败' '查看日志后重试' }
        }
        $code = Invoke-Logged $uv ("pip install --python `"$renderPy`" -r `"$lock`"")
        if ($code -ne 0) { Fail '安装渲染依赖失败' '检查网络后重新运行安装（可续装）' }
        Write-Ok '渲染项目依赖已安装'
    }
    else { Write-Ok '渲染项目依赖已存在，跳过' }

    # ---------- 9. 渲染浏览器 ----------
    Write-Step '第 9 步 / 安装渲染用 Chromium（约 150MB）'
    $code = Invoke-Logged $renderPy '-m playwright install chromium'
    if ($code -ne 0) { Fail '下载 Chromium 失败' '检查网络后重新运行安装（已下载部分会复用）' }
    Write-Ok "浏览器目录：$($env:PLAYWRIGHT_BROWSERS_PATH)"

    # ---------- 10. 自检 ----------
    Write-Step '第 10 步 / 安装后自检'
    $okAll = $true
    if (Test-PyImport $xhsPy 'import websockets, requests, python_socks') { Write-Ok '小红书项目依赖导入正常' }
    else { Write-Err '小红书项目依赖导入异常'; $okAll = $false }

    if (Test-PyImport $renderPy 'import playwright, markdown, yaml') { Write-Ok '渲染项目依赖导入正常' }
    else { Write-Err '渲染项目依赖导入异常'; $okAll = $false }

    $cliPath = Join-Path $xhsRepo 'scripts\cli.py'
    $cliOut = cmd /c "`"$xhsPy`" `"$cliPath`" --help 2>&1"
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 '小红书 CLI 帮助未正常返回，可稍后用「检查环境.cmd」复查'
        $okAll = $false
    }
    else {
        $cliText = ($cliOut | Out-String)
        $needCmds = @('search-feeds', 'get-feed-detail', 'fill-publish', 'save-draft')
        $missingCmd = @($needCmds | Where-Object { -not $cliText.Contains($_) })
        if ($missingCmd.Count -gt 0) { Write-Warn2 ("小红书 CLI 缺少子命令：" + ($missingCmd -join ', ')); $okAll = $false }
        else { Write-Ok '小红书 CLI 可运行，关键子命令齐全' }
    }

    $workbenchCheck = Test-Workbench $Root
    foreach ($line in $workbenchCheck.lines) { Write-Info2 ([string]$line) }
    if (-not $workbenchCheck.ok) { $okAll = $false }

    $state = [ordered]@{
        version    = (Get-PkgVersion $pkg)
        installed  = $okAll
        updated_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        uv         = $uv
        python     = $pyExe
        root       = $Root
    }
    Save-ConfigUtf8 (Join-Path $Root 'config\install-state.json') $state

    if (-not $okAll) {
        # 自检没过就不能报安装成功，也不许 exit 0
        try { Stop-Transcript | Out-Null } catch { }
        Write-Host ''
        Write-Host '=========================================' -ForegroundColor Red
        Write-Host '  安装自检未通过（退出码 1）' -ForegroundColor Red
        Write-Host '=========================================' -ForegroundColor Red
        Write-Host '处理：按上面的失败项处理后重新双击「安装.cmd」，已完成的步骤会跳过，不会覆盖你的资料。' -ForegroundColor Yellow
        Write-Host "安装日志：$logFile"
        Write-Host ''
        exit 1
    }

    Write-Host ''
    if (-not (Test-ModelConfig $Root)) { Write-Warn2 '程序已安装、写稿模型待配置（仅本地检查，未进行真实付费调用）' }
    Write-Host '=========================================' -ForegroundColor Green
    if ($okAll) { Write-Host '  安装完成' -ForegroundColor Green }
    else { Write-Host '  安装基本完成，有项目需要复查' -ForegroundColor Yellow }
    Write-Host '=========================================' -ForegroundColor Green
    Write-Host ''
    Write-Host '接下来按顺序做 4 件事：' -ForegroundColor Cyan
    Write-Host '  1) Chrome 加载扩展：chrome://extensions -> 开发者模式 -> 加载已解压的扩展程序'
    Write-Host "     选择目录：$(Join-Path $Root 'tools\xiaohongshu-skills\extension')"
    Write-Host '  2) 在这个 Chrome 里登录你自己的小红书账号'
    Write-Host '  3) 扣子桌面端：开启本地文件访问 -> 添加扫描目录 -> 给目标 Agent 添加本机技能'
    Write-Host "     扫描目录填：$(Join-Path $Root 'skills')"
    Write-Host "  4) 双击安装目录里的「启动助手.cmd」并保留窗口，再在扣子对话里发送：开始今天的工作"
    Write-Host ''
    Write-Host '以后每天只用安装目录里的这三个入口，不用再回原解压目录：' -ForegroundColor Cyan
    Write-Host "  启动 Bridge：$(Join-Path $Root '启动助手.cmd')"
    Write-Host "  复查环境：  $(Join-Path $Root '检查环境.cmd')"
    Write-Host "  重装/升级： $(Join-Path $Root '安装.cmd')"
    Write-Host "  更新版本： $(Join-Path $Root '更新工作台.cmd')  （首次需先运行 接入Git更新.cmd）"
    Write-Host ''
    Write-Host "详细说明：$(Join-Path $Root '先看这里.md')" -ForegroundColor Cyan
    Write-Host "安装日志：$logFile"
    Write-Host ''
}
catch {
    Write-Err ("安装中断：" + $_.Exception.Message)
    Write-Host "安装日志：$logFile" -ForegroundColor Yellow
    Write-Host '处理：修正上面的问题后重新双击「安装.cmd」，已完成的步骤会跳过，不会覆盖你的资料。' -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

try { Stop-Transcript | Out-Null } catch { }
exit 0

