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

# ── ngrok ──
# 改用 ngrok 而非 cloudflared Quick Tunnel 的原因：
#   Quick Tunnel 每次啟動都拿到隨機網址（https://<隨機字串>.trycloudflare.com），
#   而 Google OAuth 要求「已授權的 JavaScript 來源」必須事先登記——
#   一個每次都變的網址永遠登記不了，所以隧道下的 Google 登入結構上不可能成功。
#   ngrok 免費方案每個帳號可領一個固定網域，登記一次就永久有效。
#
# authtoken 不放這裡：ngrok 有自己的設定檔（Windows 在
# %LOCALAPPDATA% 底下的 ngrok/ngrok.yml），
# 用 `ngrok config add-authtoken <token>` 設定即可，
# 這樣機密不會經過本專案的 .env。
_bundled = OPS_DIR / "bin" / ("ngrok.exe" if os.name == "nt" else "ngrok")
NGROK = str(_bundled) if _bundled.exists() else "ngrok"

# 固定網域。換帳號或換網域時改 ops/.env 的 NGROK_DOMAIN 即可，不必動程式。
# 這不是機密——它就是組員要開的公開網址。
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN", "headless-clutch-mangle.ngrok-free.dev").strip()
TUNNEL_URL = f"https://{NGROK_DOMAIN}"

# ── 記錄檔 ──
LOG_DIR = OPS_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── llama.cpp（/ask 問答用）──
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://192.168.137.35:8080").rstrip("/")
# 留空則自動偵測目前已載入的模型（模型別名很長，寫死容易過時）
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "").strip()


def missing() -> list[str]:
    """回傳缺少的必要設定，供 bot 啟動時給出明確錯誤。"""
    problems = []
    if not DISCORD_TOKEN:
        problems.append("DISCORD_TOKEN 未設定（請複製 ops/.env.example 為 ops/.env 並填入）")
    if not (PYPOLY_DIR / "main.py").exists():
        problems.append(f"找不到 {PYPOLY_DIR / 'main.py'}，請確認 PYPOLY_DIR 設定")
    return problems
