"""AI 導師分析與多輪對話 —— learn.html 右側面板"""
from __future__ import annotations

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_URL = os.getenv("LLM_URL", "https://api.openai.com")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))


def generate_report(ai_context: dict) -> str:
    """依學習統計或使用者即時提問，回傳個人化分析與解答。"""
    try:
        return _call_llm(ai_context)
    except Exception as e:
        print(f"⚠️ [AI 導師] 呼叫外部 API 失敗，啟用退路機制: {e}")
        return _rule_based(ai_context)


def _call_llm(ai_context: dict) -> str:
    name = ai_context.get("username", "探險者")
    user_message = ai_context.get("message")  # 接收使用者的對話輸入
    question_context = ai_context.get("question_context")
    accuracy = ai_context.get("accuracy", 0)
    strongest = "、".join(ai_context.get("strongest", [])) or "基礎觀念"
    weakest = "、".join(ai_context.get("weakest", [])) or "暫無明顯弱項"

    # 彙整玩家最近錯題
    recent_wrong = ai_context.get("recent_wrong", [])
    wrong_summary = []
    if recent_wrong:
        for idx, item in enumerate(recent_wrong[:5], 1):
            q_topic = item.get("topic", "語法")
            q_text = item.get("question", "")
            chosen = item.get("chosen_text") or item.get("chosen", "?")
            correct = item.get("correct_text") or item.get("correct", "?")
            wrong_summary.append(
                f"{idx}. [{q_topic}] 題目：{q_text} | 玩家選了：{chosen} | 正確答案：{correct}"
            )
    wrong_text = "\n".join(wrong_summary) if wrong_summary else "目前無答錯紀錄"

    system_prompt = (
        "你是專門引導國中小學童學習 Python 的「PyPoly 大富翁隨行 AI 導師」。\n"
        "特質：溫暖親切、善於比喻、對話精準、不講冗長廢話。\n\n"
        "回答原則：\n"
        "1. 若學生在對話框主動提問（例如問『我選錯了什麼題目』、『這題為什麼錯』）：\n"
        "   - **務必直接且正面回答學生的問題**，不可回答無關的固定模組套話。\n"
        "   - 參考【學生近期錯題紀錄】，具體指稱他做錯的題目敘述與選項，並用淺顯易懂的生活例子或觀念口訣解釋。\n"
        "2. 若未提供學生留言（為首次載入統計報表）：\n"
        "   - 先肯定其強項，再針對其弱項給予 1~2 點具體解惑建議。\n"
        "3. 請輸出 HTML 格式（使用 <b>、<code>、<br> 標籤，絕對不要包裹 ```html 外框）。\n"
        "4. 字數精準控制在 160 字以內。"
    )

    # 判斷是否為使用者主動發起的即時對話
    if user_message:
        user_prompt = f"""
【學生基本資訊】
姓名：{name}
歷史錯題紀錄：
{wrong_text}

【學生目前關注的題目資訊】
{json.dumps(question_context, ensure_ascii=False) if question_context else "無指定特定題目"}

【學生的問題】
"{user_message}"

請直接且具體地回答學生的問題，點出對應的錯題與概念：
"""
    else:
        user_prompt = f"""
【學生作答概況】
姓名：{name}
正確率：{accuracy}%
強項：{strongest}
待加強主題：{weakest}
錯題紀錄：
{wrong_text}

請為該學生產出一份溫暖且具啟發性的學習總評：
"""

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

    # 清理 markdown 外框
    if text.startswith("```html"):
        text = text.replace("```html", "", 1)
    if text.startswith("```"):
        text = text.replace("```", "", 1)
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def _rule_based(ctx: dict) -> str:
    user_msg = ctx.get("message", "")
    recent_wrong = ctx.get("recent_wrong", [])

    if user_msg and "錯" in user_msg:
        if recent_wrong:
            first = recent_wrong[0]
            return (
                f"你剛才在【{first.get('topic', '語法')}】這題失分囉！<br>"
                f"題目是：<b>{first.get('question', '')}</b>。<br>"
                f"記得再仔細核對選項中的邊界條件與運算符號！"
            )
        return "你目前表現很好，近幾局沒有記錄到嚴重失分的題目喔！繼續保持！"

    acc = ctx.get("accuracy") or 0
    return f"目前正確率為 <b>{acc}%</b>。在下方對話框輸入你想問的問題，我會針對你的作答進行解說！"