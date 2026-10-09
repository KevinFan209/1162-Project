from sqlalchemy.orm import Session
import models

def seed_handbook_data(db: Session):
    starter_lessons = [
        {
            "order_index": 1,
            "title": "電腦是個死腦筋！什麼是程式？",
            "category": "intro",
            "cat_name": "零基礎啟蒙",
            "cat_class": "cat-basic",
            "level": "★☆☆ 啟蒙",
            "description": "電腦其實超級笨，它完全聽不懂人類說的中文或英文。寫程式，就是用電腦看得懂的「精確指令」，一步一步指揮它做事。只要指令漏了一個逗號、多了一個空格，電腦就會耍脾氣罷工（當機報錯）！",
            "code_example": "# 這是一行「註解」，寫給人看的，電腦會直接跳過\n# 電腦會由上到下，一行一行嚴格執行你的指令",
            "tip": "在 Python 裡面，只要在開頭加上井字號「#」，後面的文字就會變成註解，不會被電腦執行喔！"
        },
        {
            "order_index": 2,
            "title": "print() — 讓電腦開口說話",
            "category": "intro",
            "cat_name": "零基礎啟蒙",
            "cat_class": "cat-basic",
            "level": "★☆☆ 啟蒙",
            "description": "如果你想叫電腦在螢幕上顯示文字或算出來的結果，就要使用 print() 這個神奇咒語。圓括號 ( ) 裡面放的就是你要電腦說出來的內容。",
            "code_example": "print(\"哈囉！我是未來的程式大師！\")\nprint(12345)",
            "tip": "千萬記得：print 的英文全部都是小寫！寫成 Print 或 PRINT，電腦會跟你說它不認識這個字！"
        },
        {
            "order_index": 3,
            "title": "字串 (str) — 為什麼文字要穿衣服？",
            "category": "data",
            "cat_name": "資料型態",
            "cat_class": "cat-data",
            "level": "★☆☆ 必備",
            "description": "只要是人類講的話、名字、文字，在 Python 裡都叫做「字串 (String, 簡稱 str)」。文字出門一定要「穿衣服」，也就是用單引號 ' ' 或雙引號 \" \" 把文字緊緊包起來！如果不包，電腦會以為那是一個「變數名稱」或是「暗號指令」，發現找不到就會大聲報錯！",
            "code_example": "name = \"蜜蜂工程師\"    # 正確！有穿衣服的文字是字串\n# 錯誤示範：name = 蜜蜂工程師  -> 電腦會看不懂爆出 NameError",
            "tip": "單引號 ' ' 或雙引號 \" \" 都可以，但前後必須成雙成對，不能前面用單引號、後面卻用雙引號收尾！"
        },
        {
            "order_index": 4,
            "title": "整數 (int) 與小數 (float) — 算術用的數字",
            "category": "data",
            "cat_name": "資料型態",
            "cat_class": "cat-data",
            "level": "★☆☆ 必備",
            "description": "用來算數學的數字「絕對不能穿衣服（不能加引號）」！整數（沒有小數點的數字，如 100, -5）在 Python 叫 int；帶有小數點的數字（如 3.14, 25.8）在 Python 叫浮點數 float。",
            "code_example": "coins = 5000       # int (整數)：買房、金幣都是整數\ntemp = 24.5        # float (浮點數)：氣溫、體溫常有小數點\nprint(coins + 100) # 印出 5100，電腦會自動幫你算好！",
            "tip": "天大陷阱！500 是數字 int；但 \"500\" 穿了引號就會變成文字 str！\"500\" + \"500\" 在電腦眼裡是字串相黏，結果會變成 \"500500\"，而不是 1000！"
        },
        {
            "order_index": 5,
            "title": "變數 (Variable) — 貼上標籤的魔法收納盒",
            "category": "data",
            "cat_name": "資料型態",
            "cat_class": "cat-data",
            "level": "★☆☆ 必備",
            "description": "寫遊戲時，玩家的血量、金幣隨時都在改變。變數就像一個收納盒，我們給盒子貼個標籤（取個名字），然後用「單等號 =」將東西放進去。「單等號 =」不是數學的等於，它的意思是「將右邊的東西放進左邊的盒子裡」！",
            "code_example": "my_money = 3000          # 把 3000 放進叫 my_money 的盒子\nmy_money = my_money - 200 # 買東西花掉 200，盒子裡剩 2800\nprint(my_money)",
            "tip": "變數名字有規矩：只能用英文字母、數字和底線 _，而且開頭「絕對不能用數字」！"
        },
        {
            "order_index": 6,
            "title": "布林值 (bool) — 只有「對」與「錯」的開關",
            "category": "data",
            "cat_name": "資料型態",
            "cat_class": "cat-data",
            "level": "★★☆ 核心",
            "description": "電腦世界裡最單純的型態叫布林值 (Boolean, 簡稱 bool)。它只有兩個值：True（是真的、對的）或是 False（是假的、錯的）。就像電燈開關一樣，不是開就是關，常用來記錄「玩家是否還活著」、「是否買得起土地」。",
            "code_example": "is_game_over = False    # 遊戲還沒結束\ncan_buy_land = True     # 有足夠的金幣，可以買房\nprint(10 > 5)           # 電腦會回答：True (因為 10 真的大於 5)",
            "tip": "True 和 False 的第一個字母「一定要大寫」！寫成 true 或 false 電腦是不認得的喔！"
        },
        {
            "order_index": 7,
            "title": "等號的大陷阱 — 賦值 (=) vs 真正等於 (==)",
            "category": "cond",
            "cat_name": "條件判斷",
            "cat_class": "cat-cond",
            "level": "★★☆ 易錯",
            "description": "這是所有初學者最容易掉進去的陷阱！\n1. 單等號「=」：是「指派/放進去」。例如 hp = 100 是把 100 放進 hp。\n2. 雙等號「==」：才是數學上的「有沒有等於？」用來詢問電腦兩邊一不一樣！",
            "code_example": "dice = 6\n# 詢問電腦：骰子擲出來是 6 嗎？\nif dice == 6:\n    print(\"幸運大爆發！擲出最大點數 6！\")",
            "tip": "要檢查「不等於」時，Python 使用驚嘆號加等號「!=」。例如 if role != \"admin\":。"
        },
        {
            "order_index": 8,
            "title": "縮排 (Indentation) — Python 最神聖的規矩",
            "category": "cond",
            "cat_name": "條件判斷",
            "cat_class": "cat-cond",
            "level": "★★☆ 核心",
            "description": "其他程式語言常用大括號 { } 來分群，但 Python 規定：必須使用「空 4 個空格（或按一下 Tab）」來縮排！縮排進去的程式碼，代表它是「屬於上一層管轄的小弟」。如果縮排亂七八糟，電腦會直接丟出 IndentationError 罷工！",
            "code_example": "coins = 1500\nif coins >= 1000:\n    # 底下這兩行空了 4 格，代表滿足條件才會執行\n    print(\"你的金幣足夠！\")\n    print(\"成功收購這座城堡！\")\nprint(\"不管有沒有買，這行都會執行\")",
            "tip": "冒號「:」是縮排的好朋友！在 if、else、for、while、def 後面一定要加冒號，加完冒號下一行就必須縮排！"
        },
        {
            "order_index": 9,
            "title": "if / elif / else — 人生的命運十字路口",
            "category": "cond",
            "cat_name": "條件判斷",
            "cat_class": "cat-cond",
            "level": "★★☆ 核心",
            "description": "遊戲中踩到格子會發生什麼事？全靠條件判斷！\n• if（如果）：如果滿足這個條件就做這件事。\n• elif（或是如果）：如果上面不滿足，但滿足這個，就做這件事。\n• else（否則）：如果上面通通不滿足，就做最後這個保底動作。",
            "code_example": "step = 3\nif step == 1:\n    print(\"踩到機會格\")\nelif step == 2:\n    print(\"踩到命運格\")\nelse:\n    print(\"踩到空地，可以買房！\")",
            "tip": "電腦只要在上面遇到第一個成立的條件並執行完，後面的 elif 和 else 就會直接跳過不看了！"
        },
        {
            "order_index": 10,
            "title": "for 迴圈與 range() — 自動做苦工的機器人",
            "category": "loop",
            "cat_name": "迴圈控制",
            "cat_class": "cat-loop",
            "level": "★★☆ 核心",
            "description": "如果你想印出 100 次「我愛寫程式」，難道要複製貼上 100 行 print 嗎？不用！用 for 迴圈就可以命令電腦重複執行指定次數。搭配 range(數字)，就能讓機器人乖乖做苦工。",
            "code_example": "# 讓角色前進 3 步\nfor i in range(3):\n    print(\"向前跳一步！現在是第\", i, \"步\")\n# 電腦會印出 0, 1, 2 (電腦的世界都是從 0 開始數的！)",
            "tip": "range(3) 產生的數字是 0, 1, 2，總共 3 次，但「絕對不會數到 3」！這點一定要記住！"
        },
        {
            "order_index": 11,
            "title": "while 迴圈 — 停不下來的跑步機",
            "category": "loop",
            "cat_name": "迴圈控制",
            "cat_class": "cat-loop",
            "level": "★★☆ 核心",
            "description": "for 迴圈適合「知道要跑幾次」的狀況；而 while 迴圈是「只要條件還成立，就永不休止地跑下去」，直到條件破滅（變成 False）為止。",
            "code_example": "hp = 3\nwhile hp > 0:\n    print(\"正在激戰中！剩餘血量：\", hp)\n    hp = hp - 1   # 每次都要扣血！\nprint(\"血量歸零，玩家戰敗！\")",
            "tip": "極度危險！如果在 while 迴圈裡面忘記扣血（hp 一直維持大於 0），電腦就會陷入「無窮迴圈（當機卡死）」！"
        },
        {
            "order_index": 12,
            "title": "串列 (List) — 冒險背包的百寶袋",
            "category": "list",
            "cat_name": "串列與字典",
            "cat_class": "cat-data",
            "level": "★★★ 進階",
            "description": "當我們有一大堆資料（例如買下的所有土地清單）想放在同一個變數裡，就要用串列！串列使用中括號 [ ]，裡面的東西用逗號隔開。想要拿出裡面的東西，只要在中括號填入編號（索引 Index）。",
            "code_example": "bag = [\"魔法藥水\", \"免稅卡\", \"強制收購券\"]\nprint(bag[0])        # 印出第 1 個道具：\"魔法藥水\"\nbag.append(\"遙控骰子\") # 在背包最後面塞入新道具！\nprint(len(bag))      # len() 可以量出背包裡現在有 4 個道具",
            "tip": "電腦的世界從 0 開始起算！第一個東西編號是 [0]，第二個是 [1]；如果你跟電腦要 bag[99]，它會抱怨 IndexError 找不到！"
        },
        {
            "order_index": 13,
            "title": "自訂函式 (def) — 自己發明魔法大招",
            "category": "func",
            "cat_name": "自訂函式",
            "cat_class": "cat-func",
            "level": "★★★ 進階",
            "description": "如果有一段很長很複雜的計算（例如：過路費要根據天氣、AQI 和房子樓層來加成），每次用到都要重寫幾十行會累死。我們可以用 def 把這套公式打包成一個「魔法技能」，以後只要呼叫它的名字，它就會自動幫我們算好並用 return 交出答案！",
            "code_example": "def calc_toll(base_price, floors):\n    total = base_price * (1 + (floors - 1) * 0.5)\n    return total  # 將算好的過路費交還給呼叫的人\n\n# 呼叫大招：原價 1000、蓋到 3 樓\nprint(\"應收過路費：\", calc_toll(1000, 3))",
            "tip": "定義函式 (def) 就像是在筆記本上記下配方，它「並不會主動執行」，直到你在後面呼叫它的名字 calc_toll(...)，它才會動手算！"
        },
        {
            "order_index": 14,
            "title": "四大新手常見大魔王 Bug 大解密",
            "category": "bug",
            "cat_name": "除錯急救包",
            "cat_class": "cat-cond",
            "level": "★★★ 必讀",
            "description": "寫程式遇到紅字報錯千萬不要慌！看看是哪一隻魔王在搗蛋：\n1. SyntaxError（語法錯誤）：漏了冒號 :、括號沒關緊、引號只有一半。\n2. NameError（名字錯誤）：單字拼錯了（如 prnt）、變數還沒宣告就偷用、文字忘記穿引號衣服。\n3. TypeError（型態錯誤）：把文字拿去跟數字相加（例如 \"100\" + 50）。\n4. IndentationError（縮排錯誤）：該空 4 格的地方沒空，或是空格用得參差不齊。",
            "code_example": "# 遇見 Bug 時的除錯三步驟：\n# 1. 沉著冷靜看最後一行的報錯名稱\n# 2. 找到它提示的錯誤行號 (Line X)\n# 3. 檢查是不是漏冒號、打錯字或空格不對！",
            "tip": "在我們的遊戲對局中，如果不小心寫錯程式碼，AI 虛擬導師也會根據這些錯誤型態，動態給你 50 字內的專屬提示喔！"
        }
    ]

    for item in starter_lessons:
        card = models.HandbookCard(**item)
        db.add(card)
    db.commit()
    print("✅ 已成功自動初始化「零基礎 Python 學習手冊」完整資料庫教材！")