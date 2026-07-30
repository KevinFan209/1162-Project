# -*- coding: utf-8 -*-
"""管理 cloudflared Quick Tunnel 子行程。

與 server_manager 同樣的安全性設計：指令固定寫死，不接受外部輸入。
Quick Tunnel 每次啟動都會拿到不同網址，因此由本模組負責把網址解析出來，
再由 bot 貼回 Discord —— 這正好補掉 Quick Tunnel 唯一的缺點。
"""
from __future__ import annotations

import asyncio
import re
import subprocess

import httpx

import config

_CMD = [config.CLOUDFLARED, "tunnel", "--url", config.SERVER_LOCAL_URL]

_OUT_LOG = config.LOG_DIR / "cloudflared.out.log"
_ERR_LOG = config.LOG_DIR / "cloudflared.err.log"

_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

_proc: subprocess.Popen | None = None
_url: str | None = None
_logs: list = []       # 子行程的記錄檔控制代碼，stop() 時要一併關閉
_verified: bool = False  # 上次啟動時是否真的驗證到網址可連線


def url_verified() -> bool:
    """上次 start() 是否成功驗證網址可連線。

    False 代表網址已產生但本機連不上——最常見的原因是新網域的 DNS 還在傳播
    （此時本機可能只拿到 AAAA 記錄，若本機 IPv6 不通就會連不上），
    但對 DNS 已更新的組員而言網址往往是好的。呼叫端應據此提示使用者，
    而不是把網址當成無效。
    """
    return _verified


def current_url() -> str | None:
    """目前的隧道網址；隧道已結束則回 None。"""
    if _proc is None or _proc.poll() is not None:
        return None
    return _url


def is_up() -> bool:
    return _proc is not None and _proc.poll() is None


async def start(url_timeout: float = 40.0) -> tuple[bool, str]:
    """啟動隧道並解析出公開網址。回傳 (成功, 網址或錯誤訊息)。"""
    global _proc, _url, _logs, _verified

    if is_up() and _url:
        return True, _url

    _verified = False

    _OUT_LOG.write_text("", encoding="utf-8")
    _ERR_LOG.write_text("", encoding="utf-8")

    try:
        # 記錄檔控制代碼要留著，否則每次 start 都會洩漏一組檔案描述子
        _logs = [_OUT_LOG.open("a", encoding="utf-8"), _ERR_LOG.open("a", encoding="utf-8")]
        _proc = subprocess.Popen(_CMD, stdout=_logs[0], stderr=_logs[1])
    except FileNotFoundError:
        return False, ("找不到 cloudflared。請下載獨立執行檔到 ops/bin/：\n"
                       "https://github.com/cloudflare/cloudflared/releases/latest/"
                       "download/cloudflared-windows-amd64.exe")

    deadline = asyncio.get_event_loop().time() + url_timeout
    while asyncio.get_event_loop().time() < deadline:
        if _proc.poll() is not None:
            return False, f"cloudflared 異常結束：\n```\n{_tail(_ERR_LOG)}\n```"
        # cloudflared 把網址印在 stderr，兩個檔案都掃
        text = _read(_ERR_LOG) + _read(_OUT_LOG)
        m = _URL_RE.search(text)
        if m:
            _url = m.group(0)
            # 新網域的 DNS 傳播要時間（cloudflared 自己也提示
            # "it may take some time to be reachable"），等到真的連得上再回傳。
            # 驗證結果記在 _verified，呼叫端要據此提示使用者——
            # 先前這裡的回傳值被忽略，導致明知連不上卻照樣貼出網址。
            _verified = await _wait_reachable(_url)
            return True, _url
        await asyncio.sleep(0.5)

    stop()
    return False, f"取不到隧道網址（逾時 {url_timeout:.0f} 秒）：\n```\n{_tail(_ERR_LOG)}\n```"


def stop() -> tuple[bool, str]:
    global _proc, _url, _logs

    if _proc is None or _proc.poll() is not None:
        _proc, _url = None, None
        _close_logs()
        return False, "隧道未在執行中"

    _proc.terminate()
    try:
        _proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _proc.kill()
    _proc, _url = None, None
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


async def _wait_reachable(url: str, timeout: float = 90.0) -> bool:
    """等待新網域可解析且能連通。回傳是否驗證成功（逾時回 False，由呼叫端決定如何提示）。

    90 秒是實測後放寬的：30 秒對 quick tunnel 的 DNS 傳播偏短，
    曾出現逾時後 bot 貼出當下確實連不上的網址。
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
    return "\n".join(content[-lines:]) or "(無輸出)"
