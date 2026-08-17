@echo off
chcp 65001 >nul
title 角色自定義展示

:: 確認 Python 是否安裝
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  錯誤：找不到 Python，請先安裝 Python 3.x
    echo  下載網址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: 第一次執行時建立虛擬環境
if not exist "%~dp0demo_venv\Scripts\python.exe" (
    echo.
    echo  第一次執行，正在建立虛擬環境...
    python -m venv "%~dp0demo_venv"
    if %errorlevel% neq 0 (
        echo  錯誤：虛擬環境建立失敗
        pause
        exit /b 1
    )
)

:: 安裝 / 確認套件（已安裝的話會直接跳過）
echo.
echo  正在確認套件...
"%~dp0demo_venv\Scripts\pip" install -q -r "%~dp0demo_requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo  錯誤：套件安裝失敗，請確認網路連線
    pause
    exit /b 1
)

echo.
echo  正在啟動角色自定義展示伺服器...
echo.
"%~dp0demo_venv\Scripts\python.exe" "%~dp0demo_server.py"
pause
