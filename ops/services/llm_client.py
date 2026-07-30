# -*- coding: utf-8 -*-
"""llama.cpp（OpenAI 相容介面）唯讀客戶端。

⚠️ 設計約束（階段三的核心原則）：
    本模組**只做文字進、文字出**。請求裡不含 tools / functions 欄位，
    也不提供任何可以觸發副作用的能力。LLM 永遠不能啟動伺服器、
    不能執行指令、不能讀寫專案檔案。
    對應地，cogs/ask_cog.py 不得 import server_manager / tunnel_manager。
"""
from __future__ import annotations

import httpx

import config
from services import project_context

# 對話系統提示：給模型足夠的專案背景，讓它回答「這個 API 在哪」這類問題時有依據。
# 刻意保持精簡且靜態——不夾帶程式碼內容，避免脈絡爆掉也避免洩漏機敏設定。
SYSTEM_PROMPT = """你是 PyPoly 專案的技術問答助理，服務對象是這個專案的四位學生開發者。

專案概要：
- PyPoly 是一款「程式教學互動大富翁」，雙人連線，用攝影機手勢與體感操作。
- 後端：FastAPI + python-socketio，ASGI 進入點是 sio_app（用 main:app 會讓 /socket.io 回 404）。
  必須在 PyPoly/ 目錄下啟動，因為 StaticFiles 與手勢標準檔都是相對路徑。
- 前端：原生 HTML/JS + Three.js r128 + GSAP，全部在 static/ 下；game.html 是遊戲引擎主體。
- 影像辨識：MediaPipe 跑在瀏覽器，只把 landmarks 傳給後端，由 game_start.py 的
  GestureDetector / PoseDetector / BirdDetector 判定。
- 資料庫：MySQL(MariaDB) pypoly_db，資料表 users / questions / scenarios /
  game_records / game_answer_logs。
- 房間狀態存在伺服器記憶體的 active_rooms，局內狀態（金錢、土地、道具）存在前端 localStorage。
- ops/ 放營運工具：Discord bot 與 Cloudflare 隧道腳本，與遊戲程式分離。

你會拿到一份自動產生的「程式碼地圖」，內含檔案清單、REST 路由、Socket.IO 事件、
資料表欄位、前端函式名與真實行號，以及 changeLog 的最近條目。
地圖**不含完整原始碼**，只有結構索引。

以下「已知問題」清單是寫死在程式裡的，可能已經過期；
若程式碼地圖的 changeLog 段落與這裡衝突，**一律以 changeLog 為準**。

目前已知但尚未修復的問題：
1. game.html 定義了 startSyncLoop() 但從未呼叫，導致遊戲中全程無心跳，
   約 60 秒後後端會誤判玩家離線，重複登入防護也因此失效。
2. 完全沒有 socket 斷線處理，玩家關分頁後仍留在房間；決定先後手階段對手斷線會導致遊戲死鎖。
3. 殭屍房間會永久累積，active_rooms 沒有逾時回收。
4. 回合結束判定綁「加入順序」而非實際行動順序，可能少給某位玩家一回合。
5. 結算的 jump_count 前端沒送，報表永遠是 0。
6. modal.html 的「25 回合」「30 回合」選項 value 都誤植為 20。
7. /rooms/create 沒把房號正規化為大寫，其他端點都有。

回答規則：
- 用繁體中文，簡潔直接，不要冗長開場。
- 被問到「某功能在哪」時，用程式碼地圖回答，並附上檔名與行號。
- 地圖裡沒有的實作細節（某一行到底怎麼寫的、某函式內部邏輯）你看不到，
  明說看不到並指出應該去看哪個檔案的哪一行，**不要編造程式碼內容或行號**。
- 不確定的事明說不確定。
- 你只能回答問題與解釋概念，沒有能力執行任何操作。若使用者要你開伺服器或跑指令，
  請告訴他改用 /start、/restart、/stop、/status、/url 這些指令。
"""

_model_cache: str | None = None


async def _resolve_model(client: httpx.AsyncClient) -> str:
    """取得目前已載入的模型 id。設定檔有指定就用它，否則自動偵測並快取。"""
    global _model_cache
    if config.LLAMA_MODEL:
        return config.LLAMA_MODEL
    if _model_cache:
        return _model_cache

    r = await client.get(f"{config.LLAMA_BASE_URL}/v1/models")
    r.raise_for_status()
    entries = r.json().get("data", [])
    loaded = [m["id"] for m in entries
              if (m.get("status") or {}).get("value") == "loaded"]
    _model_cache = (loaded or [m["id"] for m in entries])[0]
    return _model_cache


async def health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            return (await client.get(f"{config.LLAMA_BASE_URL}/health")).status_code == 200
    except Exception:
        return False


async def ask(question: str, timeout: float = 180.0) -> tuple[bool, str]:
    """送出問題，回傳 (成功, 答案或錯誤訊息)。

    注意 payload 刻意不含 tools / functions —— 模型沒有任何工具可用。
    """
    # 程式碼地圖與系統提示都放在同一則 system 訊息，且順序固定，
    # 讓每次請求的前綴保持一致以命中 llama.cpp 的 prompt prefix 快取。
    # 地圖產生失敗不該讓 /ask 整個掛掉，退回只用系統提示。
    try:
        system = SYSTEM_PROMPT + "\n\n" + project_context.build()
    except Exception:
        system = SYSTEM_PROMPT

    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        # 這是推理型模型（gemma-4），思考過程會吃掉大量 token，
        # 額度給太小會導致 content 回空字串（實測 max_tokens=100 時就是如此）
        "max_tokens": 2048,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            payload["model"] = await _resolve_model(client)
            r = await client.post(
                f"{config.LLAMA_BASE_URL}/v1/chat/completions", json=payload)
            if r.status_code != 200:
                return False, f"llama.cpp 回應 HTTP {r.status_code}：{r.text[:300]}"
            data = r.json()
    except httpx.TimeoutException:
        return False, f"llama.cpp 回應逾時（{timeout:.0f} 秒），可能問題太複雜或模型正在載入。"
    except Exception as e:
        return False, (f"連不上 llama.cpp（{config.LLAMA_BASE_URL}）：{type(e).__name__}\n"
                       "請確認那台機器與服務都還開著。")

    choice = (data.get("choices") or [{}])[0]
    # 只取 content。reasoning_content 是模型的英文思考草稿，不該貼給使用者。
    answer = (choice.get("message") or {}).get("content", "").strip()

    if not answer:
        return False, ("模型只產出了思考過程就用完了 token 額度，沒有給出結論。"
                       "請把問題問得更具體一點再試一次。")
    return True, answer
