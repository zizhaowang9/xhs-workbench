# XHS 工作台 · 日常更新（Git 拉取 + 应用）
# 用法：在安装目录里双击「更新工作台.cmd」
#      powershell -File update.ps1 -Root "D:\XHSWork" [-CheckOnly]

param(
    [string]$Root = '',
    [string]$Repo = '',
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
. (Join-Path $PSScriptRoot 'lib.ps1')

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '  XHS 工作台 更新（Git）' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan

$logFile = ''
function Fail2($msg, $hint) {
    Write-Err ([string]$msg)
    if ($hint) { Write-Host ('    处理建议：' + [string]$hint) -ForegroundColor Yellow }
    if ($logFile) { Write-Host ('    日志：' + $logFile) -ForegroundColor Yellow }
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

# ---------- 1 安装根 ----------
Write-Step '第 1 步 / 确认安装目录'
if (-not $Root) { $Root = Resolve-InstallRoot }
if (-not $Root) {
    $def = Get-DefaultRoot
    if ($def -and (Test-Path -LiteralPath (Join-Path $def 'config\paths.json'))) { $Root = $def }
    else {
        Write-Warn2 '没有自动找到工作台安装目录（缺 config\paths.json）。'
        $in = Read-Host '    请输入工作台安装目录（例如 D:\XHSWork）'
        if ([string]::IsNullOrWhiteSpace($in)) { Fail2 '未指定安装目录' $null }
        $Root = $in.Trim('"').Trim()
    }
}
$Root = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $Root 'config\paths.json'))) {
    Fail2 ('这不是工作台安装目录：' + $Root) '确认路径；1.0.1 的安装里应该有 config\paths.json'
}
Write-Ok ('安装根：' + $Root)

# ---------- 2 仓库 ----------
if (-not $Repo) { $Repo = Join-Path $Root 'team-repo' }
if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) {
    Fail2 ('未找到已接入的仓库：' + $Repo) '先运行「接入Git更新.cmd」完成首次接入'
}
Write-Info2 ('仓库：' + $Repo)

# ---------- 3 Git ----------
Write-Step '第 2 步 / 检查 Git'
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) { Fail2 '未找到 Git' '安装 Git 后重新打开窗口：https://git-scm.com/download/win' }
$git = $gitCmd.Source
Write-Ok ('Git：' + $git)

# ---------- 4 日志 ----------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir ('update-' + $stamp + '.log')
Start-Transcript -Path $logFile -Append -Force | Out-Null

$backupRoot = Join-Path $Root ('backups\update-' + $stamp)
$state = Get-WorkbenchState $Root
$prevVersion = ''
$prevRender = ''
$prevXhs = ''
if ($state) {
    $prevVersion = [string]$state.version
    $prevRender = [string]$state.render_lock_sha
    $prevXhs = [string]$state.xhs_lock_sha
}
if ($prevVersion) { Write-Info2 ('当前已应用版本：' + $prevVersion) }
else { Write-Info2 '没有历史更新记录（首次更新）' }

$pulled = ''
$branch = ''
$remote = ''
$pkgVer = ''
$renderSha = ''
$xhsSha = ''

# ---------- 5 仓库状态 ----------
Write-Step '第 3 步 / 核对仓库状态'
$rg1 = Invoke-Git $git @('-C', $Repo, 'rev-parse', '--abbrev-ref', 'HEAD')
$branch = (($rg1.lines) -join '').Trim()
$rg2 = Invoke-Git $git @('-C', $Repo, 'remote', 'get-url', 'origin')
if ($rg2.code -eq 0) { $remote = (($rg2.lines) -join '').Trim() } else { $remote = '' }
Write-Info2 ('分支：' + $branch)
Write-Info2 ('远端：' + $remote)
if ($branch -ne 'main') {
    Fail2 ('当前分支是 ' + $branch + '，不是 main') ('切回 main 后再更新：git -C "' + $Repo + '" checkout main')
}

$rg3 = Invoke-Git $git @('-C', $Repo, 'status', '--porcelain')
$dirtyRaw = @($rg3.lines)
$dirty = @($dirtyRaw | Where-Object { $_ -and ([string]$_).Trim() -ne '' })
if ($dirty.Count -gt 0) {
    Write-Err ('仓库里有未提交的本地修改（' + $dirty.Count + ' 项）：')
    foreach ($d in ($dirty | Select-Object -First 10)) { Write-Info2 ([string]$d) }
    Fail2 '为保护你的改动，本次没有拉取、也没有改任何文件' '把改动交回发布端处理，或用 git stash 暂存后重试；不要 reset --hard、不要 clean'
}
Write-Ok '仓库干净（没有未提交的本地修改）'

# ---------- 6 拉取 ----------
Write-Step '第 4 步 / 从远端拉取'
$rg4 = Invoke-Git $git @('-C', $Repo, 'fetch', '--all', '--tags', '--prune')
foreach ($l in $rg4.lines) { if ($l) { Write-Info2 $l } }
if ($rg4.code -ne 0) { Fail2 'git fetch 失败（网络或权限）' '检查网络/代理与仓库访问权限后重试' }
$before = ((Invoke-Git $git @('-C', $Repo, 'rev-parse', 'HEAD')).lines -join '').Trim()
$rg5 = Invoke-Git $git @('-C', $Repo, 'pull', '--ff-only')
foreach ($l in $rg5.lines) { if ($l) { Write-Info2 $l } }
if ($rg5.code -ne 0) {
    Fail2 'git pull --ff-only 失败：本地与远端已分叉' '不要强推、不要 reset --hard；把窗口里的提示发给发布端'
}
$pulled = ((Invoke-Git $git @('-C', $Repo, 'rev-parse', 'HEAD')).lines -join '').Trim()
$pkgVer = Get-PkgVersion $Repo
if ($before -eq $pulled) { Write-Ok ('仓库已是最新：' + $pulled) }
else { Write-Ok ('已拉取提交：' + $pulled) }
Write-Ok ('仓库版本号：' + $pkgVer)

if ($CheckOnly) {
    Write-Info2 '只检查模式：没有改动任何文件'
    try { Stop-Transcript | Out-Null } catch { }
    exit 0
}

try {
    # ---------- 7 备份 + 应用 ----------
    Write-Step '第 5 步 / 备份并应用公共文件'
    $r = Invoke-SharedApply $Repo $Root $stamp $backupRoot
    Write-Ok ('已备份原有文件 ' + $r.backed + ' 个 -> ' + $backupRoot)
    Write-Ok ('已应用公共文件 ' + $r.copied + ' 个')
    $seeded = Invoke-SeedApply $Repo $Root
    if ($seeded.Count -gt 0) {
        foreach ($s in $seeded) { Write-Ok ('新增个人资料模板：' + [string]$s) }
    }
    else { Write-Info2 '个人资料已存在，全部保留（没有覆盖任何个人文件）' }

    # ---------- 8 paths.json 补字段 ----------
    $cfg = Read-Config $Root
    if ($cfg -and -not $cfg.knowledge_dir) {
        $cfg | Add-Member -NotePropertyName knowledge_dir -NotePropertyValue (Join-Path $Root 'knowledge') -Force
        Save-ConfigUtf8 (Join-Path $Root 'config\paths.json') $cfg
        Write-Ok 'paths.json 已补 knowledge_dir'
    }

    # ---------- 9 依赖（只在锁文件变化时） ----------
    Write-Step '第 6 步 / 依赖'
    $renderLock = Join-Path $Root 'app\constraints\render-requirements.lock.txt'
    $xhsLock = Join-Path $Root 'tools\xiaohongshu-skills\uv.lock'
    $renderSha = Get-LockSha $renderLock
    $xhsSha = Get-LockSha $xhsLock
    $needDeps = $false
    if ($prevRender -and $renderSha -and $prevRender -ne $renderSha) { $needDeps = $true }
    if ($prevXhs -and $xhsSha -and $prevXhs -ne $xhsSha) { $needDeps = $true }
    if ($needDeps) {
        Write-Warn2 '依赖锁定清单有变化，同步依赖（不会重装整个环境）'
        $uv = Find-Uv $Root
        $xhsRepo = Join-Path $Root 'tools\xiaohongshu-skills'
        if ($uv -and (Test-Path -LiteralPath $xhsLock)) {
            $env:UV_PROJECT_ENVIRONMENT = (Join-Path $xhsRepo '.venv')
            Push-Location -LiteralPath $xhsRepo
            $code = Invoke-Logged $uv 'sync --frozen'
            Pop-Location
            Remove-Item Env:\UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
            if ($code -ne 0) { throw 'uv sync 失败' }
            Write-Ok '小红书依赖已同步'
        }
        $renderPy = Join-Path $Root 'tools\Auto-Redbook-Skills\.venv\Scripts\python.exe'
        if ($uv -and (Test-Path -LiteralPath $renderPy) -and (Test-Path -LiteralPath $renderLock)) {
            $code = Invoke-Logged $uv ('pip install --python "' + $renderPy + '" -r "' + $renderLock + '"')
            if ($code -ne 0) { throw '渲染依赖同步失败' }
            Write-Ok '渲染依赖已同步'
        }
    }
    else { Write-Info2 '依赖锁定清单没有变化，跳过依赖安装' }

    # ---------- 10 自检 ----------
    Write-Step '第 7 步 / 更新后自检'
    $t = Test-Workbench $Root
    foreach ($line in $t.lines) { Write-Info2 ([string]$line) }
    if (-not $t.ok) { throw ('更新后自检未通过（' + $t.bad + ' 项）') }
    Write-Ok '版本、安装根、知识库路径、关键文件均通过'

    # ---------- 11 记录状态 ----------
    $newState = [ordered]@{
        version         = $pkgVer
        pulled_commit   = $pulled
        applied_commit  = $pulled
        applied_at      = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        last_result     = 'ok'
        backup_dir      = $backupRoot
        render_lock_sha = $renderSha
        xhs_lock_sha    = $xhsSha
        repo            = $Repo
        remote          = $remote
        branch          = $branch
    }
    Save-WorkbenchState $Root $newState

    $modelReady = Test-ModelConfig $Root
    Write-Host ''
    Write-Host '=========================================' -ForegroundColor Green
    Write-Host '  更新完成' -ForegroundColor Green
    Write-Host '=========================================' -ForegroundColor Green
    Write-Host ('  已拉取提交：      ' + $pulled)
    Write-Host ('  已成功应用提交：  ' + $pulled)
    Write-Host ('  版本：            ' + $pkgVer)
    Write-Host ('  备份目录：        ' + $backupRoot)
    if (-not $modelReady) {
        Write-Host ''
        Write-Warn2 '程序已更新、写稿模型待配置'
        Write-Info2 ('填写入口：' + (Join-Path $Root 'config\gpt.local.json') + '（模板见 config\gpt.local.template.json）')
    }
    Write-Host ''
    Write-Host '  请让扣子实际读一次新版文件（文件更新不等于 Agent 已读取）：' -ForegroundColor Cyan
    Write-Host ('  读一下 ' + (Join-Path $Root 'skills\xhs-daily\SKILL.md') + ' 和 ' + (Join-Path $Root 'knowledge\00-首页.md') + '，说出第一条规则')
    Write-Host ''
    Write-Host ('日志：' + $logFile)
    Write-Host ''
}
catch {
    $msg = [string]$_.Exception.Message
    Write-Err ('更新中断：' + $msg)
    $restored = 0
    if (Test-Path -LiteralPath $backupRoot) { $restored = Restore-FromBackup $backupRoot $Root }
    if ($restored -gt 0) { Write-Warn2 ('已从备份恢复 ' + $restored + ' 个文件（' + $backupRoot + '）') }
    $failed = [ordered]@{
        version         = $prevVersion
        pulled_commit   = $pulled
        applied_commit  = ''
        applied_at      = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        last_result     = 'failed'
        last_error      = $msg
        backup_dir      = $backupRoot
        render_lock_sha = $prevRender
        xhs_lock_sha    = $prevXhs
        repo            = $Repo
        remote          = $remote
        branch          = $branch
    }
    try { Save-WorkbenchState $Root $failed } catch { }
    Write-Host ('日志：' + $logFile) -ForegroundColor Yellow
    Write-Host '处理：按上面的提示修正后重新双击「更新工作台.cmd」；个人资料已在备份目录里，不会丢。' -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

try { Stop-Transcript | Out-Null } catch { }
exit 0
