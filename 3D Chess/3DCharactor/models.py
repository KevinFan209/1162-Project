from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="player") 
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 🏆 新增：在線狀態 (0: 離線, 1: 在線)
    is_online = Column(Integer, default=0)
    # 🏆 建議新增：紀錄最後活動時間 (這對解決第三點「斷線偵測」很有用)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)