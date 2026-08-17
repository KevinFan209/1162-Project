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

:: 確認 fastapi / uvicorn 已安裝（系統 Python 已內建，一般不需重裝）
python -c "import fastapi, uvicorn" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  正在安裝必要套件...
    python -m pip install -q fastapi "uvicorn[standard]"
)

echo.
echo  正在啟動角色自定義展示伺服器...
echo.
python "%~dp0demo_server.py"
pause
