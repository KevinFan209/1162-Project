"""AI 導師分析 —— learn.html 右側面板的文字產生器。"""
from __future__ import annotations

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ==============================================================
# 設定區
# ==============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_URL = os.getenv("LLM_URL", "https://api.openai.com")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))


# ==============================================================
# 核心進入點
# ==============================================================
def generate_report(ai_context: dict) -> str:
    """依玩家作答紀錄產生深度客製化的診斷建議。"""
    if (ai_context.get("games_played") or 0) == 0:
        return _rule_based(ai_context)

    try:
        return _call_llm(ai_context)
    except Exception as e:
        print(f"⚠️ [AI 導師] 呼叫外部 API 失敗，啟用退路機制: {e}")
        return _rule_based(ai_context)


# ==============================================================
# 精準題意分析 LLM 實作
# ==============================================================
def _call_llm(ai_context: dict) -> str:
    name = ai_context.get("username", "探險者")
    accuracy = ai_context.get("accuracy", 0)
    strongest = "、".join(ai_context.get("strongest", [])) or "基礎概念"
    weakest = "、".join(ai_context.get("weakest", [])) or "暫無明顯弱項"

    # 1. 深入解析最近錯題，將題目、玩家選擇與正確答案重構成診斷線索
    recent_wrong = ai_context.get("recent_wrong", [])
    wrong_analysis_block = ""
    if recent_wrong:
        details = []
        for i, item in enumerate(recent_wrong[:3], 1):
            topic = item.get("topic", "未分類")
            q_text = item.get("question", "")
            chosen = item.get("chosen", "?")
            correct = item.get("correct", "?")
            details.append(
                f"錯題 {i} [{topic}]：\n"
                f"  - 題目：{q_text}\n"
                f"  - 玩家選了選項 {chosen}，但正解為選項 {correct}"
            )
        wrong_analysis_block = "【玩家具體失分題目與作答】\n" + "\n".join(details)
    else:
        wrong_analysis_block = "【作答表現】全數答對或尚無近期錯題紀錄。"

    # 2. 系統提示詞：要求扮演解題教練，指出盲點核心
    system_prompt = (
        "你是 PyPoly 大富翁的「Python 隨行 AI 導師」，對象是國中小學童。\n"
        "你的目標是給出具體且具啟發性的『錯題盲點分析』，不要講空泛的客套話。\n\n"
        "請依照以下架構給予回饋：\n"
        "1. 肯定亮點：一句話肯定他在強項主題的表現。\n"
        "2. 深度診斷（重點）：直接針對錯題的題目邏輯（例如 index 索引從 0 開始、range() 範圍不包含尾數、縮排規則等），溫和點出『你當時可能是把 X 誤記成 Y 了』，並給予 1 句好記的觀念口訣。\n"
        "3. 冒險勉勵：融入 1 句南投山城大富翁或數位公民的情境激勵。\n\n"
        "輸出規範：\n"
        "- 直接輸出乾淨的 HTML 段落（使用 <b>、<code>、<br> 標籤，不使用 Markdown codeblock）。\n"
        "- 總長度精簡在 130 字以內，口吻親切自然。"
    )

    user_prompt = (
        f"學員帳號：{name}\n"
        f"全體正確率：{accuracy}%\n"
        f"熟練主題：{strongest}\n"
        f"卡關主題：{weakest}\n"
        f"{wrong_analysis_block}\n\n"
        "請針對上述具體作答失誤進行點撥指導："
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 600,
        "temperature": 0.5,
    }

    response = requests.post(
        f"{LLM_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()

    msg = response.json()["choices"][0]["message"]
    text = (msg.get("content") or "").strip()

    # 清除 Markdown 外殼
    if text.startswith("```html"):
        text = text.replace("```html", "", 1)
    if text.startswith("```"):
        text = text.replace("```", "", 1)
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ==============================================================
# 規則式保底機制
# ==============================================================
def _rule_based(ctx: dict) -> str:
    name = ctx.get("username") or "探險者"
    games = ctx.get("games_played") or 0

    if games == 0:
        return (
            f"嗨 <b>{name}</b>！你還沒有完成過任何一局。<br>"
            "先去大廳開一局，答幾道題之後回來，這裡就會出現專屬於你的學習分析。"
        )

    acc = ctx.get("accuracy") or 0
    total = ctx.get("total_questions") or 0
    weakest = ctx.get("weakest") or []
    strongest = ctx.get("strongest") or []
    recent_wrong = ctx.get("recent_wrong") or []

    parts = [f"嗨 <b>{name}</b>！本局作答正確率 <b>{acc}%</b>。"]

    if strongest:
        parts.append(f"你在 <b>{strongest[0]}</b> 概念掌握得非常扎實！")

    if recent_wrong:
        q_topic = recent_wrong[0].get("topic", "語法")
        parts.append(f"剛才在 <b>{q_topic}</b> 題目中有點可惜選錯了，注意題目裡的邊界條件與符號細節。")
    elif weakest:
        parts.append(f"接下來可以多挑戰 <b>{weakest[0]}</b> 相關的格子，把弱項補齊。")

    parts.append("整理好邏輯，下一把繼續開拓南投數位地圖！")
    return "<br>".join(parts)