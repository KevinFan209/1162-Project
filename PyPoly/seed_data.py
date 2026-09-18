# 🏆 UTF-8 輸出保險：cp950(繁中) 主控台印 emoji 會拋 UnicodeEncodeError。
# 本檔的成功訊息在 try 區塊內，一旦 print 失敗會被 except 誤判為「初始化失敗」，
# 明明資料已寫入卻顯示錯誤並噴 traceback（與 main.py 開頭相同的處理）。
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database import SessionLocal, engine
import models

# 初始化：確保資料表已根據新欄位建立
models.Base.metadata.create_all(bind=engine)

# ==========================================================
# 正式題庫（Python 程式教學）
# 說明：
#   category 是「遊戲模式」(basic/advanced)，qtype 是「作答方式」：
#     choice  基礎模式  四選一，answer 為正確「選項編號」1~4，玩家比手勢 1~4
#     code    進階模式  手打 Python 程式碼，交給 AI 判分，無選項也無 answer
#   - topic：語法主題，供需求⑨結算報表「最常出現語法」統計用。
#
#   曾有第三種 gesture（直接算出答案並比手勢），已於 2026-09-18 廢除。
#   題目由 db_migrate.py 從資料庫刪除，這裡也不再產生，否則會又長回來。
# 每筆格式：
#   BASIC_QUESTIONS -> (topic, content, [opt1, opt2, opt3, opt4], answer)
#   CODE_QUESTIONS  -> (topic, content, starter_code, expected_output, reference_solution)
# ==========================================================

BASIC_QUESTIONS = {
    "easy": [
        ("變數",   "在 Python 中，要把整數 10 指定給變數 x，正確寫法是？", ["x = 10", "x == 10", "10 = x", "int x = 10"], 1),
        ("運算子", "在 Python 中，7 % 3 的結果是？",                        ["0", "1", "2", "21"], 2),
        ("運算子", "在 Python 中，2 ** 3 的結果是？",                       ["6", "8", "9", "23"], 2),
        ("字串",   "在 Python 中，'Py' + 'thon' 的結果是？",                ["Python", "Py thon", "執行錯誤", "Pythn"], 1),
        ("資料型別", "在 Python 中，type(3.14) 會回傳哪一種型別？",          ["int", "str", "float", "bool"], 3),
        ("輸出",   "要在螢幕印出 Hello，正確的寫法是？",                     ["echo Hello", "print('Hello')", "printf('Hello')", "console.log('Hello')"], 2),
    ],
    "normal": [
        ("條件判斷", "當 x = 8 時，if x > 5: 底下的區塊會不會被執行？",       ["會執行", "不會執行", "語法錯誤", "無限迴圈"], 1),
        ("串列",   "lst = [3, 6, 9]，lst[1] 的值是？",                      ["3", "6", "9", "1"], 2),
        ("串列",   "lst = [1, 2, 3]，執行 lst.append(4) 後 len(lst) 為？",  ["3", "4", "5", "2"], 2),
        ("迴圈",   "for i in range(3): 會讓 i 依序等於哪些值？",             ["1,2,3", "0,1,2", "0,1,2,3", "1,2"], 2),
        ("字串",   "s = 'ABCD'，s[0] 的值是？",                            ["A", "B", "D", "0"], 1),
        ("布林",   "在 Python 中，not True 的結果是？",                     ["True", "False", "1", "執行錯誤"], 2),
    ],
    "hard": [
        ("函式",   "def f(a, b): return a + b，呼叫 f(2, 3) 的回傳值是？",   ["23", "5", "6", "執行錯誤"], 2),
        ("字典",   "d = {'a': 1, 'b': 2}，d['b'] 的值是？",                ["1", "2", "b", "a"], 2),
        ("迴圈",   "i 從 0 開始，while i < 3 時每次 i 加 1，迴圈結束後 i 為？", ["0", "2", "3", "無限迴圈"], 3),
        ("串列",   "lst = [5, 4, 3, 2, 1]，lst[-1] 的值是？",              ["5", "4", "1", "-1"], 3),
        ("例外",   "在 Python 中，int('abc') 會發生什麼事？",               ["回傳 0", "回傳 abc", "丟出 ValueError", "回傳 None"], 3),
        ("切片",   "s = 'PYTHON'，s[1:4] 的結果是？",                      ["PYT", "YTH", "YTHO", "THO"], 2),
    ],
}

# ==========================================================
# 程式碼題（qtype='code'）
#
# 玩家在遊戲中手打 Python，送到 /game/verify_code 由 AI 判分。
# expected_output 與 reference_solution 是判分依據——沒有它們，AI 等於要
# 自己猜標準答案是什麼，同一份學生程式碼可能這次判過、下次判不過。
# ⚠️ 這兩欄絕對不可以回傳給前端，那就是答案本身。
#
# 每筆格式：(topic, content, starter_code, expected_output, reference_solution)
# ==========================================================

CODE_QUESTIONS = {
    "easy": [
        ("輸出", "請用 print 在螢幕上印出 Hello, PyPoly",
         "# 在這裡寫下你的程式碼\n",
         "Hello, PyPoly",
         "print('Hello, PyPoly')"),
        ("變數", "宣告變數 x 等於 10、變數 y 等於 3，然後印出 x + y 的結果。",
         "x = \ny = \n",
         "13",
         "x = 10\ny = 3\nprint(x + y)"),
        ("運算子", "印出 17 除以 5 的「商」與「餘數」，兩個數字各佔一行。",
         "",
         "3\n2",
         "print(17 // 5)\nprint(17 % 5)"),
        ("字串", "已知 name = 'Python'，請印出這個字串的長度。",
         "name = 'Python'\n",
         "6",
         "name = 'Python'\nprint(len(name))"),
    ],
    "normal": [
        ("迴圈", "用 for 迴圈印出 1 到 5，每個數字各佔一行。",
         "for i in range(...):\n    ",
         "1\n2\n3\n4\n5",
         "for i in range(1, 6):\n    print(i)"),
        ("條件判斷", "已知 score = 72，若大於等於 60 印出「及格」，否則印出「不及格」。",
         "score = 72\n",
         "及格",
         "score = 72\nif score >= 60:\n    print('及格')\nelse:\n    print('不及格')"),
        ("串列", "已知 lst = [5, 3, 9, 1]，請印出這個串列由小到大排序後的結果。",
         "lst = [5, 3, 9, 1]\n",
         "[1, 3, 5, 9]",
         "lst = [5, 3, 9, 1]\nprint(sorted(lst))"),
        ("迴圈", "用迴圈計算 1 加到 10 的總和，並印出結果。",
         "total = 0\n",
         "55",
         "total = 0\nfor i in range(1, 11):\n    total += i\nprint(total)"),
    ],
    "hard": [
        ("函式", "寫一個函式 area(w, h) 回傳長方形面積，並印出 area(4, 6) 的結果。",
         "def area(w, h):\n    ",
         "24",
         "def area(w, h):\n    return w * h\n\nprint(area(4, 6))"),
        ("迴圈", "印出 1 到 20 之間所有 3 的倍數，用一個空白隔開印在同一行。",
         "",
         "3 6 9 12 15 18",
         "res = [str(i) for i in range(1, 21) if i % 3 == 0]\nprint(' '.join(res))"),
        ("串列", "已知 lst = [4, 7, 2, 9, 5]，印出其中最大值與最小值的差。",
         "lst = [4, 7, 2, 9, 5]\n",
         "7",
         "lst = [4, 7, 2, 9, 5]\nprint(max(lst) - min(lst))"),
        ("函式", "寫一個函式 is_even(n)，n 是偶數回傳 True 否則回傳 False，"
                 "接著印出 is_even(8) 與 is_even(7)，各佔一行。",
         "def is_even(n):\n    ",
         "True\nFalse",
         "def is_even(n):\n    return n % 2 == 0\n\nprint(is_even(8))\nprint(is_even(7))"),
    ],
}


def seed_data():
    db = SessionLocal()
    try:
        # ⚠️ 這裡刻意「不」清空題庫。
        #    題庫現在可以從後台 question.html 新增與編輯，整表刪掉會把老師
        #    自己出的題目一起洗掉。改成以 content 比對，只補上還沒有的題目，
        #    既有的一律不動——所以這支腳本可以安心重複執行。
        #    真的要從頭重建請帶 --reset。
        #    （情境 scenarios 一樣交由 init_adventure_data.py 專責，這裡不碰。）
        if "--reset" in sys.argv:
            removed = db.query(models.Question).delete()
            db.commit()
            print(f"⚠️  --reset：已清空 {removed} 筆既有題目")

        existing = {c for (c,) in db.query(models.Question.content).all()}
        added = skipped = 0

        def put(**kw):
            nonlocal added, skipped
            if kw["content"] in existing:
                skipped += 1
                return
            db.add(models.Question(**kw))
            existing.add(kw["content"])
            added += 1

        for difficulty, items in BASIC_QUESTIONS.items():
            for topic, content, opts, answer in items:
                put(category="basic", qtype="choice",
                    topic=topic, difficulty=difficulty, content=content,
                    opt1=opts[0], opt2=opts[1], opt3=opts[2], opt4=opts[3],
                    answer=answer)

        for difficulty, items in CODE_QUESTIONS.items():
            for topic, content, starter, expected, solution in items:
                put(category="advanced", qtype="code",
                    topic=topic, difficulty=difficulty, content=content,
                    opt1=None, opt2=None, opt3=None, opt4=None, answer=None,
                    starter_code=starter,
                    expected_output=expected,
                    reference_solution=solution,
                    time_limit_sec=300, max_attempts=3)

        db.commit()
        print(f"✅ 題庫更新完成：新增 {added} 筆，已存在跳過 {skipped} 筆。")
    except Exception as e:
        db.rollback()
        print(f"❌ 題庫寫入失敗: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
