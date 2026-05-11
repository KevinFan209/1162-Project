from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 🏆 XAMPP MySQL 連線設定
# 帳號：root | 密碼：空 | 主機：localhost | 資料庫：pypoly_db
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost/pypoly_db"

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