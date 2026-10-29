@echo off
chcp 936 >nul
setlocal
title XHS 工作台 - 启动助手
set "PKG=%~dp0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PKG%installer\start_bridge.ps1" %*
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo   未启动成功，退出码 %RC%。请按上面的提示处理，或双击「检查环境.cmd」查看详情。
) else (
  echo   Bridge 已启动，请保持那个窗口开启。
)
echo.
pause
exit /b %RC%