"""AI 導師分析與精準問答 —— learn.html 右側面板"""
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
    """依學習統計或使用者即時提問產生精準解答。"""
    try:
        return _call_llm(ai_context)
    except Exception as e:
        print(f"⚠️ [AI 導師] 呼叫外部 API 失敗，切換至退路: {e}")
        return _rule_based(ai_context)


def _call_llm(ai_context: dict) -> str:
    name = ai_context.get("username", "探險者")
    user_msg = (ai_context.get("message") or "").strip()
    accuracy = ai_context.get("accuracy", 0)
    weakest = "、".join(ai_context.get("weakest", [])) or "串列"
    
    # 解析錯題
    recent_wrong = ai_context.get("recent_wrong", [])
    wrong_lines = []
    for idx, item in enumerate(recent_wrong[:5], 1):
        q = item.get("question", "")
        chosen = item.get("chosen_text") or item.get("chosen", "?")
        correct = item.get("correct_text") or item.get("correct", "?")
        wrong_lines.append(f"{idx}. 題目：{q} | 學生選：{chosen} | 正解：{correct}")
    wrong_summary = "\n".join(wrong_lines) if wrong_lines else "目前無近期錯題紀錄"

    # 1. 判斷是否有使用者發問
    if user_msg:
        system_prompt = (
            "你是國中小學童的 Python 大富翁 AI 導師。\n"
            "【嚴格執行規則】\n"
            "1. 必須 100% 針對使用者的「最新問題/需求」直接作答！\n"
            "2. 嚴禁重複輸出開場白（例如『你好！你的基礎觀念很不錯』）。\n"
            "3. 如果學生要求「出類似題目」：請立刻根據他做錯的主題（如串列 append、布林值），直接出一道好玩的 Python 單選挑戰題（含 A, B, C 選項），並鼓勵他回答，不要直接給答案！\n"
            "4. 如果學生問「我錯了什麼」：直接列出他做錯的具體題目並解釋核心觀念。\n"
            "5. 使用簡單 HTML 排版（<b>、<code>、<br>），不要使用 ```html 程式碼外框，150 字內。"
        )
        user_prompt = f"""
學生姓名：{name}
學生弱項：{weakest}
學生做錯的題目紀錄：
{wrong_summary}

學生發送的問題：
"{user_msg}"

請直接回答該問題：
"""
    else:
        system_prompt = (
            "你是 Python 大富翁的 AI 導師。請根據統計數據寫一段親切、簡短的開場學習評語。\n"
            "使用 HTML 標籤（<b>、<code>、<br>），不要包裹 ```html 外框，120 字內。"
        )
        user_prompt = f"""
學生：{name}
正確率：{accuracy}%
待加強主題：{weakest}
錯題紀錄：
{wrong_summary}
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
        "temperature": 0.4,
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

    if text.startswith("```html"):
        text = text.replace("```html", "", 1)
    if text.startswith("```"):
        text = text.replace("```", "", 1)
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def _rule_based(ctx: dict) -> str:
    user_msg = (ctx.get("message") or "").strip()
    if "類似" in user_msg or "題" in user_msg:
        return (
            "🎯 <b>挑戰題來囉！</b><br>"
            "如果執行以下程式碼，結果長度是多少呢？<br>"
            "<code>nums = [1, 2]<br>nums.append(3)</code><br>"
            "A) 2 &nbsp;&nbsp; B) 3 &nbsp;&nbsp; C) 4<br>"
            "在下方輸入你的答案試試看！"
        )
    return "針對 Python 概念，記得串列長度會隨 append 增加，而 <code>not True</code> 就是 False 喔！"