"""AI 導師對話引擎 —— PyPoly/learn_ai.py"""
from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_URL = os.getenv("LLM_URL", "https://api.openai.com")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))


def generate_report(ai_context: dict) -> str:
    """依玩家作答紀錄與發問內容產生精準回饋。"""
    try:
        return _call_llm(ai_context)
    except Exception as e:
        print(f"⚠️ [AI 導師] 呼叫異常: {e}")
        return "導師正在整理思緒，請再試一次！"


def _call_llm(ai_context: dict) -> str:
    user_msg = (ai_context.get("message") or "").strip()
    history = ai_context.get("history") or []

    # 提取做錯的題目紀錄
    recent_wrong = ai_context.get("recent_wrong", [])
    wrong_lines = []
    for item in recent_wrong[:3]:
        q = item.get("question", "")
        chosen = item.get("chosen_text") or item.get("chosen", "")
        correct = item.get("correct_text") or item.get("correct", "")
        wrong_lines.append(f"題目：{q} (學生選了: {chosen}, 正確答案: {correct})")
    wrong_str = "\n".join(wrong_lines) if wrong_lines else "包含 not True 與 list.append() 觀念"

    system_prompt = (
        "你是專門引導國中小學童學習 Python 的「PyPoly 大富翁隨行 AI 導師」。\n"
        "【嚴格對話準則】\n"
        "1. 必須 100% 針對學生最後一句發言作答，不可忽略問題！\n"
        "2. 若學生問「我錯了什麼題目」：直接列出他做錯的具體題目與原因。\n"
        "3. 若學生點擊「出一題類似題目」：立刻出一題有 code 和 A, B, C 三個選項的單選題，不要先講答案！\n"
        "4. 若學生回答了答案（如輸入 A、B、C）：第一句立刻判定【答對了 🎉】或【答錯了 💡】，並具體解釋原因。\n"
        "5. 格式使用 HTML（<b>、<code>、<br>），字數在 140 字以內。"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # 載入前幾輪對話歷史
    if isinstance(history, list):
        for msg in history[-6:]:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append({"role": msg["role"], "content": msg["content"]})

    # 若為首次載入（無使用者提問）
    if not user_msg and len(messages) <= 1:
        messages.append({
            "role": "user",
            "content": f"學生錯題紀錄：\n{wrong_str}\n請給出一段簡短溫暖的開場學習評語與弱點提示："
        })
    elif user_msg and (not messages or messages[-1].get("content") != user_msg):
        messages.append({
            "role": "user",
            "content": f"學生錯題背景：{wrong_str}\n學生最新發言：{user_msg}"
        })

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "max_tokens": 400,
        "temperature": 0.4,
    }

    response = requests.post(
        f"{LLM_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()

    reply = response.json()["choices"][0]["message"]["content"].strip()
    if reply.startswith("```html"):
        reply = reply.replace("```html", "", 1)
    if reply.startswith("```"):
        reply = reply.replace("```", "", 1)
    if reply.endswith("```"):
        reply = reply[:-3]

    return reply.strip()