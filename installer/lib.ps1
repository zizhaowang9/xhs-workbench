# XHS 工作台 · 公共库（安装 / 接入 / 更新共用）
# 本文件以 UTF-8 BOM 保存，兼容 Windows PowerShell 5.1 的中文解析。

$ErrorActionPreference = 'Stop'

# 发布清单缺失时的兜底映射（正常以 manifest.json 为准）
$script:SHARED_MAP = @(
    @{ Src = 'tools\xiaohongshu-skills';  Dst = 'tools\xiaohongshu-skills' },
    @{ Src = 'tools\Auto-Redbook-Skills'; Dst = 'tools\Auto-Redbook-Skills' },
    @{ Src = 'tools\gpt-writer';          Dst = 'tools\gpt-writer' },
    @{ Src = 'app\adapters';              Dst = 'app\adapters' },
    @{ Src = 'app\constraints';           Dst = 'app\constraints' },
    @{ Src = 'installer';                 Dst = 'installer' },
    @{ Src = 'config_template';           Dst = 'config_template' },
    @{ Src = 'docs';                      Dst = 'docs' },
    @{ Src = 'docs\samples';              Dst = 'sample\cover-themes' },
    @{ Src = 'knowledge';                 Dst = 'knowledge' },
    @{ Src = 'skills\xhs-daily';          Dst = 'skills\xhs-daily' }
)

$script:ROOT_FILES = @('安装.cmd', '检查环境.cmd', '启动助手.cmd', '更新工作台.cmd', '先看这里.md', 'CHANGELOG.md', 'VERSION')

function Invoke-Git($GitExe, [string[]]$GitArgs) {
    # PowerShell 5.1 下原生命令写 stderr 会被当成终止错误；这里局部降级为 Continue
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $lines = New-Object System.Collections.ArrayList
    $code = 0
    try {
        $raw = & $GitExe @GitArgs 2>&1
        $code = $LASTEXITCODE
        foreach ($l in @($raw)) { [void]$lines.Add(([string]$l).TrimEnd()) }
    }
    finally { $ErrorActionPreference = $oldEap }
    return [pscustomobject]@{ code = $code; lines = $lines }
}

function Get-PkgVersion($pkg) {
    $v = Join-Path $pkg 'VERSION'
    if (Test-Path -LiteralPath $v) {
        $line = (Get-Content -LiteralPath $v -TotalCount 1 -Encoding UTF8)
        if ($line) { return ([string]$line).Trim() }
    }
    return '0.0.0-unknown'
}

function Get-Manifest($pkg) {
    $p = Join-Path $pkg 'manifest.json'
    if (-not (Test-Path -LiteralPath $p)) { return $null }
    try {
        $text = [System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8)
        return ($text | ConvertFrom-Json)
    }
    catch { return $null }
}

function Get-SharedFiles($pkg) {
    # 返回 @{ Src; Rel } 列表：Rel 是相对安装根的路径
    $list = New-Object System.Collections.ArrayList
    $mf = Get-Manifest $pkg
    if ($mf -and $mf.entries) {
        foreach ($e in $mf.entries) {
            $mode = [string]$e.mode
            if ($mode -eq 'seed' -or $mode -eq 'preserve') { continue }
            $s = Join-Path $pkg ([string]$e.from)
            if (-not (Test-Path -LiteralPath $s)) { continue }
            if ((Get-Item -LiteralPath $s).PSIsContainer) {
                $files = Get-ChildItem -LiteralPath $s -Recurse -File -Force
                foreach ($f in $files) {
                    $rel = $f.FullName.Substring($s.Length).TrimStart('\')
                    [void]$list.Add(@{ Src = $f.FullName; Rel = ([string]$e.to + '\' + $rel) })
                }
            }
            else {
                [void]$list.Add(@{ Src = $s; Rel = [string]$e.to })
            }
        }
        foreach ($f in $mf.root_files) {
            $s = Join-Path $pkg ([string]$f)
            if (Test-Path -LiteralPath $s) { [void]$list.Add(@{ Src = $s; Rel = [string]$f }) }
        }
        return $list
    }
    foreach ($m in $script:SHARED_MAP) {
        $s = Join-Path $pkg $m.Src
        if (-not (Test-Path -LiteralPath $s)) { continue }
        foreach ($f in (Get-ChildItem -LiteralPath $s -Recurse -File -Force)) {
            $rel = $f.FullName.Substring($s.Length).TrimStart('\')
            [void]$list.Add(@{ Src = $f.FullName; Rel = ($m.Dst + '\' + $rel) })
        }
    }
    foreach ($f in $script:ROOT_FILES) {
        $s = Join-Path $pkg $f
        if (Test-Path -LiteralPath $s) { [void]$list.Add(@{ Src = $s; Rel = $f }) }
    }
    return $list
}

function Invoke-SharedApply($pkg, $Root, $Stamp, $BackupRoot) {
    # shared 文件：先备份已有同名文件，再覆盖
    $files = Get-SharedFiles $pkg
    $backed = 0
    if ($BackupRoot) {
        foreach ($f in $files) {
            $dst = Join-Path $Root $f.Rel
            if (-not (Test-Path -LiteralPath $dst)) { continue }
            $bd = Join-Path $BackupRoot (Split-Path -Parent $f.Rel)
            if (-not (Test-Path -LiteralPath $bd)) { New-Item -ItemType Directory -Path $bd -Force | Out-Null }
            Copy-Item -LiteralPath $dst -Destination (Join-Path $BackupRoot $f.Rel) -Force
            $backed++
        }
    }
    $copied = 0
    foreach ($f in $files) {
        $dst = Join-Path $Root $f.Rel
        $dd = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dd)) { New-Item -ItemType Directory -Path $dd -Force | Out-Null }
        Copy-Item -LiteralPath $f.Src -Destination $dst -Force
        $copied++
    }
    return [pscustomobject]@{ copied = $copied; backed = $backed; total = $files.Count }
}

function Invoke-SeedApply($pkg, $Root) {
    # seed 文件：只在本机不存在时写入；已存在的一律保留
    $seed = Join-Path $pkg 'seed'
    $added = New-Object System.Collections.ArrayList
    if (-not (Test-Path -LiteralPath $seed)) { return $added }
    foreach ($f in (Get-ChildItem -LiteralPath $seed -Recurse -File -Force)) {
        $rel = $f.FullName.Substring($seed.Length).TrimStart('\')
        $dst = Join-Path $Root $rel
        if (Test-Path -LiteralPath $dst) { continue }
        $dd = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dd)) { New-Item -ItemType Directory -Path $dd -Force | Out-Null }
        Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
        [void]$added.Add($rel)
    }
    return $added
}

function Restore-FromBackup($BackupRoot, $Root) {
    if (-not (Test-Path -LiteralPath $BackupRoot)) { return 0 }
    $n = 0
    foreach ($f in (Get-ChildItem -LiteralPath $BackupRoot -Recurse -File -Force)) {
        $rel = $f.FullName.Substring($BackupRoot.Length).TrimStart('\')
        $dst = Join-Path $Root $rel
        $dd = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dd)) { New-Item -ItemType Directory -Path $dd -Force | Out-Null }
        Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
        $n++
    }
    return $n
}

function Get-WorkbenchState($Root) {
    $p = Join-Path $Root 'config\update-state.json'
    if (-not (Test-Path -LiteralPath $p)) { return $null }
    try {
        $text = [System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8)
        return ($text | ConvertFrom-Json)
    }
    catch { return $null }
}

function Save-WorkbenchState($Root, $State) {
    Save-ConfigUtf8 (Join-Path $Root 'config\update-state.json') $State
}

function Test-ModelConfig($Root) {
    # Inspect configuration only. Never print the parsed data or contact a provider.
    $p = Join-Path $Root 'config\gpt.local.json'
    if (-not (Test-Path -LiteralPath $p)) { return $false }
    try {
        $c = Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not ([string]$c.provider).Trim() -or -not ([string]$c.model).Trim()) { return $false }
        if ($c.protocol -notin @('responses', 'chat_completions')) { return $false }
        $uri = $null
        if (-not [Uri]::TryCreate([string]$c.base_url, [UriKind]::Absolute, [ref]$uri)) { return $false }
        if ($uri.Scheme -notin @('https', 'http') -or -not $uri.Host) { return $false }
        $key = ([string]$c.api_key).Trim()
        $keyEnv = [string]$c.api_key_env
        if (-not $keyEnv) { $keyEnv = 'XHS_GPT_API_KEY' }
        if (-not $key) { $key = [Environment]::GetEnvironmentVariable($keyEnv, 'Process') }
        return (-not [string]::IsNullOrWhiteSpace($key))
    } catch { return $false }
}

function Assert-TeamRepository($GitExe, $Repo) {
    $origin = Invoke-Git $GitExe @('-C', $Repo, 'remote', 'get-url', 'origin')
    $url = ($origin.lines -join '').Trim().TrimEnd('/') -replace '\.git$', ''
    if ($origin.code -ne 0 -or $url -notin @('https://github.com/zizhaowang9/xhs-workbench', 'git@github.com:zizhaowang9/xhs-workbench')) {
        throw 'origin 不是发布仓库 zizhaowang9/xhs-workbench；停止更新。'
    }
    $upstream = Invoke-Git $GitExe @('-C', $Repo, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    if ($upstream.code -ne 0 -or ($upstream.lines -join '').Trim() -ne 'origin/main') { throw 'main 必须跟踪 origin/main；停止更新。' }
}

function Get-LockSha($path) {
    if (Test-Path -LiteralPath $path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
    return ''
}

function Test-Workbench($Root) {
    $res = New-Object System.Collections.ArrayList
    $bad = 0
    $verFile = Join-Path $Root 'VERSION'
    if (Test-Path -LiteralPath $verFile) {
        [void]$res.Add('版本号：' + ((Get-Content -LiteralPath $verFile -TotalCount 1 -Encoding UTF8)))
    }
    else { [void]$res.Add('缺失：VERSION'); $bad++ }
    $_checks = @(
        'config\paths.json',
        'skills\xhs-daily\SKILL.md',
        'knowledge\00-首页.md',
        'knowledge\03-运营知识\00-知识目录.md',
        'tools\gpt-writer\gpt_write.py',
        'tools\gpt-writer\kb_search.py',
        'app\adapters\run_writer.py',
        'app\adapters\run_render.py',
        'app\adapters\xhs_daily.py',
        'tools\xiaohongshu-skills\scripts\cli.py',
        'tools\Auto-Redbook-Skills\scripts\render_xhs.py',
        'knowledge\04-案例与训练\03-执行反馈.md',
        'knowledge\05-内容经营\01-系列计划.md',
        'knowledge\05-内容经营\02-系列进度.md',
        'knowledge\05-内容经营\03-历史作品.md',
        'knowledge\06-工作记录\02-草稿台账.md',
        'installer\update.ps1',
        '更新工作台.cmd'
    )
    foreach ($rel in $_checks) {
        if (Test-Path -LiteralPath (Join-Path $Root $rel)) { [void]$res.Add('存在：' + $rel) }
        else { [void]$res.Add('缺失：' + $rel); $bad++ }
    }
    $cfg = $null
    try { $cfg = Read-Config $Root } catch { $cfg = $null }
    if ($cfg) {
        [void]$res.Add('安装根：' + [string]$cfg.root)
        $kb = Join-Path $Root 'knowledge'
        if ($cfg.knowledge_dir) { $kb = [string]$cfg.knowledge_dir }
        if (Test-Path -LiteralPath $kb) { [void]$res.Add('知识库路径可用：' + $kb) }
        else { [void]$res.Add('知识库路径不可用：' + $kb); $bad++ }
    }
    else { [void]$res.Add('paths.json 缺失或无法解析'); $bad++ }
    if ($cfg) {
        Set-ProjectEnv $Root
        $xhsPy = Join-Path $Root 'tools\xiaohongshu-skills\.venv\Scripts\python.exe'
        $renderPy = Join-Path $Root 'tools\Auto-Redbook-Skills\.venv\Scripts\python.exe'
        if ($cfg.xhs_python) { $xhsPy = [string]$cfg.xhs_python }
        if ($cfg.render_python) { $renderPy = [string]$cfg.render_python }
        foreach ($check in @(
            @{ Py = $xhsPy; Code = 'import websockets, requests, python_socks'; Name = '小红书独立环境' },
            @{ Py = $renderPy; Code = 'import markdown, yaml; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()'; Name = '渲染环境与 Chromium 离线启动' }
        )) {
            if ((Test-Path -LiteralPath $check.Py) -and (Test-PyImport $check.Py $check.Code)) { [void]$res.Add('通过：' + $check.Name) }
            else { [void]$res.Add('失败：' + $check.Name + '；重新运行安装.cmd 修复'); $bad++ }
        }
        if ($xhsPy -eq $renderPy) { [void]$res.Add('失败：两个虚拟环境不能共用解释器'); $bad++ }
    }
    return [pscustomobject]@{ ok = ($bad -eq 0); bad = $bad; lines = $res }
}

