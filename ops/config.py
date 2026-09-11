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

# ── 多分支工作區 ──
# 讓一個 bot 就能服務不同分支：/start <分支> 會把 uvicorn 的工作目錄
# 換成該分支的 worktree，不必再另開一個資料夾手動 git switch。
#
# 預期的結構（每個分支一個資料夾，名稱就是分支名）：
#     Project\
#       ├── main\        ← 主 worktree，bot.py 從這裡跑
#       ├── Fan-map\     ← git worktree
#       └── …
#
# 絕對路徑因人而異，寫死在版控裡對組員沒意義，所以由 ops/.env 的
# PROJECT_ROOT 決定；未設定時推算為「bot 所在倉庫的上一層」，
# 照上面的結構擺放時會自動正確。
_root = os.getenv("PROJECT_ROOT", "").strip()
PROJECT_ROOT = Path(_root).resolve() if _root else REPO_ROOT.parent

# bot 自己所在的 worktree。它服務哪個分支由子行程的 cwd 決定，與這個
# 路徑無關——只有要更新 bot 本身的程式碼時才需要動到它。
CONTROL_WORKTREE = REPO_ROOT

# 未指定分支時的預設。同時只能服務一個分支：ngrok 免費方案只允許
# 一條隧道，8000 埠也只有一個，所以切分支＝停掉舊的再起新的。
DEFAULT_BRANCH = os.getenv("DEFAULT_BRANCH", "main").strip() or "main"

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
