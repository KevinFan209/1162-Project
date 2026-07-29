# -*- coding: utf-8 -*-
"""集中管理 ops bot 的設定，避免 os.getenv 散落各處。"""
import os
from pathlib import Path

from dotenv import load_dotenv

OPS_DIR = Path(__file__).resolve().parent
REPO_ROOT = OPS_DIR.parent

load_dotenv(OPS_DIR / ".env")

# ── Discord ──
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
_guild = os.getenv("GUILD_ID", "").strip()
GUILD_ID = int(_guild) if _guild.isdigit() else None

# ── PyPoly 伺服器 ──
_pypoly = os.getenv("PYPOLY_DIR", "").strip()
PYPOLY_DIR = Path(_pypoly) if _pypoly else (REPO_ROOT / "PyPoly")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000") or 8000)
SERVER_LOCAL_URL = f"http://127.0.0.1:{SERVER_PORT}"

# ── cloudflared ──
# 優先用 ops/bin 下的獨立執行檔，找不到才退回 PATH
_bundled = OPS_DIR / "bin" / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
CLOUDFLARED = str(_bundled) if _bundled.exists() else "cloudflared"

# ── 記錄檔 ──
LOG_DIR = OPS_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── 階段三才會用到 ──
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://192.168.137.35:8080").rstrip("/")


def missing() -> list[str]:
    """回傳缺少的必要設定，供 bot 啟動時給出明確錯誤。"""
    problems = []
    if not DISCORD_TOKEN:
        problems.append("DISCORD_TOKEN 未設定（請複製 ops/.env.example 為 ops/.env 並填入）")
    if not (PYPOLY_DIR / "main.py").exists():
        problems.append(f"找不到 {PYPOLY_DIR / 'main.py'}，請確認 PYPOLY_DIR 設定")
    return problems
