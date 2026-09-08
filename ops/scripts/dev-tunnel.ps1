<#
  PyPoly 遠端測試一鍵啟動

  啟動 uvicorn (main:sio_app) + ngrok 隧道，
  並印出組員可以直接點開的 HTTPS 網址（固定網址，每次都一樣）。
  Ctrl+C 或關閉視窗會一併收掉兩個行程。

  用法： .\ops\scripts\dev-tunnel.ps1
#>

$ErrorActionPreference = 'Stop'

# ---------- 路徑 ----------
$OpsRoot   = Split-Path -Parent $PSScriptRoot   # ops/
$RepoRoot  = Split-Path -Parent $OpsRoot        # 專案根目錄
$PyPolyDir = Join-Path $RepoRoot 'PyPoly'

if (-not (Test-Path (Join-Path $PyPolyDir 'main.py'))) {
    Write-Host "[X] 找不到 $PyPolyDir\main.py，請確認腳本位置正確。" -ForegroundColor Red
    exit 1
}

# ---------- 前置檢查 ----------
# ngrok 優先用 ops\bin 下的獨立執行檔，其次找 PATH
$NgrokExe = Join-Path $OpsRoot 'bin\ngrok.exe'
if (-not (Test-Path $NgrokExe)) {
    $cmd = Get-Command ngrok -ErrorAction SilentlyContinue
    if ($cmd) {
        $NgrokExe = $cmd.Source
    } else {
        Write-Host "[X] 找不到 ngrok。安裝方式：" -ForegroundColor Red
        Write-Host '      winget install ngrok.ngrok' -ForegroundColor Yellow
        Write-Host '   或到 https://ngrok.com/download 下載後放進 .\ops\bin\' -ForegroundColor Yellow
        Write-Host '   安裝後設定一次金鑰： ngrok config add-authtoken <你的 token>' -ForegroundColor Yellow
        exit 1
    }
}

# 固定網域。換帳號時改這裡，或設環境變數 NGROK_DOMAIN。
$NgrokDomain = if ($env:NGROK_DOMAIN) { $env:NGROK_DOMAIN } else { 'headless-clutch-mangle.ngrok-free.dev' }

if (-not (Test-Path (Join-Path $PyPolyDir '.env'))) {
    Write-Host "[!] PyPoly\.env 不存在，SECRET_KEY 會使用程式碼裡的公開預設值。" -ForegroundColor Yellow
    Write-Host "    公開曝露前請先依 .env.example 建立 .env。" -ForegroundColor Yellow
}

if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "[X] port 8000 已被占用，請先關閉既有的伺服器。" -ForegroundColor Red
    exit 1
}

# ---------- 記錄檔 ----------
$LogDir = Join-Path $env:TEMP 'pypoly-ops'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$UviOut = Join-Path $LogDir 'uvicorn.out.log'
$UviErr = Join-Path $LogDir 'uvicorn.err.log'
$CfOut  = Join-Path $LogDir 'ngrok.out.log'
$CfErr  = Join-Path $LogDir 'ngrok.err.log'
Remove-Item $UviOut, $UviErr, $CfOut, $CfErr -ErrorAction SilentlyContinue

$uvicorn = $null
$tunnel  = $null

try {
    # ---------- 1. 啟動遊戲伺服器 ----------
    # 必須在 PyPoly/ 目錄下執行（StaticFiles 與 norm_hand_standards.json 都是相對路徑）
    # 進入點必須是 sio_app，用 main:app 會讓 /socket.io 回 404
    Write-Host "`n[1/2] 啟動 PyPoly 伺服器 ..." -ForegroundColor Cyan
    $uvicorn = Start-Process -FilePath 'python' `
        -ArgumentList '-m', 'uvicorn', 'main:sio_app', '--host', '0.0.0.0', '--port', '8000' `
        -WorkingDirectory $PyPolyDir -PassThru -NoNewWindow `
        -RedirectStandardOutput $UviOut -RedirectStandardError $UviErr

    # 等待 socket.io 握手成功，代表伺服器真的起來了
    $ready = $false
    foreach ($i in 1..40) {
        Start-Sleep -Milliseconds 500
        if ($uvicorn.HasExited) { break }
        try {
            $r = Invoke-WebRequest -Uri 'http://localhost:8000/socket.io/?EIO=4&transport=polling' `
                                   -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
    }

    if (-not $ready) {
        Write-Host "[X] 伺服器啟動失敗，錯誤訊息：" -ForegroundColor Red
        if (Test-Path $UviErr) { Get-Content $UviErr -Tail 20 }
        exit 1
    }
    Write-Host "      伺服器就緒 (PID $($uvicorn.Id))" -ForegroundColor Green

    # ---------- 2. 建立 ngrok 隧道 ----------
    # 網址是固定的，不必再像 Quick Tunnel 那樣從日誌裡撈隨機網址。
    Write-Host "[2/2] 建立 ngrok 隧道 ..." -ForegroundColor Cyan
    $tunnel = Start-Process -FilePath $NgrokExe `
        -ArgumentList 'http', '8000', '--url', $NgrokDomain, '--log', 'stdout' `
        -PassThru -NoNewWindow `
        -RedirectStandardOutput $CfOut -RedirectStandardError $CfErr

    $publicUrl = "https://$NgrokDomain"

    # 確認隧道真的通了（authtoken 沒設、網域被占用都會讓 ngrok 立刻結束）
    $tunnelOk = $false
    foreach ($i in 1..40) {
        Start-Sleep -Milliseconds 500
        if ($tunnel.HasExited) { break }
        try {
            $r = Invoke-WebRequest -Uri "$publicUrl/static/login.html" -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -lt 500) { $tunnelOk = $true; break }
        } catch { }
    }

    if (-not $tunnelOk) {
        Write-Host "[X] 隧道無法連線，ngrok 輸出：" -ForegroundColor Red
        foreach ($f in @($CfErr, $CfOut)) {
            if (Test-Path $f) { Get-Content $f -Tail 20 -ErrorAction SilentlyContinue }
        }
        exit 1
    }

    # ---------- 完成 ----------
    $loginUrl = "$publicUrl/static/login.html"
    Write-Host ""
    Write-Host "===============================================================" -ForegroundColor Green
    Write-Host "  組員請開這個網址（HTTPS，相機才能用）：" -ForegroundColor Green
    Write-Host ""
    Write-Host "    $loginUrl" -ForegroundColor White
    Write-Host ""
    Write-Host "  本機測試： http://localhost:8000/static/login.html" -ForegroundColor DarkGray
    Write-Host "  記錄檔　： $LogDir" -ForegroundColor DarkGray
    Write-Host "===============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  這個網址是固定的，之後每次啟動都一樣。"
    Write-Host "  按 Ctrl+C 停止伺服器與隧道。"
    Write-Host ""

    Set-Clipboard -Value $loginUrl -ErrorAction SilentlyContinue
    Write-Host "  (網址已複製到剪貼簿)" -ForegroundColor DarkGray

    # ---------- 常駐 ----------
    while ($true) {
        Start-Sleep -Seconds 2
        if ($uvicorn.HasExited) { Write-Host "`n[!] 伺服器已結束。" -ForegroundColor Yellow; break }
        if ($tunnel.HasExited)  { Write-Host "`n[!] 隧道已結束。"   -ForegroundColor Yellow; break }
    }
}
finally {
    Write-Host "`n正在停止 ..." -ForegroundColor Cyan
    foreach ($p in @($tunnel, $uvicorn)) {
        if ($p -ne $null -and -not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "已停止。" -ForegroundColor Green
}
