@echo off
chcp 65001 >nul
title PyPoly Docker 啟動工具
echo.
echo  正在啟動 PyPoly (Docker 模式)...
echo  公開網址請到 http://localhost:4040 查看
echo.
docker compose up --build
pause
