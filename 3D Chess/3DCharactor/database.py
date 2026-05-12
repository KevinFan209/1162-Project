from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pypoly.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
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