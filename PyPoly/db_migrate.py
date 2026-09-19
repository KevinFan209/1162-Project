# -*- coding: utf-8 -*-
"""資料庫欄位遷移。

為什麼需要這支腳本：
database.py 用的是 SQLAlchemy 的 create_all()，它只會建立「不存在的資料表」，
不會替既有資料表補上新欄位。所以當 models.py 新增欄位後，已經有資料庫的人
拉到新版會在每一次查詢時撞上 "Unknown column"——整個後端等於掛掉。

處理兩類事情：
  · MIGRATIONS：新增欄位（users 的角色外觀、questions 的題型與程式碼題欄位）
  · post_migrate()：改型別與回填既有資料（content 放寬成 TEXT、qtype 回填）

用法（在 PyPoly 目錄下）：
    python db_migrate.py

刻意設計成可重複執行：每個欄位都先問過 information_schema，已存在就跳過，
所以不確定自己跑過沒有的時候，再跑一次是安全的。
"""
import sys
from sqlalchemy import text

sys.stdout.reconfigure(encoding="utf-8")

import database

# (資料表, 欄位, 欄位定義)
MIGRATIONS = [
    ("users", "character_data",       "JSON NULL"),
    ("users", "character_created_at", "DATETIME NULL"),
    ("users", "character_updated_at", "DATETIME NULL"),

    # 題型改版：原本只靠 category 分基礎/進階，進階底下卻同時有
    # 「手勢比數字」與「手打程式碼」兩種題型，欄位需求互相衝突。
    ("questions", "qtype",              "VARCHAR(20) NOT NULL DEFAULT 'choice'"),
    ("questions", "starter_code",       "TEXT NULL"),
    ("questions", "expected_output",    "TEXT NULL"),
    ("questions", "reference_solution", "TEXT NULL"),
    ("questions", "time_limit_sec",     "INT NULL"),
    ("questions", "max_attempts",       "INT NULL"),

    # 棋盤真實地理化：記錄每個地點的座標與海拔，之後用來決定
    # 棋盤格的相對位置與高度（目前 BOARD_LAYOUT 是寫死的固定形狀）。
    # 資料由使用者之後自行查找並匯入，這裡只先建欄位。
    ("scenarios", "latitude",     "DECIMAL(9,6) NULL"),
    ("scenarios", "longitude",    "DECIMAL(9,6) NULL"),
    ("scenarios", "elevation_m",  "INT NULL"),
]

# 除了「加欄位」之外還要做的事：改型別與回填既有資料。
# 同樣設計成可重複執行——每一項都先確認現況再決定要不要動。


def column_exists(db, table: str, column: str) -> bool:
    row = db.execute(text("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c
    """), {"t": table, "c": column}).scalar()
    return bool(row)


def column_type(db, table: str, column: str) -> str:
    return db.execute(text("""
        SELECT DATA_TYPE FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c
    """), {"t": table, "c": column}).scalar() or ""


def post_migrate(db) -> int:
    """欄位補齊之後才能做的事：改型別 + 回填 qtype。"""
    done = 0

    # 1) content 放寬成 TEXT。程式碼題的敘述常會附一段程式碼，
    #    VARCHAR(500) 塞不下，而且超過長度時 MySQL 會直接報錯讓整筆存不進去。
    if column_type(db, "questions", "content") == "varchar":
        db.execute(text("ALTER TABLE questions MODIFY content TEXT"))
        db.commit()
        print("  [修改] questions.content VARCHAR(500) -> TEXT")
        done += 1
    else:
        print("  [跳過] questions.content 已是 TEXT")

    # 2) 回填 qtype。舊資料的判斷依據：
    #      category='basic'                  -> 四選一
    #      category='advanced' 且無任何選項   -> 手勢比數字
    #    只填還沒被分類過的（qtype 為空字串或 NULL），
    #    所以在後台改過題型的資料不會被蓋回去。
    r1 = db.execute(text("""
        UPDATE questions SET qtype='choice'
        WHERE category='basic' AND (qtype IS NULL OR qtype='')
    """)).rowcount
    r2 = db.execute(text("""
        UPDATE questions SET qtype='gesture'
        WHERE category='advanced' AND opt1 IS NULL
          AND (qtype IS NULL OR qtype='' OR qtype='choice')
    """)).rowcount
    db.commit()
    if r1 or r2:
        print(f"  [回填] qtype: choice {r1} 筆、gesture {r2} 筆")
        done += 1
    else:
        print("  [跳過] qtype 已回填過")

    return done


def main() -> int:
    db = database.SessionLocal()
    added = skipped = 0
    try:
        for table, column, ddl in MIGRATIONS:
            if column_exists(db, table, column):
                print(f"  [跳過] {table}.{column} 已存在")
                skipped += 1
                continue
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            db.commit()
            print(f"  [新增] {table}.{column} {ddl}")
            added += 1

        print()
        post_migrate(db)
    except Exception as e:
        db.rollback()
        print(f"  [失敗] {e}")
        return 1
    finally:
        db.close()

    print(f"\n完成：新增 {added} 個欄位，跳過 {skipped} 個。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
