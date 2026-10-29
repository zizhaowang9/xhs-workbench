@echo off
chcp 936 >nul
setlocal
title XHS 工作台 - 检查环境
set "PKG=%~dp0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PKG%installer\check_env.ps1" %*
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%