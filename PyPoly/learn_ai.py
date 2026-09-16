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
    """依學習統計或單題提問產生分析回饋。

    - 若 context 包含 'selected_question' 或 'question'，執行單題診斷模式。
    - 若無，則執行整局學習成就總覽診斷。
    """
    is_single_q = "selected_question" in ai_context or "question" in ai_context
    
    # 總覽模式下，若一局都沒玩過，直接返回引導文字
    if not is_single_q and (ai_context.get("games_played") or 0) == 0:
        return _rule_based(ai_context)

    try:
        return _call_llm(ai_context)
    except Exception as e:
        print(f"⚠️ [AI 導師] 外部 API 調用異常，切換至退路: {e}")
        return _rule_based(ai_context)


# ==============================================================
# LLM 核心診斷實作
# ==============================================================
def _call_llm(ai_context: dict) -> str:
    name = ai_context.get("username", "探險者")
    
    # 判斷是否為單題提問 / 追問模式
    target_q = ai_context.get("selected_question") or (ai_context if "question" in ai_context else None)
    follow_up = ai_context.get("follow_up_prompt", "")

    if target_q:
        # 模式 A：單題深度解構模式（點擊題目旁的「詢問老師」按鈕）
        q_text = target_q.get("question", "未知題目")
        topic = target_q.get("topic", "Python 觀念")
        options = target_q.get("options", [])
        chosen = target_q.get("chosen", "")
        correct = target_q.get("correct", "")
        is_correct = target_q.get("is_correct", False)

        opt_desc = "、".join([f"選項 {idx+1}: {opt}" for idx, opt in enumerate(options)]) if options else "無選項紀錄"
        status_text = "回答正確" if is_correct else "回答錯誤"

        system_prompt = (
            "你是 PyPoly 程式大富翁的隨行「AI 程式家教」，專門引導國中小學童。\n"
            "你的目標是剖析題目思維，引導孩子從題目中學會邏輯，不要長篇大論。\n\n"
            "回答架構：\n"
            "1. 選項思維剖析：溫和指出他選【{chosen}】時可能的思考盲點（例如是不是把 0-indexed 搞混了，或是誤會了條件邊界）。若答對，則提點該題核心考點。\n"
            "2. 正解思路指引：用最直白的方式解釋為什麼【{correct}】才是對的，並附上 1 行簡短的程式邏輯或記憶口訣。\n"
            "3. 延伸追問引導（核心）：在段落最末尾，以特定標籤格式輸出 2 個學童可能想繼續問的問題：\n"
            "   格式範例：[SUGGEST: 出一題類似的題目考考我] [SUGGEST: 這題的記憶口訣是什麼？]\n\n"
            "輸出要求：\n"
            "- 本文採用精簡 HTML（使用 <b>、<code>、<br>），不使用 Markdown 區塊標記。\n"
            "- 解題說明文字控制在 130 字以內，語氣生動溫暖。"
        )

        user_content = (
            f"學生：{name}\n"
            f"題目觀念：{topic}\n"
            f"題目：{q_text}\n"
            f"所有選項：{opt_desc}\n"
            f"學生當時選擇：{chosen}\n"
            f"正確解答：{correct}\n"
            f"作答狀態：{status_text}\n"
        )
        if follow_up:
            user_content += f"學生當前追問：{follow_up}\n"

        user_prompt = user_content + "\n請針對上述題目與選擇進行解構回饋："

    else:
        # 模式 B：全局總結報表模式
        accuracy = ai_context.get("accuracy", 0)
        strongest = "、".join(ai_context.get("strongest", [])) or "基礎語法"
        weakest = "、".join(ai_context.get("weakest", [])) or "暫無明顯弱項"
        recent_wrong = ai_context.get("recent_wrong", [])
        
        wrong_block = ""
        if recent_wrong:
            details = [
                f"錯題 {i+1} [{item.get('topic', '未分類')}]：{item.get('question')} (學生選 {item.get('chosen')}，正解為 {item.get('correct')})"
                for i, item in enumerate(recent_wrong[:3])
            ]
            wrong_block = "【近期失分題】\n" + "\n".join(details)

        system_prompt = (
            "你是 PyPoly 大富翁的「Python 隨行 AI 導師」，面向國中小學童。\n"
            "1. 一句話肯定他在強項主題的邏輯表現。\n"
            "2. 針對失分弱項，給予具體觀念盲點點撥與 1 句記憶口訣。\n"
            "3. 融入南投山城、大富翁闖關情境進行激勵。\n"
            "4. 直接輸出乾淨 HTML（<b>、<code>、<br>），字數控制在 120 字內。"
        )

        user_prompt = (
            f"學員名稱：{name}\n"
            f"總體正確率：{accuracy}%\n"
            f"掌握較佳：{strongest}\n"
            f"待加強：{weakest}\n"
            f"{wrong_block}\n\n"
            "請給予精簡的全局回饋："
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

    # 清理外層 Markdown 格式標籤
    if text.startswith("```html"):
        text = text.replace("```html", "", 1)
    if text.startswith("```"):
        text = text.replace("```", "", 1)
    if text.endswith("```"):
        text = text[:-3]

    # 將 [SUGGEST: ...] 轉換為前端可點擊的追問按鈕 HTML
    import re
    def make_chip(match):
        label = match.group(1).strip()
        return f'<button class="ai-chip-btn" onclick="sendFollowUp(\'{label}\')">💬 {label}</button>'

    text = re.sub(r"\[SUGGEST:\s*(.*?)\]", make_chip, text)

    return text.strip()


# ==============================================================
# 規則式保底機制
# ==============================================================
def _rule_based(ctx: dict) -> str:
    name = ctx.get("username") or "探險者"
    target_q = ctx.get("selected_question") or (ctx if "question" in ctx else None)

    # 單題模式的離線保底
    if target_q:
        q_text = target_q.get("question", "")
        chosen = target_q.get("chosen", "")
        correct = target_q.get("correct", "")
        is_correct = target_q.get("is_correct", False)

        if is_correct:
            return (
                f"太棒了 <b>{name}</b>！這題「{q_text}」你選擇 <code>{chosen}</code> 是完全正確的。<br>"
                "解題關鍵在於掌握了語法的邊界與執行順序，繼續保持！"
            )
        else:
            return (
                f"這題「{q_text}」稍微可惜了！<br>"
                f"你選擇了 <code>{chosen}</code>，但正確答案其實是 <code>{correct}</code>。<br>"
                "建議注意變數初值或是迴圈是否包含最後一個數字喔！"
            )

    # 全局模式保底
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

    parts = [f"嗨 <b>{name}</b>！本局作答正確率 <b>{acc}%</b>（共答 {total} 題）。"]
    if strongest:
        parts.append(f"你在 <b>{strongest[0]}</b> 概念掌握得相當穩固！")
    if weakest:
        parts.append(f"目前可以多針對 <b>{weakest[0]}</b> 多練習，點擊左側題目旁按鈕，我可以為你單獨解說！")

    return "<br>".join(parts)