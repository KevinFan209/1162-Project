# -*- coding: utf-8 -*-
"""資料庫欄位遷移。

為什麼需要這支腳本：
database.py 用的是 SQLAlchemy 的 create_all()，它只會建立「不存在的資料表」，
不會替既有資料表補上新欄位。所以當 models.py 新增欄位後，已經有資料庫的人
拉到新版會在每一次查詢時撞上 "Unknown column"——整個後端等於掛掉。

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
]


def column_exists(db, table: str, column: str) -> bool:
    row = db.execute(text("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c
    """), {"t": table, "c": column}).scalar()
    return bool(row)


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
