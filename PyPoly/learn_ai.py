"""AI 導師分析與智慧問答 —— learn.html 右側面板"""
from __future__ import annotations

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_URL = os.getenv("LLM_URL", "https://api.openai.com")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

# 用來記錄對話輪次的記憶體計數（無需改動資料庫與 main.py）
_CALL_COUNTER: dict[str, int] = {}


def generate_report(ai_context: dict) -> str:
    """依玩家作答紀錄產生深度回饋；第二次被呼叫時自動出題！"""
    username = ai_context.get("username", "default_user")
    
    # 計算這個使用者點擊/請求的次數
    count = _CALL_COUNTER.get(username, 0)
    _CALL_COUNTER[username] = count + 1

    try:
        return _call_llm(ai_context, call_turn=count)
    except Exception as e:
        print(f"⚠️ [AI 導師] 呼叫外部 API 失敗，啟用退路機制: {e}")
        return _rule_based(ai_context, call_turn=count)


def _call_llm(ai_context: dict, call_turn: int = 0) -> str:
    name = ai_context.get("username", "探險者")
    weakest = "、".join(ai_context.get("weakest", [])) or "串列與布林值"
    recent_wrong = ai_context.get("recent_wrong", [])

    # 提取做錯的題目資訊
    wrong_examples = []
    for item in recent_wrong[:3]:
        q = item.get("question", "")
        chosen = item.get("chosen_text") or item.get("chosen", "")
        correct = item.get("correct_text") or item.get("correct", "")
        wrong_examples.append(f"錯題：{q} (學生選: {chosen}, 正確答案: {correct})")
    wrong_str = "\n".join(wrong_examples) if wrong_examples else "包含 not True 與 append 概念"

    # 關鍵切換：第 0 次呼叫是剛進頁面的「總評」，第 1 次之後都是玩家點按鈕發問！
    if call_turn == 0:
        system_prompt = (
            "你是 Python 大富翁遊戲的隨行 AI 導師。\n"
            "請給學生一段精簡熱情的學習總評（100 字內）。\n"
            "使用 HTML 標籤（<b>、<code>、<br>），不要包裹 ```html 外框。"
        )
        user_prompt = f"學生：{name}，弱項：{weakest}。\n錯題紀錄：\n{wrong_str}\n請給出鼓勵與概念提示："
    else:
        # 玩家點擊了「出一題類似題目」或發問
        system_prompt = (
            "你是 Python 大富翁的隨行 AI 導師。\n"
            "【最高指令】\n"
            "1. 學生要求『出一題類似題目考考我』或想進一步挑戰！\n"
            "2. 嚴禁重複輸出開場白（絕對不要說『親愛的學生』、『你的正確率是50%』等廢話）。\n"
            "3. 請直接根據學生答錯的 concept（如 list.append 串列增長 或 not True 布林值），出一道簡單有趣的 Python 單選挑戰題！\n"
            "4. 題目格式：\n"
            "   - 標題：🎯 <b>挑戰題來囉！</b><br>\n"
            "   - 程式碼區塊（使用 <code> 標籤）<br>\n"
            "   - 選項：A) ...  B) ...  C) ...<br>\n"
            "   - 結尾：一句話引導學生在對話框輸入答案。<br>\n"
            "5. 請輸出 HTML 格式，不要包裹 ```html 外框。"
        )
        user_prompt = f"請針對此錯題觀念出一題全新的練習題給學生：\n{wrong_str}"

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


def _rule_based(ctx: dict, call_turn: int = 0) -> str:
    if call_turn > 0:
        return (
            "🎯 <b>挑戰題來囉！</b><br>"
            "執行以下程式碼後，列表長度是多少呢？<br>"
            "<code>fruits = ['蘋果', '香蕉']<br>fruits.append('芭樂')</code><br><br>"
            "A) 2 &nbsp;&nbsp;&nbsp;&nbsp; B) 3 &nbsp;&nbsp;&nbsp;&nbsp; C) 4<br><br>"
            "在下方輸入你的選項（A、B 或 C）試試看！"
        )
    return "歡迎來到學習分析！在串列操作中記得 <code>append()</code> 會讓元素加一，而 <code>not True</code> 就是 False 喔！"