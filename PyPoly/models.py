from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Float, Boolean
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
    category = Column(String(50))    # basic / advanced（遊戲模式）
    topic = Column(String(50))       # 語法主題（變數/迴圈/條件判斷/函式…）需求⑨結算統計用
    difficulty = Column(String(50))  # easy / normal / hard
    content = Column(String(500))    # 題目內容
    opt1 = Column(String(200))       # 選項 1
    opt2 = Column(String(200))       # 選項 2
    opt3 = Column(String(200))       # 選項 3
    opt4 = Column(String(200))       # 選項 4 (需求①：新增第四選項)
    answer = Column(Integer)         # 儲存 1, 2, 3 或 4

# models.py
class CountryScenario(Base):
    __tablename__ = "scenarios"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))           # 地名 (如：中興新村)
    township = Column(String(20))       # 行政區 (如：南投市)
    scenario = Column(Text)             # 故事敘事文字
    # ⚠️ 原本這裡有 skybox_url 欄位，已移除。
    #    存檔名容易與實際檔案脫節（實測 5 筆全部指向不存在的檔案，導致整局卡死），
    #    現改由 /game/map_config 依 id 推導出 "scenarios/{id}.jpg"，
    #    圖檔放 static/assets/skyboxes/scenarios/ 底下，資料庫不再持有檔名。
    
    # 💰 基礎經濟數值
    base_price = Column(Integer, default=1000) # 基本收購價
    base_toll = Column(Integer, default=200)  # 基本過路費
    
    # 🔗 Open Data 關聯 ID (用於抓取政府人流/AQI 測站)
    api_station_name = Column(String(50))


# ==========================================================
# 需求⑨：遊戲結算相關資料表
# ==========================================================

class GameRecord(Base):
    """每人每局的結算摘要 (排行榜用)。一場遊戲、一位玩家 = 一筆。"""
    __tablename__ = "game_records"

    id = Column(Integer, primary_key=True, index=True)
    room_code = Column(String(20), index=True)        # 房間代碼 (辨識同一場對局)
    username = Column(String(50), index=True)         # 玩家帳號
    final_money = Column(Integer, default=0)          # 最終金錢 (排行榜分數)
    rank = Column(Integer, default=0)                 # 名次 (1 = 冠軍)
    is_winner = Column(Boolean, default=False)        # 是否獲勝
    total_questions = Column(Integer, default=0)      # 本局答題總數
    correct_count = Column(Integer, default=0)        # 答對題數 (答對率 = correct/total)
    avg_answer_sec = Column(Float, default=0)         # 答題平均用時 (秒)
    top_category = Column(String(50))                 # 最常出現語法 (如 if-else / Variables)
    jump_count = Column(Integer, default=0)           # 實體動作次數 (開合跳等)
    laps = Column(Integer, default=0)                 # 完成回合數
    created_at = Column(DateTime, default=datetime.utcnow)


class GameAnswerLog(Base):
    """每一題的作答明細 (報表/答錯回顧用)。用來計算答對率、最常出現語法、平均用時。"""
    __tablename__ = "game_answer_logs"

    id = Column(Integer, primary_key=True, index=True)
    room_code = Column(String(20), index=True)        # 房間代碼
    username = Column(String(50), index=True)         # 玩家帳號
    # question_id 僅作參考，不設外鍵：seed_data 會清空重建 questions，故另存快照
    question_id = Column(Integer)                     # 對應 questions.id (參考用)
    category = Column(String(50))                     # 題目語法分類 (快照)
    question_text = Column(String(500))               # 題目內容 (快照，供答錯回顧)
    chosen_answer = Column(Integer)                   # 玩家所選 (1~4)
    correct_answer = Column(Integer)                  # 正確答案 (1~4)
    is_correct = Column(Boolean, default=False)       # 是否答對
    answer_sec = Column(Float, default=0)             # 該題作答用時 (秒)
    created_at = Column(DateTime, default=datetime.utcnow)