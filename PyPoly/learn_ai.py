"""AI 導師分析 —— learn.html 右側面板的文字產生器。"""
from __future__ import annotations

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ==============================================================
# 設定區（API 金鑰填在此處，或寫在 PyPoly/.env 中）
# ==============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_URL = os.getenv("LLM_URL", "https://api.openai.com")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))


# ==============================================================
# 核心進入點
# ==============================================================
def generate_report(ai_context: dict) -> str:
    """依學習統計產生給玩家看的分析文字。

    優先呼叫外部 LLM，若 API 呼叫失敗或逾時，自動無縫切換至規則式文字。
    """
    # 從未完成過對局的玩家直接走引導文字，避免不必要的 API 消耗
    if (ai_context.get("games_played") or 0) == 0:
        return _rule_based(ai_context)

    try:
        return _call_llm(ai_context)
    except Exception as e:
        print(f"⚠️ [AI 導師] 呼叫外部 API 失敗，啟用退路機制: {e}")
        return _rule_based(ai_context)


# ==============================================================
# LLM 呼叫實作
# ==============================================================
def _call_llm(ai_context: dict) -> str:
    """呼叫 OpenAI 相容端點生成個人化學習回饋。"""
    name = ai_context.get("username", "探險者")
    accuracy = ai_context.get("accuracy", 0)
    strongest = "、".join(ai_context.get("strongest", [])) or "暫無特別突出項目"
    weakest = "、".join(ai_context.get("weakest", [])) or "暫無明顯弱項"

    # 提取最近答錯的具體題目資訊
    recent_wrong = ai_context.get("recent_wrong", [])
    wrong_detail = ""
    if recent_wrong:
        items = [
            f"{i+1}. [{item.get('topic')}] {item.get('question')}"
            for i, item in enumerate(recent_wrong[:3])
        ]
        wrong_detail = "\n最近答錯的題目：\n" + "\n".join(items)

    system_prompt = (
        "你是 PyPoly 大富翁的「AI 導師」，面向國中小學童。\n"
        "語氣原則：極度溫暖、具啟發性、幽默。\n"
        "分析指令：\n"
        "1. 稱讚他在強項主題上的運算思維。\n"
        "2. 針對他最近答錯的主題或具體題目，給予實用的 Python 觀念指引。\n"
        "3. 巧妙融合南投山城、大富翁、數位公民等意象進行鼓勵。\n"
        "4. 請直接輸出 HTML 片段（使用 <b>、<br>、<code> 標籤，絕對不要輸出 ```html 程式碼區塊外殼）。\n"
        "5. 扣除 HTML 標籤後，字數控制在 120 字以內。"
    )

    user_prompt = (
        f"學員名稱：{name}\n"
        f"整體答題正確率：{accuracy}%\n"
        f"掌握較佳主題：{strongest}\n"
        f"待加強主題：{weakest}\n"
        f"{wrong_detail}\n\n"
        "請根據上述實際作答情況，給予一段專屬的學習反饋。"
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
        "max_tokens": 500,
        "temperature": 0.6,
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

    # 清理大模型可能自帶的 markdown 外框
    if text.startswith("```html"):
        text = text.replace("```html", "", 1)
    if text.startswith("```"):
        text = text.replace("```", "", 1)
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ==============================================================
# 規則式退路（安全防護）
# ==============================================================
def _rule_based(ctx: dict) -> str:
    name = ctx.get("username") or "探險者"
    games = ctx.get("games_played") or 0

    if games == 0:
        return (
            f"嗨 <b>{name}</b>！你還沒有完成過任何一局。<br>"
            "先去大廳開一局，答幾道題之後回來，這裡就會出現你的學習分析。"
        )

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