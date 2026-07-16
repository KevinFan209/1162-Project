from database import SessionLocal, engine
import models

# 初始化：確保資料表已根據新欄位建立
models.Base.metadata.create_all(bind=engine)

# ==========================================================
# 正式題庫（Python 程式教學）
# 說明：
#   - 遊戲以「手勢比數字」作答，answer 即玩家要比出的數字。
#   - 基礎題(basic)：四選一，answer 為正確「選項編號」1~4，玩家比出 1~4。
#   - 進階題(advanced)：直接算出答案，answer 為個位數字 1~9（手勢僅支援 1~9），無選項。
#   - topic：語法主題，供需求⑨結算報表「最常出現語法」統計用。
# 每筆格式：
#   basic    -> (topic, content, [opt1, opt2, opt3, opt4], answer)
#   advanced -> (topic, content, answer)
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

ADVANCED_QUESTIONS = {
    "easy": [
        ("運算子", "請算出 3 + 4 的結果，並用手勢比出該數字。", 7),
        ("運算子", "請算出 2 * 3 的結果。",                     6),
        ("運算子", "請算出 10 - 5 的結果。",                    5),
        ("串列",   "lst = [4, 8, 15]，len(lst) 是多少？",       3),
        ("運算子", "請算出 9 // 2（整數除法）的結果。",          4),
        ("運算子", "請算出 8 % 5 的結果。",                     3),
    ],
    "normal": [
        ("迴圈",   "for i in range(5): 迴圈總共會執行幾次？",                 5),
        ("運算子", "請算出 2 ** 3 的結果。",                                 8),
        ("串列",   "lst = [1, 2, 3, 4]，執行 lst.append(9) 後 len(lst) 為？", 5),
        ("字串",   "s = 'HELLO'，len(s) 是多少？",                          5),
        ("運算子", "請算出 (2 + 3) * 1 的結果。",                           5),
        ("條件判斷", "x = 6，若 x > 3 則 y = 9 否則 y = 1，執行後 y 是多少？",  9),
    ],
    "hard": [
        ("函式",   "def f(n): return n + 2，f(5) 的回傳值是多少？",           7),
        ("迴圈",   "sum = 0，for i in range(4): sum += i，結束後 sum 是多少？", 6),
        ("串列",   "lst = [2, 4, 6, 8]，lst[2] 的值是多少？",                6),
        ("字串",   "s = 'PYTHON'，len(s) 是多少？",                         6),
        ("函式",   "def add(a, b): return a + b，add(4, 5) 的結果是多少？",   9),
        ("迴圈",   "range(1, 4) 總共會產生幾個數字？",                       3),
    ],
}


def seed_data():
    db = SessionLocal()
    try:
        # 只清空題目；情境(scenarios)交由 init_adventure_data.py 專責，避免兩支腳本互相覆蓋
        db.query(models.Question).delete()

        count = 0
        for difficulty, items in BASIC_QUESTIONS.items():
            for topic, content, opts, answer in items:
                db.add(models.Question(
                    category="basic",
                    topic=topic,
                    difficulty=difficulty,
                    content=content,
                    opt1=opts[0], opt2=opts[1], opt3=opts[2], opt4=opts[3],
                    answer=answer,
                ))
                count += 1

        for difficulty, items in ADVANCED_QUESTIONS.items():
            for topic, content, answer in items:
                db.add(models.Question(
                    category="advanced",
                    topic=topic,
                    difficulty=difficulty,
                    content=content,
                    opt1=None, opt2=None, opt3=None, opt4=None,
                    answer=answer,
                ))
                count += 1

        db.commit()
        print(f"✅ 成功插入 {count} 筆正式題庫（含 topic 語法主題、進階題答案皆為 1~9）！")
    except Exception as e:
        db.rollback()
        print(f"❌ 題庫寫入失敗: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
