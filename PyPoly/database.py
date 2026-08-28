import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 🏆 資料庫連線設定
#
# 預設是本機 XAMPP：帳號 root、密碼空、主機 localhost、資料庫 pypoly_db。
# 直接在自己電腦跑的人不必做任何事，行為與以前完全相同。
#
# 之所以改成可由環境變數覆寫，是因為：
#   1. 在 Docker 裡「localhost」指的是容器自己，連不到資料庫服務，
#      必須改指向 compose 的服務名（例如 mysql+pymysql://root:pypoly@db/pypoly_db）。
#   2. MySQL root 有設密碼的人，以前只能直接改這一行（改了容易誤 commit 進版控）。
#
# ⚠️ .env.example 一直宣稱支援 DATABASE_URL，但先前這裡並沒有讀取任何
#    環境變數，那句說明是假的——現在才真的成立。
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:@localhost/pypoly_db",
)

# 建立連線引擎
# 🚀 優化重點：
# 1. pool_size: 提高基礎連線數到 20
# 2. max_overflow: 允許額外增加 30 個臨時連線
# 3. pool_timeout: 延長等待時間至 60 秒，避免瞬間併發時報錯
# 4. pool_recycle: 每半小時自動回收連線，防止 MySQL 端的斷開
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
    pool_recycle=1800,
    pool_pre_ping=True
)

# 建立 Session 類別
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建立模型基底類別
Base = declarative_base()

# 🏆 FastAPI 的相依注入函式
# ⚠️ 關鍵：finally 區塊的 db.close() 絕對不能拿掉
# 它是將連線還給連線池（Pool）的唯一方法
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()