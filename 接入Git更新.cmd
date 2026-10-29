@echo off
setlocal
set "PS1=%~dp0installer\join.ps1"
if not exist "%PS1%" set "PS1=%~dp0team-repo\installer\join.ps1"
if not exist "%PS1%" (
  echo [ERROR] join.ps1 not found.
  echo Keep this file next to the "installer" folder of the workbench package.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
echo.
pause
