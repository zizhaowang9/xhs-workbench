@echo off
setlocal
set "PS1=%~dp0installer\update.ps1"
if exist "%~dp0team-repo\installer\update.ps1" set "PS1=%~dp0team-repo\installer\update.ps1"
if not exist "%PS1%" (
  echo [ERROR] update.ps1 not found.
  echo Keep this file in the workbench install folder next to the "installer" folder.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Root "%~dp0." %*
echo.
pause
