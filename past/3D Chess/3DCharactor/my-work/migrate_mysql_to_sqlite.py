"""
從 XAMPP MySQL (beerich_db) 搬移資料到 SQLite (beerich.db)
執行前請確認 XAMPP 的 MySQL 正在運行。
執行方式：venv\Scripts\python.exe migrate_mysql_to_sqlite.py
"""
import sys
import os

try:
    import pymysql
except ImportError:
    print("錯誤：找不到 pymysql，請先執行：")
    print("  venv\\Scripts\\pip install pymysql")
    sys.exit(1)

# 連接 MySQL
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DB = "beerich_db"

print("=" * 50)
print("  MySQL → SQLite 資料搬移工具")
print("=" * 50)

print("\n[1/3] 連接 MySQL...")
try:
    conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
    )
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    conn.close()
    print(f"  讀取到 {len(rows)} 筆使用者資料")
except Exception as e:
    print(f"  錯誤：無法連接 MySQL：{e}")
    print("  請確認 XAMPP MySQL 正在運行")
    sys.exit(1)

if not rows:
    print("\n  MySQL 裡沒有資料，不需要搬移。")
    sys.exit(0)

print("\n[2/3] 建立 SQLite 資料庫...")
# 直接使用 SQLAlchemy 建立 SQLite 並寫入
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beerich.db")

if os.path.exists(_DB_PATH):
    confirm = input(f"\n  警告：{_DB_PATH} 已存在，繼續會覆蓋重複的帳號。\n  繼續？(y/n): ")
    if confirm.strip().lower() != "y":
        print("  已取消。")
        sys.exit(0)

from models import Base, User

engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

print("\n[3/3] 寫入資料...")
success, skip = 0, 0
for row in rows:
    exists = db.query(User).filter(User.username == row["username"]).first()
    if exists:
        print(f"  略過（已存在）：{row['username']}")
        skip += 1
        continue
    user = User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        role=row["role"],
        created_at=row["created_at"],
        is_online=0,
        last_active=row["last_active"],
    )
    db.add(user)
    success += 1

db.commit()
db.close()

print("\n" + "=" * 50)
print(f"  完成！成功搬移 {success} 筆，略過 {skip} 筆")
print(f"  SQLite 位置：{_DB_PATH}")
print("=" * 50)
