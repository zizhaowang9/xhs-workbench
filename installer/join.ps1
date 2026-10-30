# XHS 工作台 · 首次接入 Git 更新
# 用法：双击「接入Git更新.cmd」，或在任意位置执行：
#       powershell -File join.ps1 -Root "D:\XHSWork" -Url "https://github.com/你的账号/xhs-workbench.git"

param(
    [string]$Root = '',
    [string]$Url = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
. (Join-Path $PSScriptRoot 'lib.ps1')

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '  XHS 工作台 首次接入 Git 更新' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan

$logFile = ''
function Fail3($msg, $hint, $code) {
    Write-Err ([string]$msg)
    if ($hint) { Write-Host ('    处理建议：' + [string]$hint) -ForegroundColor Yellow }
    if ($logFile) { Write-Host ('    日志：' + $logFile) -ForegroundColor Yellow }
    try { Stop-Transcript | Out-Null } catch { }
    if ($code) { exit $code }
    exit 1
}

# ---------- 1 原安装目录 ----------
Write-Step '第 1 步 / 确认原工作台安装目录'
if (-not $Root) { $Root = Resolve-InstallRoot }
if (-not $Root) {
    $def = Get-DefaultRoot
    if ($def) {
        $in = Read-Host ('    原工作台安装目录（直接回车用默认 ' + $def + '）')
        if ([string]::IsNullOrWhiteSpace($in)) { $Root = $def } else { $Root = $in.Trim('"').Trim() }
    }
    else {
        $in = Read-Host '    原工作台安装目录（例如 D:\XHSWork）'
        if ([string]::IsNullOrWhiteSpace($in)) { Fail3 '未指定安装目录' $null 1 }
        $Root = $in.Trim('"').Trim()
    }
}
$Root = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $Root 'config\paths.json'))) {
    Fail3 ('这里不是工作台安装目录：' + $Root) '先完成 1.0.1 安装（安装.cmd），或填对安装目录'
}
$cfg = Read-Config $Root
Set-ProjectEnv $Root
$curVer = Get-PkgVersion $Root
if ($curVer -like '0.0.0*' -and $cfg -and $cfg.version) { $curVer = [string]$cfg.version }
Write-Ok ('安装根：' + $Root)
Write-Ok ('当前版本：' + $curVer)

# ---------- 2 Git ----------
Write-Step '第 2 步 / 检查 Git'
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Err '本机没有找到 Git。'
    Write-Host ''
    Write-Host '  安装步骤（约 2 分钟）：' -ForegroundColor Cyan
    Write-Host '  1) 打开官方下载页：https://git-scm.com/download/win'
    Write-Host '  2) 下载 64-bit Git for Windows Setup，双击运行'
    Write-Host '  3) 一路 Next 即可（默认选项都可用）'
    Write-Host '  4) 装完关掉现在这个窗口，重新双击「接入Git更新.cmd」'
    Write-Host ''
    Write-Host '  不需要在聊天里提供任何访问令牌。' -ForegroundColor Yellow
    exit 2
}
$git = $gitCmd.Source
$gitVer = ((Invoke-Git $git @('--version')).lines -join ' ').Trim()
Write-Ok ($gitVer + '  ' + $git)

# ---------- 3 仓库目录 ----------
Write-Step '第 3 步 / 确定仓库目录'
$Repo = Join-Path $Root 'team-repo'
if (Test-Path -LiteralPath (Join-Path $Repo '.git')) {
    Write-Info2 '仓库已存在；继续检查并应用，修复上次未完成的接入。'
    & (Join-Path $PSScriptRoot 'update.ps1') -Root $Root -Repo $Repo
    exit $LASTEXITCODE
}
Write-Info2 ('仓库目录：' + $Repo)

# ---------- 4 仓库地址 ----------
# 优先级：-Url 参数 > 安装目录 team-repo-url.txt（本机覆盖）> 随包 installer\repo-url.txt（公共、不含凭据）
$urlFile = Join-Path $Root 'team-repo-url.txt'
if (-not $Url -and (Test-Path -LiteralPath $urlFile)) {
    $Url = ([string](Get-Content -LiteralPath $urlFile -TotalCount 1 -Encoding UTF8)).Trim()
    if ($Url) { Write-Info2 ('仓库地址来自本机配置：' + $urlFile) }
}
$pkgUrlFile = Join-Path $PSScriptRoot 'repo-url.txt'
if (-not $Url -and (Test-Path -LiteralPath $pkgUrlFile)) {
    $Url = ([string](Get-Content -LiteralPath $pkgUrlFile -TotalCount 1 -Encoding UTF8)).Trim()
    if ($Url) { Write-Info2 ('仓库地址来自随包配置：' + $pkgUrlFile) }
}
if (-not $Url) {
    Write-Warn2 '还没有配置团队仓库地址。'
    Write-Host '  请向发布人索取私有仓库地址（形如 https://github.com/账号/xhs-workbench.git），' -ForegroundColor Yellow
    Write-Host '  填一次即可：把它写入 ' -ForegroundColor Yellow
    Write-Host ('  ' + $urlFile) -ForegroundColor Yellow
    Write-Host '  或重新运行：powershell -File installer\join.ps1 -Root "' + $Root + '" -Url "仓库地址"' -ForegroundColor Yellow
    exit 3
}
$normalizedUrl = $Url.TrimEnd('/') -replace '\.git$', ''
if ($normalizedUrl -notin @('https://github.com/zizhaowang9/xhs-workbench', 'git@github.com:zizhaowang9/xhs-workbench')) { Fail3 '仓库地址不是发布仓库 zizhaowang9/xhs-workbench' '请使用发布仓库地址，不在地址中嵌入凭据' 3 }
Write-Info2 '仓库地址已核对：zizhaowang9/xhs-workbench'

# ---------- 5 备份个人资料 ----------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir ('join-' + $stamp + '.log')
Start-Transcript -Path $logFile -Append -Force | Out-Null

$backupRoot = Join-Path $Root ('backups\join-' + $stamp)
Write-Step '第 4 步 / 备份现有资料'
foreach ($d in @('config', 'skills', 'knowledge')) {
    $s = Join-Path $Root $d
    if (-not (Test-Path -LiteralPath $s)) { continue }
    $t = Join-Path $backupRoot $d
    New-Item -ItemType Directory -Path $t -Force | Out-Null
    Copy-Item -LiteralPath $s -Destination $t -Recurse -Force
    Write-Ok ('已备份 ' + $d + ' -> ' + $t)
}

# ---------- 6 克隆 ----------
Write-Step '第 5 步 / 克隆团队仓库'
Write-Info2 '如果弹出登录窗口，请用你自己的 GitHub 账号正常登录（密码/浏览器授权，不在聊天里填）。'
$rgc = Invoke-Git $git @('clone', '--branch', 'main', $Url, $Repo)
foreach ($l in $rgc.lines) { if ($l) { Write-Info2 $l } }
if ($rgc.code -ne 0) {
    Fail3 '克隆失败' '确认仓库地址正确、你本人有该私有仓库的访问权限；登录后重新运行本脚本'
}
$pulled = ((Invoke-Git $git @('-C', $Repo, 'rev-parse', 'HEAD')).lines -join '').Trim()
Write-Ok ('已克隆：' + $pulled)
$pkgVer = Get-PkgVersion $Repo
Write-Ok ('仓库版本号：' + $pkgVer)

try {
    Assert-TeamRepository $git $Repo
    $previousState = Get-WorkbenchState $Root
    Save-WorkbenchState $Root ([ordered]@{ pulled_commit = $pulled; applied_commit = $(if ($previousState) { [string]$previousState.applied_commit } else { '' }); last_result = 'applying'; backup_dir = $backupRoot })
    # ---------- 7 应用公共文件 ----------
    Write-Step '第 6 步 / 应用程序与公共知识库'
    $r = Invoke-SharedApply $Repo $Root $stamp (Join-Path $backupRoot 'applied')
    Write-Ok ('已应用公共文件 ' + $r.copied + ' 个（覆盖前已备份 ' + $r.backed + ' 个）')
    $seeded = Invoke-SeedApply $Repo $Root
    if ($seeded.Count -gt 0) {
        foreach ($s in $seeded) { Write-Ok ('初始化个人资料模板：' + [string]$s) }
    }
    Write-Info2 '你原有的定位、反馈、历史、稿件与自定义配置都保留在原位。'

    # ---------- 8 paths.json ----------
    $cfg = Read-Config $Root
    if ($cfg) {
        if (-not $cfg.knowledge_dir) {
            $cfg | Add-Member -NotePropertyName knowledge_dir -NotePropertyValue (Join-Path $Root 'knowledge') -Force
        }
        $cfg | Add-Member -NotePropertyName version -NotePropertyValue $pkgVer -Force
        Save-ConfigUtf8 (Join-Path $Root 'config\paths.json') $cfg
        Write-Ok 'paths.json 已更新（保留你的模型地址、端口等自定义字段）'
    }

    # ---------- 9 依赖 ----------
    Write-Step '第 7 步 / 检查运行环境（复用现有虚拟环境，不重装）'
    $uv = Find-Uv $Root
    if ($uv) { Write-Ok ('uv：' + $uv) } else { Write-Warn2 '未找到 uv；如需重装依赖，请运行安装目录里的「安装.cmd」' }
    $renderLock = Join-Path $Root 'app\constraints\render-requirements.lock.txt'
    $xhsLock = Join-Path $Root 'tools\xiaohongshu-skills\uv.lock'
    $xhsPy = Join-Path $Root 'tools\xiaohongshu-skills\.venv\Scripts\python.exe'
    $renderPy = Join-Path $Root 'tools\Auto-Redbook-Skills\.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $xhsPy) { Write-Ok '小红书环境已存在，直接复用' } else { Write-Warn2 '缺少小红书环境，稍后用「安装.cmd」补齐' }
    if (Test-Path -LiteralPath $renderPy) { Write-Ok '渲染环境已存在，直接复用' } else { Write-Warn2 '缺少渲染环境，稍后用「安装.cmd」补齐' }

    # ---------- 10 自检 ----------
    Write-Step '第 8 步 / 接入后自检'
    $t = Test-Workbench $Root
    foreach ($line in $t.lines) { Write-Info2 ([string]$line) }
    if (-not $t.ok) { throw ('接入自检未通过（' + $t.bad + ' 项）') }
    Write-Ok '版本、安装根、知识库路径、关键文件均通过'

    $newState = [ordered]@{
        version         = $pkgVer
        pulled_commit   = $pulled
        applied_commit  = $pulled
        applied_at      = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        joined_at       = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        last_result     = 'ok'
        backup_dir      = $backupRoot
        render_lock_sha = (Get-LockSha $renderLock)
        xhs_lock_sha    = (Get-LockSha $xhsLock)
        repo            = $Repo
        remote          = $Url
        branch          = 'main'
    }
    Save-WorkbenchState $Root $newState

    $modelReady = Test-ModelConfig $Root
    Write-Host ''
    Write-Host '=========================================' -ForegroundColor Green
    Write-Host '  接入完成' -ForegroundColor Green
    Write-Host '=========================================' -ForegroundColor Green
    Write-Host ('  仓库：            ' + $Repo)
    Write-Host ('  已拉取提交：      ' + $pulled)
    Write-Host ('  已成功应用提交：  ' + $pulled)
    Write-Host ('  版本：            ' + $pkgVer)
    Write-Host ('  备份目录：        ' + $backupRoot)
    Write-Host ''
    Write-Host '  以后更新：双击安装目录里的「更新工作台.cmd」' -ForegroundColor Cyan
    Write-Host ('  路径：' + (Join-Path $Root '更新工作台.cmd'))
    if (-not $modelReady) {
        Write-Host ''
        Write-Warn2 '程序已更新、写稿模型待配置'
        Write-Info2 ('填写入口：' + (Join-Path $Root 'config\gpt.local.json') + '（模板：config\gpt.local.template.json）')
        Write-Info2 '填你自己的服务地址、协议、模型 ID、密钥；不要用别人的配置。'
    }
    Write-Host ''
    Write-Host '  请让扣子实际读一次新版文件：' -ForegroundColor Cyan
    Write-Host ('  读一下 ' + (Join-Path $Root 'skills\xhs-daily\SKILL.md') + ' 和 ' + (Join-Path $Root 'knowledge\00-首页.md') + '，说出第一条规则')
    Write-Host ''
    Write-Host ('日志：' + $logFile)
    Write-Host ''
}
catch {
    Write-Err ('接入中断：' + [string]$_.Exception.Message)
    Write-Warn2 ('接入可能部分应用；未执行整体回滚。备份：' + $backupRoot)
    try { Save-WorkbenchState $Root ([ordered]@{ pulled_commit = $pulled; applied_commit = $(if ($previousState) { [string]$previousState.applied_commit } else { '' }); last_result = 'failed_partial_apply'; backup_dir = $backupRoot; last_error = [string]$_.Exception.Message }) } catch { Write-Err '失败状态无法保存；请保留日志并修复目录权限。' }
    Write-Host ('日志：' + $logFile) -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

try { Stop-Transcript | Out-Null } catch { }
exit 0

