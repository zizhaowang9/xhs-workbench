param([switch]$Install, [string]$Root = '')
$ErrorActionPreference = 'Stop'
$Package = Split-Path -Parent $PSScriptRoot

# Parse every shipped PowerShell script using the current Windows parser.
foreach ($file in (Get-ChildItem -LiteralPath $Package -Recurse -Filter '*.ps1' -File)) {
    $tokens = $null; $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw ('PowerShell syntax failed: ' + $file.FullName + ': ' + ($errors -join '; ')) }
}
if (-not $Install) { Write-Host 'PowerShell syntax passed; use -Install for the fresh-directory network install and local render checks.'; exit 0 }
if (-not $Root) { $Root = Join-Path $env:TEMP ('XHS 中文 空格 ' + [Guid]::NewGuid().ToString('N')) }
if (Test-Path -LiteralPath $Root) { throw 'Smoke root must not already exist.' }
if ($env:GITHUB_ENV) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::AppendAllText($env:GITHUB_ENV, ('XHS_SMOKE_ROOT=' + $Root + [Environment]::NewLine), $utf8)
}

# This is a fresh install DIRECTORY. CI host may already have Python/Git.
# Force uv to provision/use managed Python; do not remove host software.
$env:UV_PYTHON_PREFERENCE = 'only-managed'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Package 'installer\install.ps1') -Root $Root
if ($LASTEXITCODE -ne 0) { throw 'Fresh install failed.' }
. (Join-Path $Root 'installer\common.ps1')
. (Join-Path $Root 'installer\lib.ps1')
Set-ProjectEnv $Root
$cfg = Read-Config $Root
$installState = Get-Content -LiteralPath (Join-Path $Root 'config\install-state.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$managedRoot = [IO.Path]::GetFullPath([string]$cfg.python_install_dir).TrimEnd('\') + '\'
if (-not ([IO.Path]::GetFullPath([string]$installState.python)).StartsWith($managedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Installer did not select project-managed Python.' }
$t = Test-Workbench $Root
if (-not $t.ok) { throw ($t.lines -join '; ') }
if (Test-ModelConfig $Root) { throw 'Blank model unexpectedly reported ready.' }

# Actual localhost Bridge lifecycle through the installed Windows runner.
# This creates no browser/account connection and uses only an available test port.
& $cfg.xhs_python (Join-Path $Package 'tests\bridge_smoke.py')
if ($LASTEXITCODE -ne 0) { throw 'Bridge localhost protocol checks failed.' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Package 'tests\bridge_windows.ps1') -Root $Root
if ($LASTEXITCODE -ne 0) { throw 'Windows Bridge runner and ownership checks failed.' }

# Model readiness is a local structural check. All keys below are dummy fixtures.
$modelPath = Join-Path $Root 'config\gpt.local.json'
$fixtures = @(
    @{ provider = 'fixture'; protocol = 'responses'; base_url = 'https://example.invalid'; model = ''; api_key = 'dummy-offline'; Expected = $false },
    @{ provider = 'fixture'; protocol = 'invalid'; base_url = 'https://example.invalid'; model = 'fixture'; api_key = 'dummy-offline'; Expected = $false },
    @{ provider = 'fixture'; protocol = 'responses'; base_url = 'https://example.invalid'; model = 'fixture'; api_key = 'dummy-offline'; Expected = $true }
)
foreach ($fixture in $fixtures) {
    Save-ConfigUtf8 $modelPath $fixture
    if ((Test-ModelConfig $Root) -ne $fixture.Expected) { throw 'Model readiness fixture failed.' }
}
[IO.File]::WriteAllText($modelPath, '{invalid json')
if (Test-ModelConfig $Root) { throw 'Invalid JSON unexpectedly reported ready.' }
Remove-Item -LiteralPath $modelPath

# Run the small offline fixture suite with PROJECT Python, never a model API.
& $cfg.xhs_python (Join-Path $Package 'tests\offline_smoke.py')
if ($LASTEXITCODE -ne 0) { throw 'Offline fixture suite failed.' }
$run = Join-Path $Root 'runs\smoke-mock'
$task = Join-Path $Root 'tools\gpt-writer\examples\task-praise.json'
& $cfg.xhs_python (Join-Path $Root 'app\adapters\run_writer.py') --task $task --run-dir $run --mock
if ($LASTEXITCODE -ne 0) { throw 'Installed writer mock failed.' }
& $cfg.render_python (Join-Path $Root 'app\adapters\run_render.py') --cards (Join-Path $run 'cards.md') --output-dir (Join-Path $run 'images') --theme professional --mode auto-fit --width 1080 --height 1440 --dpr 1
if ($LASTEXITCODE -ne 0) { throw 'Installed local render failed.' }
& $cfg.xhs_python (Join-Path $Package 'tests\verify_render.py') (Join-Path $run 'images')
if ($LASTEXITCODE -ne 0) { throw 'Rendered six-image check failed.' }
Write-Host 'PASS: fresh install directory, project environments, real localhost Bridge and Windows runner, blank model, offline materials, mock writer, Chromium and six local rendered PNGs.'
Write-Host 'Verified: project-managed Python provision/use (UV_PYTHON_PREFERENCE=only-managed). Host is not a completely clean Windows image. Not tested: live model calls, Chrome extension, XHS login, upload, saving or reopening site drafts.'

