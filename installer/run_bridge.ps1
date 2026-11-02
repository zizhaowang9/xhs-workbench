# XHS 工作台 · Bridge 服务窗口
# 由「启动助手.cmd」通过 start_bridge.ps1 在本窗口内启动；窗口关闭即服务停止。
# 只使用本安装目录的 Python 与源码，不使用开发机上的任何路径或后台任务。

param([string]$Root = '', [switch]$NoPause)

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'common.ps1')

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
if (-not $cfg) {
    Write-Host "未找到配置：$(Join-Path $Root 'config\paths.json')" -ForegroundColor Red
    Write-Host '请先运行「安装.cmd」。'
    if (-not $NoPause) { Read-Host '按回车关闭窗口' }
    exit 1
}

Set-ProjectEnv $Root | Out-Null

$logDir = $cfg.logs_dir
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("bridge-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '  XHS 工作台 · Bridge 服务' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host "  安装目录：$Root"
Write-Host "  程序：$($cfg.xhs_python)"
Write-Host "  端口：$($cfg.bridge_port)"
Write-Host "  日志：$logFile"
Write-Host ''
Write-Host '  运行期间请保留本窗口，关闭窗口会停止 Bridge。' -ForegroundColor Yellow
Write-Host ''

try { Start-Transcript -Path $logFile -Append -Force | Out-Null } catch { }

$server = Join-Path $cfg.xhs_repo 'scripts\bridge_server.py'
if (-not (Test-Path -LiteralPath $server)) {
    Write-Host "缺少 Bridge 服务文件：$server" -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    if (-not $NoPause) { Read-Host '按回车关闭窗口' }
    exit 1
}

Set-Location -LiteralPath $cfg.xhs_repo
$LASTEXITCODE = $null
& $cfg.xhs_python $server --port $cfg.bridge_port --root $Root

$code = $LASTEXITCODE
if ($null -eq $code) { $code = 1 }
Write-Host ''
Write-Host "Bridge 进程已退出（退出码 $code）。" -ForegroundColor Yellow
Write-Host "日志：$logFile"
try { Stop-Transcript | Out-Null } catch { }
Write-Host ''
if (-not $NoPause) { Read-Host '按回车关闭窗口' }
exit $code

