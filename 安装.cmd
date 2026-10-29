@echo off
chcp 936 >nul
setlocal
title XHS 工作台 - 安装
set "PKG=%~dp0"
echo.
echo   正在启动安装程序，请稍候...
echo.
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PKG%installer\install.ps1" %*
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo   安装未完成，退出码 %RC%。请把上面的提示或 logs 目录里的日志发给提供者。
) else (
  echo   安装流程结束。建议接着双击「检查环境.cmd」确认状态。
)
echo.
pause
exit /b %RC%