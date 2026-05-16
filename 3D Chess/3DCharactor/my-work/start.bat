@echo off
chcp 65001 >nul
title PyPoly 啟動工具
echo.
echo  正在啟動 PyPoly 伺服器...
echo.
"%~dp0venv\Scripts\python.exe" "%~dp0start_server.py"
pause
