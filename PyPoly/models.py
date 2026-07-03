from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
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


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50))    # basic / advanced
    difficulty = Column(String(50))  # easy / normal / hard
    content = Column(String(500))    # 題目內容
    opt1 = Column(String(200))       # 選項 1
    opt2 = Column(String(200))       # 選項 2
    opt3 = Column(String(200))       # 選項 3
    answer = Column(Integer)         # 儲存 1, 2, 或 3

# models.py
class CountryScenario(Base):
    __tablename__ = "scenarios"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))           # 地名 (如：中興新村)
    township = Column(String(20))       # 行政區 (如：南投市)
    scenario = Column(Text)             # 故事敘事文字
    skybox_url = Column(String(100))    # 360度圖片檔名
    
    # 💰 基礎經濟數值
    base_price = Column(Integer, default=1000) # 基本收購價
    base_toll = Column(Integer, default=200)  # 基本過路費
    
    # 🔗 Open Data 關聯 ID (用於抓取政府人流/AQI 測站)
    api_station_name = Column(String(50))