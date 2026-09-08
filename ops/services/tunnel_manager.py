# -*- coding: utf-8 -*-
"""管理 ngrok 隧道子行程。

與 server_manager 同樣的安全性設計：指令固定寫死，不接受外部輸入。

為什麼從 cloudflared Quick Tunnel 換成 ngrok：
    Quick Tunnel 每次啟動都拿到隨機網址，而 Google OAuth 要求
    「已授權的 JavaScript 來源」必須事先登記在 Google Cloud Console——
    一個每次都變的網址永遠登記不了，所以隧道下的 Google 登入
    在結構上就不可能成功，不是設定問題。
    ngrok 免費方案每個帳號可領一個固定網域，登記一次就永久有效。

換成固定網址之後，本模組比先前簡單很多：
    網址是常數（config.TUNNEL_URL），不必再從子行程的日誌裡用
    正規表示式把它撈出來，也不必等 DNS 傳播——網域早就存在了。
    保留的只有「確認隧道真的通了」這一步。
"""
from __future__ import annotations

import asyncio
import subprocess

import httpx

import config

# ngrok 3.x 語法：ngrok http <port> --url <domain>
_CMD = [
    config.NGROK, "http", str(config.SERVER_PORT),
    "--url", config.NGROK_DOMAIN,
    "--log", "stdout",
]

_OUT_LOG = config.LOG_DIR / "ngrok.out.log"
_ERR_LOG = config.LOG_DIR / "ngrok.err.log"

_proc: subprocess.Popen | None = None
_logs: list = []         # 子行程的記錄檔控制代碼，stop() 時要一併關閉
_verified: bool = False  # 上次啟動時是否真的驗證到網址可連線


def url_verified() -> bool:
    """上次 start() 是否成功驗證網址可連線。

    False 代表 ngrok 行程還活著但本機連不上——通常是 PyPoly 伺服器
    根本沒開（隧道通了但後面沒有東西）。呼叫端應據此提示使用者。
    """
    return _verified


def current_url() -> str | None:
    """目前的隧道網址；隧道未在執行則回 None。

    網址是固定的，所以這裡只需要判斷行程是否還活著。
    """
    if _proc is None or _proc.poll() is not None:
        return None
    return config.TUNNEL_URL


def is_up() -> bool:
    return _proc is not None and _proc.poll() is None


async def start(url_timeout: float = 40.0) -> tuple[bool, str]:
    """啟動隧道。回傳 (成功, 網址或錯誤訊息)。"""
    global _proc, _logs, _verified

    if is_up():
        return True, config.TUNNEL_URL

    _verified = False

    _OUT_LOG.write_text("", encoding="utf-8")
    _ERR_LOG.write_text("", encoding="utf-8")

    try:
        # 記錄檔控制代碼要留著，否則每次 start 都會洩漏一組檔案描述子
        _logs = [_OUT_LOG.open("a", encoding="utf-8"), _ERR_LOG.open("a", encoding="utf-8")]
        _proc = subprocess.Popen(_CMD, stdout=_logs[0], stderr=_logs[1])
    except FileNotFoundError:
        return False, ("找不到 ngrok。請安裝後設定 authtoken：\n"
                       "1. 到 https://ngrok.com/download 下載，或 `winget install ngrok.ngrok`\n"
                       "2. `ngrok config add-authtoken <你的 token>`")

    # 給行程一點時間失敗（authtoken 沒設、網域被占用都會立刻結束）
    await asyncio.sleep(2)
    if _proc.poll() is not None:
        _close_logs()
        _proc = None
        return False, f"ngrok 異常結束：\n```\n{_tail(_ERR_LOG) or _tail(_OUT_LOG)}\n```"

    _verified = await _wait_reachable(config.TUNNEL_URL, timeout=url_timeout)
    return True, config.TUNNEL_URL


def stop() -> tuple[bool, str]:
    global _proc, _logs

    if _proc is None or _proc.poll() is not None:
        _proc = None
        _close_logs()
        return False, "隧道未在執行中"

    _proc.terminate()
    try:
        _proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _proc.kill()
    _proc = None
    _close_logs()
    return True, "隧道已關閉"


def _close_logs():
    global _logs
    for f in _logs:
        try:
            f.close()
        except Exception:
            pass
    _logs = []


async def _wait_reachable(url: str, timeout: float = 40.0) -> bool:
    """確認經由隧道真的連得到 PyPoly。回傳是否驗證成功。

    固定網域不需要等 DNS 傳播（先前 cloudflared 那版要等 90 秒就是為此），
    所以這裡只是確認「隧道通了而且後面的伺服器有回應」。
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(f"{url}/static/login.html")
                if r.status_code < 500:
                    return True
        except Exception:
            pass
        await asyncio.sleep(2)
    return False


def _read(path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _tail(path, lines: int = 15) -> str:
    content = _read(path).strip().splitlines()
    return "\n".join(content[-lines:]) or ""
