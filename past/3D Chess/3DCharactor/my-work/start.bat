@echo off
chcp 65001 >nul
title BeeRich 啟動工具

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  錯誤：找不到 Python，請先安裝 Python 3.x
    pause
    exit /b 1
)

echo.
echo  正在啟動 BeeRich 伺服器...
echo.
python "%~dp0start_server.py"
pause
