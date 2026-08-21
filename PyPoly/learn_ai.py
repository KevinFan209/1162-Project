# -*- coding: utf-8 -*-
"""AI 導師分析 —— learn.html 右側面板的文字產生器。

================================================================
給接手的組員
================================================================
這個檔案是 AI 導師功能的**唯一交接點**。

你只需要改 generate_report() 這一個函式，
不必動 main.py（1600 行，四個人一起改很容易撞 merge），
也不必動 learn.html。路由與前端都已經接好了：

    learn.html  --POST /learn/ai_report-->  main.py
                                              |
                                              v
                              learn_ai.generate_report(ai_context)
                                              |
                                              v
                              回傳的字串 --> #aiMentorReport

main.py 那一端已經包了 try/except 與逾時保護：
你在這裡拋例外或卡住，頁面只會顯示規則式的退路文字，不會整頁掛掉。
所以放心改，改壞了不會害到別人正在測的遊戲流程。

目前 generate_report() 是**規則式**的實作（沒有 AI），
目的是讓頁面現在就能動。你要做的是把它換成呼叫 LLM，
底下 _call_llm() 已經寫好骨架，把註解拆掉、補上 prompt 就能用。

--------------------------------------------------------------
ai_context 的結構（main.py 的 _build_learn_stats 產生，保證有這些鍵）
--------------------------------------------------------------
{
  "username": "112213007",       # str  玩家帳號
  "games_played": 2,             # int  總對局數；0 代表從沒玩過
  "accuracy": 67,                # int  總正確率 %（0~100）
  "total_questions": 6,          # int  總作答題數
  "avg_answer_sec": 6.8,         # float 平均每題用時（秒）

  # 各語法主題的表現，已依作答數由多到少排序
  "dimensions": [
      {"topic": "串列", "accuracy": 75, "total": 4},
      {"topic": "迴圈", "accuracy": 0,  "total": 2}
  ],

  # 最多 3 個。只納入作答數 >= 2 的主題，避免單題誤判
  "strongest": ["串列"],         # 正確率 >= 60% 的，由高到低
  "weakest":   ["迴圈"],         # 正確率 < 100% 的，由低到高

  # 最近答錯的題目，最多 5 題（刻意限制，避免 prompt 過長）
  "recent_wrong": [
      {"topic": "迴圈", "question": "下列何者會印出 0,1,2？",
       "chosen": 2, "correct": 3}
  ]
}

⚠️ 所有清單都可能是空的（新玩家 games_played=0 時全空），
   寫程式時請假設每個清單都可能沒有元素。

--------------------------------------------------------------
回傳值
--------------------------------------------------------------
回傳 str。內容會**直接以 innerHTML 放進頁面**，所以：
  - 可以用 <b> <br> <code> <ul> 這類簡單標籤排版
  - 不要放 <script>，也不要把使用者輸入原樣拼進去
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

# llama.cpp 的位址。組員若在別台機器開發，在 PyPoly/.env 裡覆寫這個值。
# 注意這是**伺服器端**去呼叫，所以遠端玩家透過隧道連進來也不受影響；
# 但如果跑伺服器的那台機器連不到這個位址，就會落到規則式退路。
LLM_URL = os.getenv("LLM_URL", "http://192.168.137.35:8080")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))


# ==============================================================
# 組員要改的就是這裡
# ==============================================================
def generate_report(ai_context: dict) -> str:
    """依學習統計產生給玩家看的分析文字。

    目前是規則式實作。要接 AI 的話，把下面這行的註解拆掉：

        return _call_llm(ai_context)

    建議保留 try/except 讓 LLM 失敗時仍回 _rule_based()，
    這樣即使模型伺服器沒開，頁面也還是有東西可看。
    """
    # return _call_llm(ai_context)
    return _rule_based(ai_context)


# ==============================================================
# LLM 呼叫骨架（尚未啟用）
# ==============================================================
def _call_llm(ai_context: dict) -> str:
    """呼叫 llama.cpp 的 OpenAI 相容介面產生分析。

    ⚠️ 兩個實測踩過的坑，改之前先看：

    1. gemma-4 是**推理模型**，它會把輸出拆成 content 與 reasoning_content
       兩個欄位。只讀 content——reasoning_content 是思考過程，不要顯示給玩家。

    2. max_tokens 要給足。思考過程會吃掉大量額度，
       實測 max_tokens=100 時 content 會回**空字串**，看起來像模型壞了。
       2048 是可用的起點。

    參考實作見 ops/services/llm_client.py（Discord bot 的 /ask 指令），
    那邊是 async + httpx，這裡用 requests 是為了配合 main.py 的同步路由。
    """
    import json

    prompt = (
        "以下是一位學生在 Python 教學大富翁遊戲中的學習統計（JSON）：\n\n"
        + json.dumps(ai_context, ensure_ascii=False, indent=2)
        + "\n\n請用繁體中文寫一段 100 字以內的學習建議。"
    )

    payload = {
        "messages": [
            {"role": "system", "content": "你是 Python 教學助教，語氣鼓勵但具體。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,   # 見上面第 2 點，不要調小
        "temperature": 0.4,
    }

    r = requests.post(f"{LLM_URL}/v1/chat/completions",
                      json=payload, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    # 只取 content，不要 reasoning_content（見上面第 1 點）
    text = (msg.get("content") or "").strip()
    if not text:
        raise ValueError("LLM 回傳空內容（多半是 max_tokens 被推理過程吃光）")
    return text


# ==============================================================
# 規則式退路
#
# 這段的存在不只是「暫時擋著」——它同時是 LLM 掛掉時的安全網，
# 所以就算 AI 接上去了，也建議留著。
# ==============================================================
def _rule_based(ctx: dict) -> str:
    name = ctx.get("username") or "探險者"
    games = ctx.get("games_played") or 0

    if games == 0:
        return (f"嗨 <b>{name}</b>！你還沒有完成過任何一局。<br>"
                "先去大廳開一局，答幾道題之後回來，這裡就會出現你的學習分析。")

    acc = ctx.get("accuracy") or 0
    total = ctx.get("total_questions") or 0
    weakest = ctx.get("weakest") or []
    strongest = ctx.get("strongest") or []
    avg_sec = ctx.get("avg_answer_sec") or 0

    if acc >= 80:
        opening = f"嗨 <b>{name}</b>！{total} 題答對 {acc}%，表現相當穩。"
    elif acc >= 50:
        opening = f"嗨 <b>{name}</b>！{total} 題答對 {acc}%，基礎已經有了，再推一把。"
    else:
        opening = f"嗨 <b>{name}</b>！目前 {total} 題答對 {acc}%，還有不少進步空間，別氣餒。"

    parts = [opening]
    if strongest:
        parts.append(f"你在 <b>{strongest[0]}</b> 上掌握得不錯。")
    if weakest:
        parts.append(f"目前的挑戰是 <b>{weakest[0]}</b>，建議針對這個主題多練幾題。")
    if avg_sec and avg_sec > 15:
        parts.append(f"平均每題花 {avg_sec} 秒，可以再熟悉一下語法來加快判斷。")

    parts.append("繼續保持開合跳，對專注力很有幫助！")
    return "<br>".join(parts)
