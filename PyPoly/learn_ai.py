"""AI 導師對話引擎 —— PyPoly/learn_ai.py"""
from __future__ import annotations

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_URL = os.getenv("LLM_URL", "https://api.openai.com")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

# 本地記憶體對話歷史快取（依照使用者名稱維護多輪對話）
_USER_CHATS: dict[str, list[dict]] = {}


def generate_report(ai_context: dict) -> str:
    """供後端調用的進入點。"""
    try:
        return _call_llm(ai_context)
    except Exception as e:
        print(f"⚠️ [AI 導師] 呼叫異常: {e}")
        return _rule_based(ai_context)


def _call_llm(ai_context: dict) -> str:
    username = ai_context.get("username", "default_user")
    name = ai_context.get("username", "探險者")
    user_msg = (ai_context.get("message") or "").strip()
    history = ai_context.get("history") or _USER_CHATS.get(username, [])

    # 提取做錯的題目資訊
    recent_wrong = ai_context.get("recent_wrong", [])
    wrong_lines = []
    for item in recent_wrong[:3]:
        q = item.get("question", "")
        chosen = item.get("chosen_text") or item.get("chosen", "")
        correct = item.get("correct_text") or item.get("correct", "")
        wrong_lines.append(f"錯題：{q} (學生選了: {chosen}, 正解: {correct})")
    wrong_str = "\n".join(wrong_lines) if wrong_lines else "包含 not True 與 append 概念"

    system_prompt = (
        "你是專為國中小學童解答的「PyPoly Python AI 導師」。\n"
        "【嚴格交談規則】\n"
        "1. 你必須像真人導師一樣進行連續對話，參考先前的聊天紀錄！\n"
        "2. 當你先前出了一題挑戰題，學生現在回答了選項（例如輸入 A、B、C 或答案文字）：\n"
        "   - **第一句話立刻批改**：明確告訴他「答對了 🎉」或「答錯了 💡」！\n"
        "   - 具體拆解各選項為什麼對或錯，並解釋解題思路。\n"
        "   - 不要連續主動狂出新題目，先好好給予這題的回饋與肯定！\n"
        "3. 當學生點擊「出一題類似題目」：請出一道包含簡短程式碼、A) B) C) 選項的單選挑戰題，不要先公佈答案！\n"
        "4. 當學生問「口訣」：給予一句押韻好記的語法口訣。\n"
        "5. 格式：輸出 HTML（使用 <b>、<code>、<br>），不要包裹 ```html 外框，字數 140 字以內。"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # 將過往對話放入 messages
    for msg in history[-8:]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # 如果有新傳進來的使用者訊息
    if user_msg and (not messages or messages[-1].get("content") != user_msg):
        messages.append({
            "role": "user",
            "content": f"學生錯題背景：{wrong_str}\n學生最新發言：{user_msg}"
        })
    elif len(messages) == 1:
        # 首次載入頁面開場
        messages.append({
            "role": "user",
            "content": f"學生錯題紀錄：\n{wrong_str}\n請給出親切簡短的開場評語與鼓勵："
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

    reply = reply.strip()

    # 記錄到記憶體快取
    if username not in _USER_CHATS:
        _USER_CHATS[username] = []
    if user_msg:
        _USER_CHATS[username].append({"role": "user", "content": user_msg})
    _USER_CHATS[username].append({"role": "assistant", "content": reply})

    return reply


def _rule_based(ctx: dict) -> str:
    user_msg = (ctx.get("message") or "").strip().upper()
    if user_msg in ["A", "B", "C"]:
        return f"你選擇了 <b>{user_msg}</b>！太棒了，有積極思考。記得 <code>len()</code> 會算長度，而 <code>not False</code> 是 True 喔！"
    return "歡迎來到學習分析！有任何問題隨時在下方輸入，導師為你一一解惑！"