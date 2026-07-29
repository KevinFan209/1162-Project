# -*- coding: utf-8 -*-
"""管理 PyPoly uvicorn 子行程。

安全性設計：啟動指令是寫死在本模組中的固定字串陣列，不接受任何來自 Discord
的輸入，也不經過 shell。呼叫端只能「啟動 / 停止 / 查狀態」這三個動作。
"""
from __future__ import annotations

import asyncio
import subprocess
import sys

import httpx

import config

# 固定指令：必須在 PyPoly/ 目錄下執行（StaticFiles 與手勢標準檔皆為相對路徑），
# 且進入點必須是 sio_app（用 main:app 會讓 /socket.io 回 404）
_CMD = [
    sys.executable, "-m", "uvicorn", "main:sio_app",
    "--host", "0.0.0.0", "--port", str(config.SERVER_PORT),
]

_OUT_LOG = config.LOG_DIR / "uvicorn.out.log"
_ERR_LOG = config.LOG_DIR / "uvicorn.err.log"

_proc: subprocess.Popen | None = None
_logs: list = []   # 子行程的記錄檔控制代碼，stop() 時要一併關閉


async def is_up(timeout: float = 3.0) -> bool:
    """伺服器是否可服務（不論是誰啟動的）。以 socket.io 握手為準。"""
    url = f"{config.SERVER_LOCAL_URL}/socket.io/?EIO=4&transport=polling"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return (await client.get(url)).status_code == 200
    except Exception:
        return False


def owned() -> bool:
    """這個伺服器是否由本 bot 啟動（決定 /stop 能不能收掉它）。"""
    return _proc is not None and _proc.poll() is None


async def start(ready_timeout: float = 30.0) -> tuple[bool, str]:
    """啟動伺服器。回傳 (成功, 訊息)。"""
    global _proc, _logs

    if await is_up():
        who = "由 bot 啟動" if owned() else "由其他方式啟動（例如 dev-tunnel.ps1）"
        return True, f"伺服器已在執行中（{who}）"

    _OUT_LOG.write_text("", encoding="utf-8")
    _ERR_LOG.write_text("", encoding="utf-8")

    # 記錄檔控制代碼要留著，否則每次 start 都會洩漏一組檔案描述子
    _logs = [_OUT_LOG.open("a", encoding="utf-8"), _ERR_LOG.open("a", encoding="utf-8")]
    _proc = subprocess.Popen(
        _CMD,
        cwd=str(config.PYPOLY_DIR),
        stdout=_logs[0],
        stderr=_logs[1],
    )

    deadline = asyncio.get_event_loop().time() + ready_timeout
    while asyncio.get_event_loop().time() < deadline:
        if _proc.poll() is not None:
            return False, f"伺服器行程異常結束：\n```\n{_tail(_ERR_LOG)}\n```"
        if await is_up():
            return True, "伺服器已啟動"
        await asyncio.sleep(0.5)

    stop()
    return False, f"伺服器啟動逾時（{ready_timeout:.0f} 秒）：\n```\n{_tail(_ERR_LOG)}\n```"


def stop() -> tuple[bool, str]:
    """停止由本 bot 啟動的伺服器。"""
    global _proc

    if _proc is None or _proc.poll() is not None:
        _proc = None
        _close_logs()
        return False, "伺服器不是由 bot 啟動的，請在原本啟動它的視窗按 Ctrl+C"

    _proc.terminate()
    try:
        _proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _proc.kill()
    _proc = None
    _close_logs()
    return True, "伺服器已停止"


def _close_logs():
    global _logs
    for f in _logs:
        try:
            f.close()
        except Exception:
            pass
    _logs = []


async def online_players() -> int | None:
    """目前在線人數；查不到時回 None（不讓 /status 因此失敗）。"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{config.SERVER_LOCAL_URL}/rooms/public")
            if r.status_code != 200:
                return None
            return sum(len(room.get("players", [])) for room in r.json())
    except Exception:
        return None


def _tail(path, lines: int = 15) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        return "\n".join(content[-lines:]) or "(無輸出)"
    except Exception:
        return "(讀不到記錄檔)"
