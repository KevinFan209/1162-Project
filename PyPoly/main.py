# 🏆 UTF-8 輸出保險：避免在 cp950(繁中) 主控台下，含 emoji 的 print 造成 UnicodeEncodeError 讓請求崩潰
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models, auth_utils, database
import air_quality  # 🏆 環境部 AQI（移植自 origin/vamos 的 990e880）
import temperature  # 🏆 中央氣象署即時氣溫（白名單 64 景點）
import learn_ai     # 🏆 AI 導師分析（learn.html 右側面板，交接給組員維護）
import board_geo    # 🏆 棋盤格子座標依真實經緯度/海拔動態換算
# ⚠️ 這裡原本有 cv2，但全檔沒有任何一處用到它。
#    它唯一的作用是讓 mediapipe 相依的 opencv（149MB）變成必裝，
#    而 mediapipe 本身也沒有被任何 .py import——手勢辨識是跑在瀏覽器端的。
import smtplib, random, requests, base64
import numpy as np
from email.mime.text import MIMEText
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import case, text
from game_start import GestureDetector
import asyncio
import socketio
from fastapi import Query
import game_start # 🏆 關鍵新增：把整個模組抓進來，準備竄改它的全域變數
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError  # 🏆 註冊時攔截 email/username 唯一鍵衝突
from collections import Counter  # 🏆 需求⑨：統計最常出現語法
# main.py
import os
import json   # 🏆 角色外觀的大小驗證用
import base64
from fastapi.staticfiles import StaticFiles
from PIL import Image # 需安裝 pillow: pip install Pillow
import io
from dotenv import load_dotenv
from fastapi import Request
from openai import AsyncOpenAI
from fastapi.responses import FileResponse
import seed_handbook

# 🏆 讀取 PyPoly/.env（機敏設定：SENDER_EMAIL / SENDER_PASSWORD / SECRET_KEY 等）
load_dotenv()

# --- 請加入這段 ---
# 初始化 OpenAI 客戶端
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# 如果沒有設定 API Key，先設為 None 避免伺服器啟動直接崩潰
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# ------------------



# 🏆 自動建立 MySQL 資料庫表格
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")

sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

AVATAR_DIR = os.path.join("static", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs("models", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/models", StaticFiles(directory="models"), name="models")

# 🏆 終極 Favicon 強制路由：只要瀏覽器要圖示，一律塞這張給它！
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # 請確保你的蜜蜂圖片真的是放在 static 資料夾底下，且檔名叫 logo.jpg
    return FileResponse("static/favicon.jpg")


# 🏆 靜態檔一律要求瀏覽器重新驗證。
#
# StaticFiles 只回 last-modified 與 etag，不回 Cache-Control。沒有明確
# 有效期時，瀏覽器會套用「啟發式快取」（RFC 9111 §4.2.2）——一般取
# 「檔案最後修改到現在」的 10% 當作新鮮期，期間內連問都不問伺服器。
# 於是改完程式碼重開伺服器，畫面還是舊的，要 Ctrl+Shift+R 才看得到；
# 在不同分支的 worktree 之間切換時尤其明顯，因為網址完全一樣。
#
# no-cache 不是不快取（那是 no-store）：瀏覽器照樣存，但每次都必須拿
# etag 回來問一次。沒改動就回 304，只有幾百 bytes，成本很低。
@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/static/", "/models/")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response

# 🏆 用來存放所有線上房間的「記憶體筆記本」
# 只要伺服器沒關，房間資料都會存在這
active_rooms = {}

land_ownership = {}

# 🏆 刪房時一併清掉該房的擲骰暫存（dice_order_results / room_dice_data 於檔案下方定義，
#    此函式在請求時才執行，屆時兩個全域字典已存在）。同時清 code 與其大寫版以防鍵不一致。
def _clear_room_dice_state(code: str):
    for key in {code, code.upper()}:
        dice_order_results.pop(key, None)
        room_dice_data.pop(key, None)


# ==========================================================
# 🏆 殭屍房間回收
# active_rooms 原本只有明確呼叫 leave/delete 才會清除，玩家關掉分頁、當機或
# 網路中斷時房間會永久留著，大廳因此逐漸堆滿別人進不去的滿員房。
# 這裡替每間房記錄最後活躍時間，由背景任務回收長時間沒有動靜的房間。
# ==========================================================
# 60 分鐘沒有任何活動才回收。訂得比一般對局長是刻意的——
# 一局最長可能接近 30 分鐘，中途還可能暫離，寧可晚一點收也不要誤殺進行中的房間。
# 所有 REST 端點與 socket 事件都會更新活躍時間，真正被收掉的必然是沒人在玩的房。
ROOM_IDLE_TIMEOUT = 3600


def touch_room(room: dict):
    """更新房間的最後活躍時間。任何與該房有關的請求或 socket 事件都應呼叫。"""
    if isinstance(room, dict):
        room['last_active'] = datetime.utcnow().timestamp()


def touch_room_by_code(code: str):
    room = active_rooms.get((code or "").upper())
    if room:
        touch_room(room)


def cleanup_idle_rooms():
    """回收超過 ROOM_IDLE_TIMEOUT 沒有活動的房間。"""
    now = datetime.utcnow().timestamp()
    stale = [c for c, r in active_rooms.items()
             if now - r.get('last_active', now) > ROOM_IDLE_TIMEOUT]
    for code in stale:
        active_rooms.pop(code, None)
        _clear_room_dice_state(code)
        sync_room_log(code, "abandoned")
        print(f"🧹 [房間回收] {code} 閒置超過 {ROOM_IDLE_TIMEOUT // 60} 分鐘，已清除")
    return len(stale)


# ==========================================================
# 🏆 房間生命週期紀錄（game_room_logs）
# 集中在這裡處理 upsert，避免五個端點各寫一份而漸漸分歧。
# 自帶 DB session：這些呼叫點多半不是 request handler，
# 不能沿用 Depends(get_db) 的 session。
# ==========================================================
ROOM_OPEN_STATUSES = ("waiting", "gaming")   # 尚未結束、重啟後需要還原的狀態


def sync_room_log(code: str, status: str, room: dict = None):
    """建立或更新該房的生命週期紀錄。同一房號取尚未結束的最新一筆。"""
    if not code:
        return
    code = code.upper()
    db = database.SessionLocal()
    try:
        log = (db.query(models.GameRoomLog)
                 .filter(models.GameRoomLog.room_code == code,
                         models.GameRoomLog.status.in_(ROOM_OPEN_STATUSES))
                 .order_by(models.GameRoomLog.id.desc())
                 .first())

        if log is None:
            if status != "waiting" and room is None:
                return   # 沒有進行中的紀錄又沒有房間資料可建，略過
            log = models.GameRoomLog(room_code=code)
            db.add(log)

        if room:
            log.host = room.get("hostId")
            log.name = room.get("name")
            log.mode = room.get("mode")
            log.difficulty = room.get("difficulty")
            log.win_laps = str(room.get("winLaps", ""))
            log.room_type = room.get("type")
            log.test_mode = bool(room.get("testMode"))

        # 已結束的紀錄不再被改回進行中，避免重複呼叫 finish 造成狀態跳動
        if log.status in ("finished", "abandoned") and status in ROOM_OPEN_STATUSES:
            return

        log.status = status
        if status == "gaming" and log.started_at is None:
            log.started_at = datetime.utcnow()
        if status in ("finished", "abandoned") and log.finished_at is None:
            log.finished_at = datetime.utcnow()

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️ 房間紀錄寫入失敗（{code} → {status}）：{type(e).__name__}: {e}")
    finally:
        db.close()


def restore_rooms_from_db():
    """啟動時把尚未結束的房間還原到 active_rooms。

    先前 active_rooms 只存在記憶體，重啟就整批消失——房間紀錄與進行中的
    對局都救不回來。有了 game_room_logs 之後至少能還原房間本身。
    """
    db = database.SessionLocal()
    try:
        logs = (db.query(models.GameRoomLog)
                  .filter(models.GameRoomLog.status.in_(ROOM_OPEN_STATUSES))
                  .all())
        for log in logs:
            if log.room_code in active_rooms:
                continue
            active_rooms[log.room_code] = {
                "code": log.room_code,
                "hostId": log.host,
                "name": log.name,
                "mode": log.mode,
                "difficulty": log.difficulty,
                "winLaps": log.win_laps,
                "type": log.room_type,
                "testMode": bool(log.test_mode),
                # 還原後 players 一律清空：socket 連線在重啟時已全數斷開，
                # 沿用舊名單會讓房間顯示滿員卻沒有人在裡面。
                "players": [],
                "status": log.status,
                "is_started": log.status == "gaming",
                "last_active": datetime.utcnow().timestamp(),
            }
        if logs:
            print(f"♻️ 已從資料庫還原 {len(logs)} 間未結束的房間")
    except Exception as e:
        print(f"⚠️ 還原房間失敗：{type(e).__name__}: {e}")
    finally:
        db.close()

# 定義接收的資料結構
class RoomSchema(BaseModel):
    hostId: str
    name: str
    mode: str
    difficulty: str
    winLaps: str
    type: str
    code: str
    # 🏆 測試模式：地圖大部分冒險格改為 BLANK，讓一局能快速跑完以驗證結算頁。
    #    存在房間資料裡，客人加入時會從 /rooms/join 回傳的房間 dict 一併取得，
    #    雙方因此拿到同一張地圖。
    testMode: bool = False

@app.on_event("startup")
async def start_cleanup_task():
    # 🏆 先把尚未結束的房間從資料庫還原，重啟不再遺失
    restore_rooms_from_db()

    async def cleanup_loop():
        while True:
            # 建立一個新的資料庫連線來清理
            db = database.SessionLocal()
            try:
                perform_auto_cleanup(db)
            finally:
                db.close()
            # 🏆 一併回收閒置房間，避免大廳堆滿沒人但顯示滿員的殭屍房
            cleanup_idle_rooms()
            # 每 10 秒自動掃描一次
            await asyncio.sleep(10)
    
    # 讓它在背景執行
    asyncio.create_task(cleanup_loop())

# 允許前端本地連線 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允許所有裝置連線
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 設定區 ---
GOOGLE_CLIENT_ID = "174084310746-5nhhblrrd4bii9nd6smf4oqb2a0j1ro1.apps.googleusercontent.com"
ADMIN_EMAILS = ["admin@gmail.com"]

# 📧 Gmail SMTP 設定（改由環境變數提供；請於 PyPoly/.env 填入，切勿寫死於程式碼）
#    ⚠️ 原先寫死的應用程式密碼已移除，請至 Google 帳戶撤銷該密碼並重新產生。
# 檔案上方確認有執行 load_dotenv()
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# 暫存驗證碼
otp_storage: Dict[str, str] = {}

# --- Pydantic 模型 ---
class UserLogin(BaseModel):
    username: str
    password: str

class GoogleTokenRequest(BaseModel):
    access_token: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# --- 核心清理邏輯 (全自動打掃) ---
def perform_auto_cleanup(db: Session):
    # 🏆 設定 60 秒為判定標準（先前被改為 600000000 秒的 debug hack 已還原）
    threshold = datetime.utcnow() - timedelta(seconds=60)

    # 找出那些「在線中」但「超過 60 秒沒說話」的人
    offline_users = db.query(models.User).filter(
        models.User.is_online == 1, 
        models.User.last_active < threshold
    ).all()
    
    if offline_users:
        for u in offline_users:
            u.is_online = 0
            print(f"🧹 [自動清理] 偵測到使用者 {u.username} 超時，已強制登出。")
        db.commit()

# 🏆 供 BackgroundTasks 使用：自帶 DB session，避免沿用 request-scoped session
#    （FastAPI 0.106+ 會在背景任務執行前就關閉 Depends(get_db) 的 session）
def perform_auto_cleanup_bg():
    db = database.SessionLocal()
    try:
        perform_auto_cleanup(db)
    finally:
        db.close()

# --- API 路由 ---

# --- 1. 影像辨識 WebSocket 路由 (串接你的 .py 檔案) ---



# 1. 帳密登入 (含封鎖攔截與重複登入攔截)
@app.post("/auth/login")
def login(user: UserLogin, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    # 登入前先清理一遍
    perform_auto_cleanup(db)
    
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth_utils.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    
    # 🏆 核心修正：檢查是否被封鎖
    if db_user.role == "banned":
        raise HTTPException(status_code=403, detail="您的帳號已被封鎖，請聯繫管理員。")
    
    # 核心防禦：攔截重複登入
    if db_user.is_online == 1:
        raise HTTPException(status_code=403, detail="該帳號已在其他地方登入中，請先登出。")
    
    db_user.is_online = 1
    db_user.last_active = datetime.utcnow()
    db.commit()

    token = auth_utils.create_access_token(data={"sub": db_user.username, "role": db_user.role})
    return {"access_token": token, "role": db_user.role, "username": db_user.username}

# 2. Google 登入 (整合封鎖邏輯)
@app.post("/auth/google_v2")
def google_login_v2(data: GoogleTokenRequest, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    background_tasks.add_task(perform_auto_cleanup_bg)
    
    google_res = requests.get(f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={data.access_token}")
    if google_res.status_code != 200:
        raise HTTPException(status_code=400, detail="Google 驗證失敗")
    
    user_info = google_res.json()
    email = user_info.get('email')
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        username = email.split('@')[0]
        role = "admin" if email in ADMIN_EMAILS else "player"
        user = models.User(username=username, email=email, hashed_password="google_linked", role=role, is_online=1)
        db.add(user)
    else:
        # 🏆 檢查封鎖
        if user.role == "banned":
            raise HTTPException(status_code=403, detail="您的 Google 帳號已被封鎖")
            
        if user.is_online == 1:
            raise HTTPException(status_code=403, detail="此 Google 帳號已在其他地方登入中")
        user.is_online = 1
        
    user.last_active = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    token = auth_utils.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": token, "username": user.username, "role": user.role}

# 3. 心跳機制 (維持在線與 Admin 復活)
@app.post("/auth/heartbeat")
def heartbeat(username: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        user.last_active = datetime.utcnow() # 只更新活動時間
        db.commit()
    return {"status": "alive"}

# 4. 取得我的狀態 (刷新同步 & 封鎖踢出校對)
@app.get("/auth/me")
def get_me(username: str, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    background_tasks.add_task(perform_auto_cleanup_bg)
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")
    
    # 🏆 查詢該玩家是否有加入班級
    class_name = None
    if user.class_id:
        classroom = db.query(models.Classroom).filter(models.Classroom.id == user.class_id).first()
        if classroom:
            class_name = classroom.name

    return {
        "username": user.username, 
        "is_online": user.is_online,
        "role": user.role,
        "email": user.email,
        "class_id": user.class_id,
        "class_name": class_name
    }

# 5. 登出
# --- main.py ---

# 請確保你的 main.py 這行長這樣
# 修改 logout 路由
@app.post("/auth/logout") # 這裡固定用 POST 比較安全
def logout(username: str, db: Session = Depends(database.get_db), confirm: Optional[str] = None): 
    # 🏆 這裡保持不變，但我們要確保前端 fetch 的時候，參數有正確帶上
    if confirm == "true":
        db_user = db.query(models.User).filter(models.User.username == username).first()
        if db_user:
            db_user.is_online = 0
            db.commit()
            print(f"🚪 [正式登出成功] 使用者 {username}")
            return {"status": "success", "message": "Logged out"}
    
    # 如果走到這，代表 confirm 抓到的是 None 或不是 "true"
    print(f"🛡️ [攔截] 收到請求但 confirm 為: {confirm}") 
    return {"status": "ignored"}

@app.post("/auth/verify_and_refresh")
def verify_and_refresh(username: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user: raise HTTPException(status_code=401)
    
    # 強行讓狀態變回在線
    user.is_online = 1
    user.last_active = datetime.utcnow()
    db.commit()
    return {"status": "success"}

# 🏆 管理員權限守衛：解出 JWT 的 username 後，查 DB 確認 role == admin 才放行
def require_admin(authorization: str = Header(None), db: Session = Depends(database.get_db)):
    username = auth_utils.get_current_user(authorization)  # 未帶/無效 token 會拋 401
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理員權限")
    return user

# 6. 管理員：獲取所有用戶 (加權排序)
# 6. 管理員：獲取所有用戶 (加權排序 + 班級資訊)
@app.get("/admin/users")
def get_all_users(db: Session = Depends(database.get_db), admin: models.User = Depends(require_admin)):
    perform_auto_cleanup(db)
    
    # 🏆 排序優先級：admin > teacher > player
    role_priority = case(
        (models.User.role == 'admin', 2),
        (models.User.role == 'teacher', 1),
        else_=0
    )
    
    users = db.query(models.User).order_by(
        role_priority.desc(),
        models.User.is_online.desc(),
        models.User.username.asc()
    ).all()

    # 撈出所有班級名稱對照表
    classrooms = db.query(models.Classroom).all()
    class_map = {c.id: c.name for c in classrooms}
    
    return [
        {
            "username": u.username, 
            "email": u.email, 
            "role": u.role, 
            "is_online": u.is_online,
            "class_id": u.class_id,
            "class_name": class_map.get(u.class_id) if u.class_id else None
        } for u in users
    ]

# 🏆 新增：管理員變更用戶角色 (封鎖/解封)
@app.put("/admin/users/{target_username}/role")
def update_user_role(target_username: str, data: dict, db: Session = Depends(database.get_db), admin: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.username == target_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到該用戶")
    
    # 禁止管理員封鎖自己
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能更改管理員權限")

    new_role = data.get("role")
    user.role = new_role
    
    # 🏆 核心邏輯：如果是封鎖，強制變 0 讓他在 5 秒內被踢出
    if new_role == "banned":
        user.is_online = 0
        
    db.commit()
    return {"message": "success"}

# ==========================================================
# 🏆 題庫後台 CRUD（給 question.html 用）
#
# qtype 決定哪些欄位有意義，這也是驗證的分流依據：
#   choice  四選一     opt1~opt4 必填、answer 1~4
#   gesture 手勢比數字  answer 1~9（手勢辨識只認得 1~9）、不可有選項
#   code    手打程式碼  expected_output 與 reference_solution 必填、
#                      不可有 answer 也不可有選項
#
# 沒有這層驗證的話，後台存得出一筆「code 題但沒有參考解答」，
# 而遊戲中不會報錯，只會安靜地讓 AI 拿不到判分依據去亂判。
# ==========================================================

QTYPES = ("choice", "gesture", "code")
DIFFICULTIES = ("easy", "normal", "hard")
CATEGORIES = ("basic", "advanced")


class QuestionPayload(BaseModel):
    category: str
    qtype: str
    topic: str
    difficulty: str
    content: str
    opt1: Optional[str] = None
    opt2: Optional[str] = None
    opt3: Optional[str] = None
    opt4: Optional[str] = None
    answer: Optional[int] = None
    starter_code: Optional[str] = None
    expected_output: Optional[str] = None
    reference_solution: Optional[str] = None
    time_limit_sec: Optional[int] = None
    max_attempts: Optional[int] = None


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def validate_question(q: QuestionPayload) -> dict:
    """依 qtype 檢查並正規化，回傳可直接塞進 models.Question 的 dict。

    刻意不用 pydantic 的 validator：錯誤訊息要中文、而且要一次列出全部問題，
    前端才能一口氣標在對應欄位上，不必讓使用者改一個存一次。
    """
    errors = []
    if q.category not in CATEGORIES:
        errors.append("遊戲模式只能是 " + " / ".join(CATEGORIES))
    if q.qtype not in QTYPES:
        errors.append("題型只能是 " + " / ".join(QTYPES))
    if q.difficulty not in DIFFICULTIES:
        errors.append("難度只能是 " + " / ".join(DIFFICULTIES))
    if _blank(q.topic):
        errors.append("語法主題不可空白")
    if _blank(q.content):
        errors.append("題目內容不可空白")

    data = q.model_dump()
    opts = [q.opt1, q.opt2, q.opt3, q.opt4]

    if q.qtype == "choice":
        missing = [str(i + 1) for i, o in enumerate(opts) if _blank(o)]
        if missing:
            errors.append("選擇題四個選項都必填，缺少選項 " + "、".join(missing))
        if q.answer is None or not 1 <= q.answer <= 4:
            errors.append("選擇題的正解必須是 1~4")
        # 用不到的程式碼題欄位一律清掉，避免改過題型之後留下髒資料
        for f in ("starter_code", "expected_output", "reference_solution",
                  "time_limit_sec", "max_attempts"):
            data[f] = None

    elif q.qtype == "gesture":
        if q.answer is None or not 1 <= q.answer <= 9:
            errors.append("手勢題的答案必須是 1~9（手勢辨識只支援 1~9）")
        if any(not _blank(o) for o in opts):
            errors.append("手勢題不應該有選項")
        for f in ("opt1", "opt2", "opt3", "opt4", "starter_code",
                  "expected_output", "reference_solution",
                  "time_limit_sec", "max_attempts"):
            data[f] = None

    elif q.qtype == "code":
        if _blank(q.expected_output):
            errors.append("程式碼題必須填寫預期輸出（AI 判分的依據）")
        if _blank(q.reference_solution):
            errors.append("程式碼題必須填寫參考解答（AI 判分的依據）")
        if any(not _blank(o) for o in opts):
            errors.append("程式碼題不應該有選項")
        if q.answer is not None:
            errors.append("程式碼題不使用 answer 欄位")
        for f in ("opt1", "opt2", "opt3", "opt4"):
            data[f] = None
        data["answer"] = None
        # 前端原本把這兩個值寫死成 300 秒 / 3 次，這裡沿用為預設
        data["time_limit_sec"] = q.time_limit_sec or 300
        data["max_attempts"] = q.max_attempts or 3
        if data["time_limit_sec"] <= 0:
            errors.append("作答時限必須大於 0 秒")
        if data["max_attempts"] <= 0:
            errors.append("可驗證次數必須大於 0")

    if errors:
        raise HTTPException(status_code=400, detail="；".join(errors))

    data["topic"] = data["topic"].strip()
    data["content"] = data["content"].strip()
    return data


def question_to_dict(q: models.Question) -> dict:
    """後台用的完整表示。"""
    return {
        "id": q.id,
        "category": q.category,
        "qtype": q.qtype or "choice",
        "topic": q.topic,
        "difficulty": q.difficulty,
        "content": q.content,
        "opt1": q.opt1, "opt2": q.opt2, "opt3": q.opt3, "opt4": q.opt4,
        "answer": q.answer,
        "starter_code": q.starter_code,
        "expected_output": q.expected_output,
        "reference_solution": q.reference_solution,
        "time_limit_sec": q.time_limit_sec,
        "max_attempts": q.max_attempts,
        "class_id": getattr(q, "class_id", None),
        "created_by": getattr(q, "created_by", None),
    }


@app.get("/admin/questions")
def list_questions(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    qtype: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(require_admin),
):
    query = db.query(models.Question)
    if category:
        query = query.filter(models.Question.category == category)
    if difficulty:
        query = query.filter(models.Question.difficulty == difficulty)
    if topic:
        query = query.filter(models.Question.topic == topic)
    if qtype:
        query = query.filter(models.Question.qtype == qtype)
    if q and q.strip():
        query = query.filter(models.Question.content.like("%" + q.strip() + "%"))

    rows = query.order_by(models.Question.id.desc()).all()
    return {"total": len(rows), "items": [question_to_dict(r) for r in rows]}


@app.get("/admin/questions/meta")
def question_meta(db: Session = Depends(database.get_db),
                  admin: models.User = Depends(require_admin)):
    """下拉選單要用的選項。

    topic 一律從現有資料撈，不在前端寫死——question.html 原本寫死
    Variables / Loops，但資料庫裡其實是中文主題，兩邊早就對不上了。
    """
    topics = [t for (t,) in db.query(models.Question.topic)
              .filter(models.Question.topic.isnot(None))
              .distinct().order_by(models.Question.topic).all()]
    rows = db.query(models.Question.qtype,
                    func.count(models.Question.id)).group_by(
                        models.Question.qtype).all()
    return {
        "topics": topics,
        "qtypes": list(QTYPES),
        "difficulties": list(DIFFICULTIES),
        "categories": list(CATEGORIES),
        "counts": {(qt or "choice"): n for qt, n in rows},
    }


@app.post("/admin/questions")
def create_question(payload: QuestionPayload,
                    db: Session = Depends(database.get_db),
                    admin: models.User = Depends(require_admin)):
    row = models.Question(**validate_question(payload))
    db.add(row)
    db.commit()
    db.refresh(row)
    return question_to_dict(row)


@app.put("/admin/questions/{question_id}")
def update_question(question_id: int, payload: QuestionPayload,
                    db: Session = Depends(database.get_db),
                    admin: models.User = Depends(require_admin)):
    row = db.query(models.Question).filter(
        models.Question.id == question_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="找不到這一題")
    for k, v in validate_question(payload).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return question_to_dict(row)


@app.delete("/admin/questions/{question_id}")
def delete_question(question_id: int,
                    db: Session = Depends(database.get_db),
                    admin: models.User = Depends(require_admin)):
    row = db.query(models.Question).filter(
        models.Question.id == question_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="找不到這一題")
    db.delete(row)
    db.commit()
    return {"message": "success", "id": question_id}


# 8. 註冊與 ID 檢查
@app.get("/auth/check-id")
def check_id(username: str, db: Session = Depends(database.get_db)):
    exists = db.query(models.User).filter(models.User.username == username).first() is not None
    return {"exists": exists}

@app.post("/auth/register")
def register(user: UserCreate, db: Session = Depends(database.get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="ID 已被使用")
    # 🏆 email 在 models.User 有 unique 約束，若不先檢查，重複時會由 DB 丟
    #    IntegrityError 而變成 500（前端會誤顯示為「伺服器連線失敗」）
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="此信箱已被註冊")
    user_role = "admin" if user.email in ADMIN_EMAILS else "player"
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=auth_utils.get_password_hash(user.password),
        role=user_role,
        is_online=0
    )
    db.add(new_user)
    # 🏆 保險：兩個請求同時通過上面的檢查時，仍由唯一鍵擋下，轉成 400 而非 500
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="帳號或信箱已被使用")
    return {"message": "success"}

# 📧 寄送 OTP 驗證碼到指定信箱（Gmail SMTP, STARTTLS）
def send_otp_email(to_email: str, otp: str):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise HTTPException(status_code=500, detail="郵件服務未設定（請於 .env 填入 SENDER_EMAIL / SENDER_PASSWORD）")
    msg = MIMEText(
        f"您的 PyPoly 密碼重設驗證碼為：{otp}\n\n此驗證碼供重設密碼使用，若非本人操作請忽略本信。",
        "plain", "utf-8"
    )
    msg["Subject"] = "PyPoly 密碼重設驗證碼"
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        print(f"📧 已寄送驗證碼至 {to_email}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 寄送驗證碼失敗: {e}")
        raise HTTPException(status_code=500, detail="驗證碼寄送失敗，請稍後再試")

# 9. 忘記密碼邏輯
@app.post("/auth/forgot-password")
def forgot_password(req: dict, db: Session = Depends(database.get_db)):
    email = req.get("email")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user: raise HTTPException(status_code=404)
    otp = str(random.randint(100000, 999999))
    otp_storage[email] = otp
    send_otp_email(email, otp)
    return {"message": "sent"}

# 10. 重設密碼：驗證 OTP 後更新密碼（前端 forgot.html 送 {email, code, new_password}）
@app.post("/auth/reset-password")
def reset_password(req: dict, db: Session = Depends(database.get_db)):
    email = req.get("email")
    code = req.get("code")
    new_password = req.get("new_password")
    if not email or not code or not new_password:
        raise HTTPException(status_code=400, detail="缺少必要欄位")
    saved = otp_storage.get(email)
    if not saved or saved != code:
        raise HTTPException(status_code=400, detail="驗證碼錯誤或已失效")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")
    user.hashed_password = auth_utils.get_password_hash(new_password)
    db.commit()
    otp_storage.pop(email, None)  # 用過即失效
    print(f"🔑 使用者 {user.username} 已重設密碼")
    return {"message": "success"}


# ==========================================================
# 個人資料修改（供 static/profile.html 使用）
# ==========================================================

class ProfileUpdate(BaseModel):
    new_username: str
    new_email: Optional[str] = None
    email_otp: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None


# 11. 寄驗證碼到「新信箱」（換 email 前先證明本人收得到該信箱）
@app.post("/auth/send-otp-new-email")
def send_otp_new_email(req: dict, db: Session = Depends(database.get_db)):
    email = (req.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="請先輸入新的 Email")
    # email 於 models.User 有 unique 約束，先擋掉才不會等到 update 時才失敗
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="此信箱已被其他帳號使用")
    otp = str(random.randint(100000, 999999))
    otp_storage[email] = otp
    send_otp_email(email, otp)   # 未設定 SENDER_* 時會回 500 並附上提示訊息
    return {"message": "sent"}


# 12. 更新個人資料：ID / Email(需 OTP) / 密碼(需舊密碼)
#     前端 profile.html 以 PUT 呼叫，成功後用回傳的 access_token 與 username 覆蓋 localStorage
@app.put("/auth/update-profile")
def update_profile(
    data: ProfileUpdate,
    authorization: str = Header(None),
    db: Session = Depends(database.get_db),
):
    current_username = auth_utils.get_current_user(authorization)  # 無效 token 會拋 401
    user = db.query(models.User).filter(models.User.username == current_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")

    new_username = (data.new_username or "").strip()
    new_email = (data.new_email or "").strip()
    new_password = data.new_password or ""

    username_changed = bool(new_username) and new_username != user.username
    email_changed = bool(new_email) and new_email != user.email

    # ---- 先全部驗證，任何一項不過就不寫入，避免只改到一半 ----
    if not new_username:
        raise HTTPException(status_code=400, detail="使用者 ID 不能為空")

    # ---- 驗證全過，才實際寫入 ----
    if username_changed:
        # 🏆 新增這兩行：如果老師改了名字(ID)，一併更新他名下班級與通知紀錄的老師名稱
        db.query(models.Classroom).filter(models.Classroom.teacher_username == current_username).update({"teacher_username": new_username})
        db.query(models.TeacherAuditLog).filter(models.TeacherAuditLog.teacher_username == current_username).update({"teacher_username": new_username})
        user.username = new_username

    if email_changed:
        if db.query(models.User).filter(models.User.email == new_email).first():
            raise HTTPException(status_code=400, detail="此信箱已被其他帳號使用")
        saved = otp_storage.get(new_email)
        if not saved or not data.email_otp or saved != data.email_otp.strip():
            raise HTTPException(status_code=400, detail="信箱驗證碼錯誤或已失效")

    if new_password:
        if user.hashed_password == "google_linked":
            raise HTTPException(status_code=400, detail="Google 登入的帳號請由 Google 管理密碼")
        if not data.old_password or not auth_utils.verify_password(data.old_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="目前密碼不正確")

    # ---- 驗證全過，才實際寫入 ----
    if username_changed:
        user.username = new_username
    if email_changed:
        user.email = new_email
        otp_storage.pop(new_email, None)  # 用過即失效
    if new_password:
        user.hashed_password = auth_utils.get_password_hash(new_password)
    user.last_active = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="ID 或信箱已被使用")

    print(f"✏️ 使用者 {current_username} 已更新個人資料 -> {user.username}")
    # username 可能已變更，必須重新簽發 token（sub 帶的是 username）
    token = auth_utils.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": token, "username": user.username, "role": user.role}


# ==========================================================
# 角色外觀（users.character_data）
#
# 只存「配方」不存「成品圖」——外觀完全由 colors 與 features 決定，
# 臉部貼圖由前端的 static/js/character-face.js 即時合成。
# 這讓角色形式日後改版時，舊資料還能重新渲染或轉換。
# ==========================================================

CHARACTER_SCHEMA_VERSION = 1
# 8KB 上限：配方本身約 200 bytes，訂這個上限是為了擋住有人把 base64 圖片
# 塞進來——那會讓這個欄位失去輕量的意義。
CHARACTER_MAX_BYTES = 8 * 1024


def _validate_character(payload: dict) -> dict:
    """檢查並正規化角色配方。

    刻意只驗結構與大小，不逐一檢查色碼格式或五官 ID 是否在白名單內——
    角色形式日後會改，嚴格驗證會擋掉未來的新欄位。
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="角色資料格式錯誤")

    colors = payload.get("colors")
    features = payload.get("features")
    if not isinstance(colors, dict) or not isinstance(features, dict):
        raise HTTPException(status_code=400, detail="角色資料需包含 colors 與 features 兩個物件")

    data = {
        "version": int(payload.get("version") or CHARACTER_SCHEMA_VERSION),
        "colors": colors,
        "features": features,
    }

    size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    if size > CHARACTER_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"角色資料過大（{size} bytes，上限 {CHARACTER_MAX_BYTES}）。"
                   "此欄位只應存放外觀設定，不可放圖片。")
    return data


@app.put("/auth/character")
def save_character(payload: dict, authorization: str = Header(None),
                   db: Session = Depends(database.get_db)):
    """儲存目前登入者的角色外觀。首次寫入會記錄 character_created_at。"""
    username = auth_utils.get_current_user(authorization)   # 無效 token 會拋 401
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")

    data = _validate_character(payload)
    now = datetime.utcnow()
    is_first = user.character_created_at is None

    user.character_data = data
    if is_first:
        user.character_created_at = now
    user.character_updated_at = now
    db.commit()

    print(f"🎨 {username} {'建立' if is_first else '更新'}了角色外觀")
    return {"status": "success", "is_first": is_first,
            "created_at": user.character_created_at, "updated_at": user.character_updated_at}


@app.get("/auth/character")
def get_character(username: str = None, authorization: str = Header(None),
                  db: Session = Depends(database.get_db)):
    """取得角色外觀。

    username 省略時回傳「自己的」（用 token 解身分），這是 game.html 進場
    還原自己外觀的用法；帶 username 則可查他人（大廳／觀戰用）。

    尚未建立角色時回 character=None 而非 404——前端據此決定要不要
    退回 localStorage 的舊資料，回 404 會讓前端誤判為錯誤。
    """
    if not username:
        username = auth_utils.get_current_user(authorization)   # 無效 token 會拋 401

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return {
        "username": user.username,
        "character": user.character_data,
        "created_at": user.character_created_at,
        "updated_at": user.character_updated_at,
    }




class AvatarUpload(BaseModel):
    username: str
    image: str # Base64 字串

# --- 請加入這段 ---
class CodeVerifyRequest(BaseModel):
    question_content: str
    code: str
# ------------------

# main.py
@app.post("/avatar/upload")
async def upload_avatar(data: dict):
    try:
        username = data.get("username", "player")
        image_b64 = data.get("image").split(",")[1]
        img_bytes = base64.b64decode(image_b64)
        
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = img.size

        # 🤖 1. 分析膚色 (偵測臉部中心)
        skin_region = img.crop((w*0.45, h*0.4, w*0.55, h*0.5))
        skin_rgb = np.array(skin_region).mean(axis=(0, 1))
        
        # 🤖 2. 分析衣服顏色 (偵測胸口位置)
        cloth_region = img.crop((w*0.4, h*0.7, w*0.6, h*0.8))
        cloth_rgb = np.array(cloth_region).mean(axis=(0, 1))

        # 🤖 3. 【核心】分析五官特徵 (範例：判斷眼睛寬度來決定眼型)
        # 這裡可以透過簡單的對比度或邊緣偵測，判斷眼部特徵
        eye_area = img.crop((w*0.3, h*0.3, w*0.7, h*0.4))
        # 假設我們根據亮度分布判斷是「圓眼」還是「細長眼」
        eye_type = "round" if np.mean(eye_area) > 120 else "sharp"

        def to_hex(rgb): return '#%02x%02x%02x' % (int(rgb[0]), int(rgb[1]), int(rgb[2]))

        # 將分析結果包裝成特徵包
        features = {
            "skin": to_hex(skin_rgb),
            "cloth": to_hex(cloth_rgb),
            "eye_id": eye_type,  # 這是關鍵：AI 決定了要用哪種眼睛！
            "mouth_id": "smile"  # 也可以依此類推分析嘴角弧度
        }
        
        return {"status": "success", "features": features}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- main.py 最終修復版本 (請確保這是檔案中唯一一個 /ws/vision/game_start) ---
# --- main.py 唯一版本 ---
# --- main.py 第二步修改：數據接收版 ---


# 修改 main.py 中的 WebSocket 路由
# main.py 中的 WebSocket 路由
# main.py
@app.websocket("/ws/vision/game_start")
async def vision_game_start(websocket: WebSocket):
    await websocket.accept()
    detector = GestureDetector() 
    try:
        while True:
            data = await websocket.receive_json()
            landmarks = data.get("landmarks")
            target = data.get("target_dice") # 🏆 取得前端要你比的目標
            
            if not landmarks:
                await websocket.send_json({"status": "WAITING", "dice_val": 0})
                continue

            # 🏆 核心修正：將目標 target 傳入 process_data
            result = detector.process_data(landmarks, data.get("width", 640), data.get("height", 480), target)
            await websocket.send_json(result)

            # ❌ 移除原本的 if result.get("done"): break
            # 理由：由前端來決定何時關閉 WebSocket，避免後端誤判導致連線中斷
            
    except Exception as e:
        print(f"❌ WebSocket 異常: {e}")
    finally:
        try:
            await websocket.close()
        except: pass

# --- main.py 修正部分 ---

@app.post("/rooms/create")
async def create_room(room: RoomSchema):
    # 🏆 房號一律正規化為大寫：verify / join / leave / kick / start 全都有 .upper()，
    #    唯獨建房沒有，會讓 'abc123' 與 'ABC123' 被當成兩間不同的房。
    code = room.code.upper()
    if code in active_rooms:
        raise HTTPException(status_code=400, detail="代碼已存在")

    # 🏆 修正：初始化時就建立 players 陣列，並把房主放進去
    room_dict = room.dict()
    room_dict['code'] = code
    room_dict['players'] = [room.hostId]
    room_dict['status'] = 'waiting'
    room_dict['is_started'] = False
    touch_room(room_dict)

    active_rooms[code] = room_dict
    sync_room_log(code, "waiting", room_dict)
    return room_dict

# --- 核心邏輯：獲取所有公開房間 ---
@app.get("/rooms/public")
async def get_public_rooms():
    # 🏆 只回傳「還能加入」的房：公開、尚未開局、且狀態為 waiting。
    #    先前不分狀態全回，導致已開局或已結算的房仍留在大廳，
    #    看得到卻進不去（顯示滿員）——這是使用者回報的殭屍房間。
    return [
        r for r in active_rooms.values()
        if r.get('type') in ['public', '公開']
        and not r.get('is_started')
        and r.get('status', 'waiting') == 'waiting'
    ]

# --- 核心邏輯：刪除房間 (解決解散不掉的問題) ---
@app.delete("/rooms/delete/{code}")
async def delete_room(code: str):
    code = code.upper()
    if code in active_rooms:
        del active_rooms[code]
        _clear_room_dice_state(code)  # 🏆 一併清掉擲骰暫存，避免同房號重開有殘留
        sync_room_log(code, "abandoned")
        print(f"🔥 房間 {code} 已被刪除")
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="房間不存在")


@app.post("/rooms/join/{code}")
async def join_room(code: str, username: str):
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="房間不存在")

    room = active_rooms[code]
    if username not in room['players']:
        if len(room['players']) >= 2:
            raise HTTPException(status_code=400, detail="房間已滿")
        room['players'].append(username)

    touch_room(room)
    return room

@app.post("/rooms/leave/{code}")
async def leave_room(code: str, username: str):
    code = code.upper()
    if code in active_rooms:
        room = active_rooms[code]
        if 'players' in room and username in room['players']:
            room['players'].remove(username)
            print(f"👋 玩家 {username} 成功從房間 {code} 移除，剩餘人數: {len(room['players'])}")
            
            # 🏆 額外邏輯 1：如果房間沒人了，徹底刪除
            if not room['players']:
                del active_rooms[code]
                _clear_room_dice_state(code)  # 🏆 一併清掉擲骰暫存
                sync_room_log(code, "abandoned")
                print(f"🧹 房間 {code} 已空，自動清理完成")
            else:
                touch_room(room)
            
            # 🏆 額外邏輯 2：如果是房主離開，也可以選擇解散 (選用)
            # elif username == room.get('hostId'):
            #     del active_rooms[code]
            
            return {"status": "success", "count": len(room.get('players', []))}
            
    return {"status": "error", "message": "找不到房間或玩家"}

# 在 main.py 中加入此路由
@app.post("/rooms/kick/{code}")
async def kick_player(code: str, username: str = Query(...)): # 🏆 強制指定為 Query 參數
    code = code.upper()
    print(f"--- 偵測到踢人請求 ---")
    print(f"房間代碼: {code}, 目標玩家: {username}")
    print(f"目前所有房間: {list(active_rooms.keys())}")

    if code in active_rooms:
        room = active_rooms[code]
        touch_room(room)
        if 'players' in room and username in room['players']:
            room['players'].remove(username)
            print(f"✅ 成功剔除: {username}")
            return {"status": "success", "message": f"已將 {username} 剔除"}
        else:
            print(f"❌ 失敗: 房間 {code} 內找不到玩家 {username}")
            raise HTTPException(status_code=404, detail="房間內找不到該玩家")
    
    print(f"❌ 失敗: 伺服器找不到房間 {code}")
    raise HTTPException(status_code=404, detail="找不到房間")

# 🏆 已移除兩個 Flask 風格殘留死碼（/rooms、/rooms/public 的 @app.route 版本）：
#    它們引用未定義的 rooms_data / jsonify，一被呼叫即 NameError；
#    公開房間清單以上方 FastAPI 版 @app.get("/rooms/public") 為準。

# 🏆 修改後的驗證路由：支援同步狀態，讓平板知道何時跳轉
# main.py 約 Line 331
@app.get("/rooms/verify/{code}")
async def verify_room(code: str, username: Optional[str] = None):
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="房間不存在")
    
    room = active_rooms[code]
    
    touch_room(room)
    
    return {
        "exists": True,
        "code": code,
        "name": room.get("name", "未命名房間"),  # 🏆 確保這行存在
        "status": room.get("status", "waiting"),
        "is_started": room.get("is_started", False),
        "players": room.get("players", []),
        "hostId": room.get("hostId"),
        "mode": room.get("mode"),               # 🏆 建議同步回傳
        "difficulty": room.get("difficulty"),   # 🏆 建議同步回傳
        "winLaps": room.get("winLaps")          # 🏆 建議同步回傳
    }

@app.get("/rooms/status")
async def get_room_status(code: str):
    """
    供前端輪詢使用的 API，回傳房間目前的人數、狀態與是否已開始。
    """
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="找不到該房間")
    
    room = active_rooms[code]
    
    touch_room(room)
    
    # 🏆 確保回傳前端需要的欄位：status, players, is_started
    return {
        "code": code,
        "status": room.get("status", "waiting"),
        "players": room.get("players", []),
        "is_started": room.get("is_started", False),
        "hostId": room.get("hostId")
    }

# 🏆 新增這個路由：房主按下開始時會呼叫它
# main.py 修正點
@app.post("/rooms/start/{code}")
async def start_game(code: str, username: str, token: str = Depends(auth_utils.oauth2_scheme)):
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="找不到該房間")
    
    room = active_rooms[code]
    
    touch_room(room)
    if room['hostId'] != username:
        raise HTTPException(status_code=403, detail="只有房主可以開始遊戲")

    room['status'] = 'gaming'
    room['is_started'] = True
    sync_room_log(code, "gaming", room)

    # 🏆 務必回傳整個 room，這樣房主端 localStorage.setItem(JSON.stringify(latestData)) 才有資料
    return room


@app.post("/rooms/finish/{code}")
async def finish_room(code: str):
    """對局結束：標記為 finished 並把房間收掉。

    先前完全沒有這個端點——results.html 的「回大廳」只是換頁，
    後端從不知道對局已結束，房間就永遠留在 active_rooms 裡。

    ⚠️ 必須具冪等性：兩位玩家都會進結算頁，各會呼叫一次。
    """
    code = code.upper()
    existed = code in active_rooms
    if existed:
        del active_rooms[code]
        _clear_room_dice_state(code)
    sync_room_log(code, "finished")
    print(f"🏁 房間 {code} 對局結束，已收回")
    # 第二次呼叫時 existed 為 False，但仍回 200——冪等，不讓前端看到假錯誤
    return {"status": "success", "was_active": existed}

# 🏆 修正：讓玩家連線進入 Socket 房間，否則訊息發不出去
# 在 handle_order_dice 附近加入這個函式
# 🏆 必須加入此監聽器，否則 emit(room=room) 會找不到對象
# ==========================================================
# 🏆 斷線處理
# 原本完全沒有 disconnect handler：玩家關掉分頁後仍留在 room['players']，
# 對手收不到任何通知。最嚴重的是決定先後手階段——handle_order_dice 要湊滿
# 2 人才會廣播 dice_order_final，對手一斷線就永遠湊不滿，遊戲直接死鎖。
# 這裡記錄 sid 對應的房間與玩家，斷線時通知同房其他人並解除該死鎖。
# ==========================================================
sid_to_player: Dict[str, dict] = {}   # sid -> {"room": 房號, "user": 玩家名}


@sio.on('join_game_room')
async def handle_join_game_room(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    room = data.get('room')
    user = data.get('user')
    if room:
        await sio.enter_room(sid, room)
        sid_to_player[sid] = {"room": room, "user": user}
        print(f"✅ [Socket 房門已開] 使用者 {user} 已進入房間: {room}")


@sio.event
async def disconnect(sid):
    """玩家斷線（關分頁、當機、網路中斷）時通知同房其他人。"""
    info = sid_to_player.pop(sid, None)
    if not info:
        return   # 沒進過遊戲房的連線，不必處理

    room, user = info.get("room"), info.get("user")
    print(f"🔌 [斷線] {user} 離開房間 {room}")

    # 1. 若還在決定先後手階段，整份清掉並通知同房的人。
    #    ⚠️ 不能只在「斷線者已提交過點數」時才處理——死鎖恰恰發生在他還沒提交
    #    就離開的情況（剩下的人永遠湊不滿 2 人）。只要該房有進行中的擲骰回合，
    #    離開任何一人都代表這輪無法完成。
    #    整份清空也避免殘留的舊點數在對方重連後被誤用。
    if room_dice_data.get(room):
        room_dice_data[room] = {}
        await sio.emit('order_dice_aborted',
                       {"reason": "opponent_left", "user": user}, room=room)

    # 2. 通知同房其他人，讓前端能顯示提示而不是無限等待
    await sio.emit('opponent_disconnected', {"user": user, "room": room}, room=room)


@sio.event
async def connect(sid, environ, auth=None):
    # 僅記錄，實際的房間綁定在 join_game_room
    print(f"🔗 [Socket 連線] {sid}")

# 在 main.py 中檢查或加入此段
@sio.on('start_game_request')
async def handle_start_game(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    room_code = data.get('room')
    print(f"🚀 房主請求開始遊戲，房間代碼: {room_code}")
    
    # 🏆 關鍵：發送 'start_game_command' 給該房間內的所有成員
    await sio.emit('start_game_command', {"status": "go"}, room=room_code)

# 儲存房間擲骰順序的資料 { room_code: { username: point } }
dice_order_results = {}

@app.post("/rooms/roll_order/{code}")
async def roll_order(code: str, data: dict):
    code = code.upper()
    username = data.get('username')
    point = data.get('point')

    if code not in dice_order_results:
        dice_order_results[code] = {}

    # 記錄該玩家點數
    dice_order_results[code][username] = point
    
    room = active_rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="房間不存在")

    # 檢查是否兩位玩家都擲骰了
    players = room.get('players', [])
    if len(dice_order_results[code]) >= len(players):
        # 回傳所有人的點數，讓前端比大小
        return {
            "status": "completed",
            "results": dice_order_results[code]
        }
    else:
        return {"status": "waiting", "message": "等待對方擲骰..."}

# 儲存結構: { room_name: { username: points } }
room_dice_data = {}

# --- 修正 1：handle_order_dice ---
# --- 修正後的 handle_order_dice ---
@sio.on('submit_order_dice')
async def handle_order_dice(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    print(f"📥 收到點數提交: {data}")
    room = data.get('room')
    user = data.get('user')
    points = data.get('points') 

    if points is None or not room:
        print(f"⚠️ 資料格式錯誤")
        return
    
    if room not in room_dice_data:
        room_dice_data[room] = {}
    
    room_dice_data[room][user] = points
    print(f"📊 房間 {room} 目前進度: {room_dice_data[room]}")
    
    # 🏆 檢查房間人數 (假設為 2 人)
    # 如果您 active_rooms 裡有存人數，也可以改用 len(active_rooms[room]['players'])
    if len(room_dice_data[room]) >= 2:
        print(f"📣 雙方到齊！正在對房間 {room} 發送 dice_order_final...")
        
        # 複製一份資料再發送，避免發送中途被清空
        final_results = room_dice_data[room].copy()
        
        # 🏆 關鍵：發送給該房間所有成員
        await sio.emit('dice_order_final', final_results, room=room)
        
        # 發送完畢後再清空
        room_dice_data[room] = {}

# 🏆 新增：處理平手重置請求
@sio.on('reset_dice_order')
async def handle_reset_dice(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    room = data.get('room')
    if room in room_dice_data:
        room_dice_data[room] = {}
        print(f"🔄 房間 {room} 點數已重置 (平手重新擲骰)")

# 在 main.py 中加入或修改此 Socket 監聽器
@sio.on('broadcast_dice_event')
async def handle_dice_event(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    # data 格式範例: {"room": "ROOM123", "user": "玩家ID", "type": "ROLLING" 或 "RESULT", "point": 5}
    room = data.get('room')
    print(f"📣 廣播擲骰事件: {data}")
    await sio.emit('dice_event_sync', data, room=room)

# 在 main.py 中加入此段落
@sio.on('player_move_sync_request')
async def handle_move_request(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    room = data.get('room')
    print(f"🚀 收到移動請求，正在廣播給房間 {room}: {data}")
    # 🏆 關鍵：將訊息廣播給房間內所有人 (包含發送者自己)
    # 這樣所有人的電腦都會觸發 socket.on('player_move_sync')
    await sio.emit('player_move_sync', data, room=room)

@sio.on('player_move_finished_event')
async def handle_move_finished(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    room = data.get('room')
    # 通知所有人清空提示訊息
    await sio.emit('player_move_finished', data, room=room)

@app.get("/game/map_config")
async def get_map_config(
    mode: str,
    difficulty: str,
    test: bool = False,
    qtype: str = None,
    username: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    try:
        from sqlalchemy import or_
        db_mode = "basic" if "基礎" in mode else "advanced"
        db_qtype = qtype or ("choice" if db_mode == "basic" else "code")

        # 🏆 判斷遊玩者所屬班級：優先從參數 username 找，若無則從目前活躍房間內的玩家找
        user_class_id = None
        if username:
            u = db.query(models.User).filter(models.User.username == username).first()
            if u and u.class_id:
                user_class_id = u.class_id
        else:
            for r in active_rooms.values():
                for p_name in r.get("players", []):
                    u = db.query(models.User).filter(models.User.username == p_name).first()
                    if u and u.class_id:
                        user_class_id = u.class_id
                        break
                if user_class_id:
                    break

        # 🏆 一般玩家只抽官方題庫 (class_id IS NULL)；班級學生抽「官方 ＋ 該班級老師新增的題庫」
        q_filter = models.Question.class_id.is_(None)
        if user_class_id:
            q_filter = or_(models.Question.class_id.is_(None), models.Question.class_id == user_class_id)

        questions = db.query(models.Question).filter(
            models.Question.category == db_mode,
            models.Question.qtype == db_qtype,
            models.Question.difficulty == difficulty,
            q_filter
        ).order_by(func.random()).limit(20).all()
        
        countries = db.query(models.CountryScenario).order_by(func.random()).limit(20).all()

        if not questions or not countries:
             return {"error": "資料庫資料不足",
                     "q_count": len(questions), "c_count": len(countries),
                     "qtype": db_qtype,
                     "hint": f"找不到 {db_mode}/{db_qtype}/{difficulty} 的題目，"
                             f"請到後台 question.html 新增，或在 PyPoly/ 底下跑 python seed_data.py"}

        adventure_tiles = []
        adventure_geo = []  # 與 adventure_tiles 一一對應的 (lat, lon, elev_m)
        for i in range(20):
            q = questions[i % len(questions)]
            c = countries[i % len(countries)]
            adventure_geo.append((
                float(c.latitude) if c.latitude is not None else None,
                float(c.longitude) if c.longitude is not None else None,
                c.elevation_m,
            ))

            adventure_tiles.append({
                "type": "ADVENTURE",
                "id": c.id,
                "data": { 
                    "name": c.name,
                    # 🏆 前端用鄉鎮決定格子的地形外觀（見 static/js/board-terrain.js）：
                    #    魚池鄉→水岸、仁愛鄉→雪地、鹿谷鄉→森林…
                    "township": c.township,
                    "scenario": c.scenario,
                    # 🏆 由 id 推導而非讀資料庫欄位：資料庫存檔名容易與實際檔案脫節
                    #    （實測 5 筆全指向不存在的圖，導致冒險格整局卡死）。
                    #    放 scenarios/ 子目錄是為了與現有的 24.jpg~107.jpg 隔離，
                    #    否則情境數成長到 24 以上會撞名且不會報錯。
                    "skybox_url": f"scenarios/{c.id}.jpg",
                    "base_price": c.base_price,  # 🏆 補上收購價
                    "base_toll": c.base_toll,    # 🏆 補上過路費
                    # 🏆 真實座標與海拔，沒有敏感性，對玩家來說是有意義的
                    #    資訊（棋盤格的 x/y/z 就是由這幾個值換算出來的）
                    "latitude": float(c.latitude) if c.latitude is not None else None,
                    "longitude": float(c.longitude) if c.longitude is not None else None,
                    "elevation_m": c.elevation_m,
                    # ⚠️ 這裡絕對不可以放 expected_output 與 reference_solution。
                    #    那是程式碼題的答案，前端拿到等於 DevTools 一開就看得到。
                    #    判分要用的時候，由 /game/verify_code 憑題目 id 自己查資料庫。
                    "question": {
                        "id": q.id,                # 🏆 需求⑨：作答紀錄用
                        "category": q.category,    # basic / advanced（模式）
                        "qtype": q.qtype or "choice",   # choice / gesture / code：前端據此決定作答介面
                        "topic": q.topic,          # 🏆 需求⑨：真正的語法主題，供結算「最常出現語法」統計
                        "content": q.content,
                        # 🏆 需求①：加入 opt4，並濾掉 None（進階題無選項時才不會出現空泡泡）
                        "options": [o for o in [q.opt1, q.opt2, q.opt3, q.opt4] if o],
                        "answer": q.answer,
                        "starter_code": q.starter_code,       # 程式碼題：編輯器預填
                        "time_limit_sec": q.time_limit_sec,   # 程式碼題：作答秒數
                        "max_attempts": q.max_attempts        # 程式碼題：可驗證次數
                    }
                }
            })

        # 🏆 每局隨機挑一種幾何形狀（圓形/方形/六邊形/無限符號），20 個
        #    冒險格依真實海拔的「排名」決定走訪順序，並把內容
        #    （adventure_tiles）跟著一起重新排列——內容跟座標必須綁在
        #    一起移動，不然會出現「這格顯示地點 A 的故事，卻站在地點 B
        #    的座標上」的錯位。詳見 board_geo.py 檔頭說明。
        elevations = [elev for _, _, elev in adventure_geo]
        shape_key, order, positions_26 = board_geo.compute_shape_board(elevations)
        adventure_tiles = [adventure_tiles[i] for i in order]

        full_map = [None] * 26
        full_map[0] = {"type": "START", "name": "起點"}
        full_map[13] = {"type": "JAIL", "name": "監獄"}
        full_map[6] = {"type": "PUNISH", "name": "開合跳"}
        full_map[19] = {"type": "REWARD", "name": "獎勵遊戲"}
        full_map[3] = {"type": "SHOP", "name": "道具店"}
        full_map[16] = {"type": "SHOP", "name": "道具店"}

        # 🏆 測試模式：只保留前 KEEP 格冒險格，其餘換成 BLANK。
        #    保留幾格是為了仍能驗證答題→作答紀錄→結算報表這條資料鏈，
        #    全部換成 BLANK 的話結算頁會沒有答題數據可看。
        TEST_KEEP_ADVENTURE = 4
        if test:
            for idx in range(TEST_KEEP_ADVENTURE, len(adventure_tiles)):
                adventure_tiles[idx] = {"type": "BLANK", "name": "空白格"}

        # positions_26（board_geo.compute_shape_board 算好的）已經是
        # 完整 26 格、slot 順序的座標，特殊格的 x/y/z 也都算好了——
        # 形狀本身天生均勻分布在外框上，不會重疊，不需要再額外插值
        # 或 declutter。
        adv_idx = 0
        for i in range(26):
            if full_map[i] is None:
                full_map[i] = adventure_tiles[adv_idx]
                adv_idx += 1

        for i in range(26):
            x, y, z = positions_26[i]
            full_map[i]["x"] = x
            full_map[i]["y"] = y
            full_map[i]["z"] = z

        return full_map

    except Exception as e:
        print(f"🔥 後端報錯: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# main.py 修正版
@app.websocket("/ws/vision/jumping")
async def vision_jumping(websocket: WebSocket):
    await websocket.accept()
    pose_detector = game_start.PoseDetector()
    gesture_detector = game_start.GestureDetector() 
    
    try:
        while True:
            data = await websocket.receive_json()
            pose_lms = data.get("landmarks")
            hand_lms = data.get("hand_landmarks")
            # 🏆 核心修正：接收前端傳來的 target_dice (這在 SKIP_CONFIRMING 階段非常重要)
            target = data.get("target_dice") 
            
            result = pose_detector.process_data(pose_lms)
            
            if hand_lms:
                # 🏆 核心修正：傳入正確的 target 以啟用穩定度檢查與決策判定
                gesture_res = gesture_detector.process_data(hand_lms, 640, 480, target)
                res_val = gesture_res.get("dice_val")
                result["gesture"] = res_val
                # 這裡也要同步回傳 status 以便前端判斷 SUCCESS
                result["status"] = gesture_res.get("status")
            else:
                result["gesture"] = None
                result["status"] = "WAITING"

            await websocket.send_json(result)
            if result.get("done"): break
    except Exception as e:
        print(f"❌ Jumping WebSocket 異常: {e}")
    finally:
        await websocket.close()

# main.py 中新增
@app.websocket("/ws/vision/bird")
async def vision_bird(websocket: WebSocket):
    await websocket.accept()
    detector = game_start.BirdDetector()
    try:
        while True:
            data = await websocket.receive_json()
            landmarks = data.get("landmarks")
            result = detector.process_data(landmarks)
            await websocket.send_json(result)
            if result.get("done"): break
    except Exception as e:
        print(f"❌ Bird WebSocket 異常: {e}")
    finally:
        await websocket.close()

@sio.on('sync_user_appearance')
async def handle_sync_appearance(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    room = data.get('room')
    user = data.get('user')
    
    # 🏆 新增：印出這個廣播到底要發給誰，以及房間號碼是否正確
    print(f"🎨 [後端偵測] 收到來自 {user} 的請求，目標房間為: '{room}'")
    
    if not room or room == "":
        print(f"❌ [嚴重錯誤] 房間代碼為空，廣播失敗！")
        return

    # 確認廣播
    await sio.emit('user_appearance_broadcast', data, room=room)
    print(f"📡 [後端廣播] 已將外觀資料送出至房間: {room}")


# --- 修正 2：handle_buy_land ---
# main.py 修正版
@sio.on('buy_land')
async def handle_buy_land(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    room = data['room']
    user = data['user']
    tile_index = data['tileIndex']
    price = data.get('price', 500)
    # 🏆 修正：加蓋第二棟房子時前端已經正確把過路費算成兩倍（window.newToll），
    # 但這裡原本沒有把 toll 收進來、也沒有廣播出去，導致雙方畫面上的過路費
    # 永遠停在舊值（只算一棟的錢）。這裡原封不動轉發前端送來的值即可，
    # 不需要在伺服器端重新計算。
    toll = data.get('toll', 0)

    # 🏆 依房內玩家索引分配固定色盤，避免以隨機 sid 字串判斷造成兩人同色
    palette = ["#4facfe", "#ffde59", "#ff6b6b", "#51cf66"]
    players = active_rooms.get(room, {}).get('players', [])
    try:
        idx = players.index(user)
    except ValueError:
        idx = 0
    color = palette[idx % len(palette)]

    await sio.emit('land_bought_sync', {
        'user': user,
        'tileIndex': tile_index,
        'color': color,
        'price': price,
        'toll': toll
    }, room=room)

# 🏆 模擬/實際抓取南投縣開放平台數據的函式
async def fetch_nantou_live_data(location_name: str):
    """
    這裡未來可以串接南投縣政府資料開放平台的 API。
    目前先結構化，方便您將來填入 API Key 與 URL。
    """
    try:
        # 範例：串接「南投縣主要觀光景點遊客人數統計」
        # api_url = f"https://data.nantou.gov.tw/api/v1/..."
        # res = requests.get(api_url)
        # data = res.json()
        # return data['current_count'] 
        
        # 目前暫時維持隨機以供比賽展示，但建議正式環境填入上述邏輯
        return random.randint(150, 2500) 
    except:
        return 500 # 發生錯誤時的保底人數

@app.get("/game/adventure_analysis/{land_id}")
async def get_adventure_analysis(land_id: int, db: Session = Depends(database.get_db)):
    # 1. 從資料庫抓取基礎情境
    land = db.query(models.CountryScenario).filter(models.CountryScenario.id == land_id).first()
    if not land:
        raise HTTPException(status_code=404, detail="找不到情境")

    # 🏆 2. AQI 真實資料（環境部）
    aqi_info = air_quality.fetch_aqi_by_name(land.api_station_name)
    has_env_event = aqi_info is not None
    real_aqi = aqi_info["aqi"] if has_env_event else None
    multiplier = aqi_info["multiplier"] if has_env_event else 1.0

    # 🏆 3. 氣溫與天氣真實資料（中央氣象署）
    temp_info = temperature.fetch_temperature(land.name, land.township)
    has_temp_event = temp_info is not None
    real_temp = temp_info["temperature"] if has_temp_event else None
    real_weather = temp_info["weather"] if has_temp_event else "晴"
    temp_multiplier = temp_info["multiplier"] if has_temp_event else 1.0

    # 🏆 4. 綜合環境加成（AQI 加成 × 氣溫加成）
    combined_multiplier = round(multiplier * temp_multiplier, 2)

    # 5. ⚖️ 收購價與過路費計算（移除隨機人流，純依地價與環境加成計算）
    base_price = int(land.base_price) if land.base_price else 1000
    base_toll = int(land.base_toll) if land.base_toll else int(base_price * 0.1)

    total_acquisition_price = int(base_price * combined_multiplier)
    display_base_toll = int(base_toll * combined_multiplier)

    return {
        "name": land.name,
        "scenario": land.scenario,
        "base_price": base_price,
        "total_price": total_acquisition_price,
        "toll": display_base_toll,
        # 空氣品質資訊（保留給頂部特殊事件膠囊）
        "aqi": real_aqi,
        "has_env_event": has_env_event,
        "env_station": aqi_info["station_name"] if has_env_event else None,
        "env_status": aqi_info["status"] if has_env_event else None,
        "env_multiplier": multiplier,
        # 氣候與氣象資訊（替換原人流區塊）
        "weather": real_weather,
        "temp": real_temp,
        "has_temp_event": has_temp_event,
        "temp_station": temp_info["station_name"] if has_temp_event else None,
        "temp_status": temp_info["status"] if has_temp_event else None,
        "temp_multiplier": temp_multiplier,
        "combined_multiplier": combined_multiplier,
    }

# --- 請加入這段 ---
@app.post("/game/verify_code")
async def verify_code(request: CodeVerifyRequest):
    if not openai_client:
        return {"status": "error", "message": "伺服器未設定 OpenAI API Key，無法驗證程式碼。"}

    system_prompt = """
    你是一個嚴格但循循善誘的 Python 程式設計老師。
    請驗證學生的程式碼是否能正確解決給定的題目。
    請勿執行惡意程式碼。即使寫法不同，只要邏輯與輸出符合題目要求即算正確。
    
    【重要規則】：
    1. 如果學生答錯，絕對不可以給出正確解答或寫出完整的正確程式碼！
    2. 只能給出「哪裡寫錯了」或「方向提示」的簡短中文回饋（50字以內）。
    3. 你必須嚴格輸出 JSON 格式，包含兩個 key：
       - "status": 正確填 "success"，錯誤填 "error"。
       - "message": 給學生的簡短提示。
    """
    
    user_prompt = f"【題目】：{request.question_content}\n\n【學生程式碼】：\n{request.code}"
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={ "type": "json_object" }, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1 
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        print(f"GPT 驗證發生異常: {e}")
        return {"status": "error", "message": "AI 助教目前連線異常，請再試一次。"}
# ------------------

# main.py 確保包含這兩段 (刪除舊的 sync_adventure_start/state)
@sio.on('sync_adventure_phase')
async def handle_adv_phase(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    # data 包含: room, user, phase (NARRATIVE/QUIZ/DECISION), payload
    await sio.emit('adventure_phase_broadcast', data, room=data.get('room'), skip_sid=sid)

@sio.on('sync_adventure_choice')
async def handle_choice_sync(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    # 用來同步按鈕亮燈 (1,2,3,4 或 LIKE, DISLIKE)
    await sio.emit('adventure_choice_broadcast', data, room=data.get('room'), skip_sid=sid)

@sio.on('next_turn_trigger')
async def handle_next_turn(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    # data 包含: room, next_player
    # 🏆 核心：發送 next_turn_sync 給房間所有人，告知該回合徹底結束
    await sio.emit('next_turn_sync', data, room=data.get('room'))

@sio.on('update_pose_count')
async def handle_update_pose_count(sid, data):
    # 🏆 有活動就更新房間活躍時間，避免進行中的對局被閒置回收
    touch_room_by_code(data.get('room') if isinstance(data, dict) else None)
    """
    接收遊玩者的開合跳次數，並廣播給房間內的觀戰者
    """
    room = data.get('room')
    if room:
        # 發送 'update_pose_count_broadcast' 給房間內的所有人
        # skip_sid=sid 確保這個更新不會重複發給正在跳躍的玩家自己
        await sio.emit('update_pose_count_broadcast', data, room=room, skip_sid=sid)


# ==========================================================
# 🏆 需求⑨：遊戲結算 API (存 DB + 提供結算畫面資料)
# ==========================================================

# 1. 作答紀錄：每答一題寫入一筆明細 (game_answer_logs)
@app.post("/game/answer_log")
def log_answer(data: dict, db: Session = Depends(database.get_db)):
    log = models.GameAnswerLog(
        room_code=data.get("room_code"),
        username=data.get("username"),
        question_id=data.get("question_id"),
        category=data.get("category"),
        question_text=data.get("question_text"),
        chosen_answer=data.get("chosen_answer"),
        correct_answer=data.get("correct_answer"),
        is_correct=bool(data.get("is_correct")),
        answer_sec=float(data.get("answer_sec") or 0),
    )
    db.add(log)
    db.commit()
    return {"status": "success"}


# 2. 遊戲結算：依各玩家金錢排名，聚合作答明細寫入 game_records
#    body: { room_code, players: [ {username, final_money, laps, jump_count} ] }
@app.post("/game/settle")
def settle_game(data: dict, db: Session = Depends(database.get_db)):
    room_code = data.get("room_code")
    players = data.get("players", [])
    if not room_code or not players:
        raise HTTPException(status_code=400, detail="缺少 room_code 或 players")

    # 冪等：先清掉此房間的舊結算，避免重複送出造成重複列
    db.query(models.GameRecord).filter(
        models.GameRecord.room_code == room_code
    ).delete()

    # 依最終金錢由高到低排名
    ranked = sorted(players, key=lambda p: p.get("final_money", 0), reverse=True)
    top_money = ranked[0].get("final_money", 0) if ranked else 0

    results = []
    for idx, p in enumerate(ranked):
        username = p.get("username")
        final_money = int(p.get("final_money", 0) or 0)
        laps = int(p.get("laps", 0) or 0)
        jump_count = int(p.get("jump_count", 0) or 0)

        # 從作答明細聚合該玩家統計
        logs = db.query(models.GameAnswerLog).filter(
            models.GameAnswerLog.room_code == room_code,
            models.GameAnswerLog.username == username
        ).all()
        total_q = len(logs)
        correct = sum(1 for l in logs if l.is_correct)
        avg_sec = round(sum((l.answer_sec or 0) for l in logs) / total_q, 1) if total_q else 0
        cats = [l.category for l in logs if l.category]
        top_category = Counter(cats).most_common(1)[0][0] if cats else None

        rec = models.GameRecord(
            room_code=room_code,
            username=username,
            final_money=final_money,
            rank=idx + 1,
            is_winner=(final_money == top_money),
            total_questions=total_q,
            correct_count=correct,
            avg_answer_sec=avg_sec,
            top_category=top_category,
            jump_count=jump_count,
            laps=laps,
        )
        db.add(rec)
        results.append({
            "rank": idx + 1,
            "username": username,
            "final_money": final_money,
            "is_winner": (final_money == top_money),
            "accuracy": round(correct / total_q * 100) if total_q else 0,
        })

    db.commit()
    return {"status": "success", "results": results}


# 3. 取得結算資料：供 results.html 顯示排行榜與整體報表
@app.get("/game/results/{room_code}")
def get_results(room_code: str, db: Session = Depends(database.get_db)):
    records = db.query(models.GameRecord).filter(
        models.GameRecord.room_code == room_code
    ).order_by(models.GameRecord.rank.asc()).all()
    if not records:
        raise HTTPException(status_code=404, detail="找不到該局結算資料")

    leaderboard = [{
        "rank": r.rank,
        "username": r.username,
        "final_money": r.final_money,
        "is_winner": bool(r.is_winner),
        "accuracy": round(r.correct_count / r.total_questions * 100) if r.total_questions else 0,
        "correct_count": r.correct_count,
        "total_questions": r.total_questions,
        "avg_answer_sec": r.avg_answer_sec,
        "top_category": r.top_category,
        "jump_count": r.jump_count,
        "laps": r.laps,
    } for r in records]

    # 整體報表：彙整全房作答明細
    logs = db.query(models.GameAnswerLog).filter(
        models.GameAnswerLog.room_code == room_code
    ).all()
    cat_counter = Counter([l.category for l in logs if l.category])
    total_logs = len(logs)
    total_correct = sum(1 for l in logs if l.is_correct)
    avg_all = round(sum((l.answer_sec or 0) for l in logs) / total_logs, 1) if total_logs else 0

    report = {
        "top_category": cat_counter.most_common(1)[0][0] if cat_counter else "—",
        "category_counts": dict(cat_counter),
        "total_questions": total_logs,
        "overall_accuracy": round(total_correct / total_logs * 100) if total_logs else 0,
        "avg_answer_sec": avg_all,
        # 答錯題回顧
        "wrong_questions": [{
            "username": l.username,
            "question_text": l.question_text,
            "chosen": l.chosen_answer,
            "correct": l.correct_answer,
            "category": l.category,
        } for l in logs if not l.is_correct],
    }

    return {"room_code": room_code, "leaderboard": leaderboard, "report": report}


# ==========================================================
# 學習統計 (learn.html)
#
# 這裡刻意「即時計算」而不另建彙總表。所有數字都能從 game_records 與
# game_answer_logs 算出來，另存一份就是衍生資料——結算時若漏更新或需要回填，
# 它會安靜地與來源表不一致，而且沒有人會發現。
# 成本可忽略：兩張表的 username 都已建索引，目前資料量也只有數十筆。
# ==========================================================

# ⚠️ 與 static/game.html:2475 的起始金寫死值對應，兩處必須一起改。
#    「累積淨賺」要扣掉起始金，否則玩越多局數字越大，反映的是場次而非實力。
STARTING_MONEY = 5000

# 判定弱項至少要答過幾題。只答一題就答錯不足以稱為弱項，
# 否則第一次上場答錯一題，該主題就會被 AI 拿去說教。
_WEAK_MIN_SAMPLES = 2


def _build_learn_stats(username: str, db: Session) -> dict:
    """彙總單一玩家的跨場次學習統計。

    回傳的 ai_context 是給組員接 AI 用的**穩定契約**：
    畫面欄位日後怎麼改都不動它，組員的程式只讀那一塊。
    """
    records = db.query(models.GameRecord).filter(
        models.GameRecord.username == username
    ).order_by(models.GameRecord.created_at.desc()).all()

    logs = db.query(models.GameAnswerLog).filter(
        models.GameAnswerLog.username == username
    ).order_by(models.GameAnswerLog.created_at.desc()).all()

    # --- 總覽 ---
    total_q = sum(r.total_questions or 0 for r in records)
    correct = sum(r.correct_count or 0 for r in records)
    net_profit = sum((r.final_money or 0) - STARTING_MONEY for r in records)
    jump_total = sum(r.jump_count or 0 for r in records)
    wins = sum(1 for r in records if r.is_winner)
    # 平均用時取自作答明細而非 game_records.avg_answer_sec，
    # 後者是「每局的平均」，再平均一次會讓題數少的那局被過度加權。
    avg_sec = round(sum((l.answer_sec or 0) for l in logs) / len(logs), 1) if logs else 0

    summary = {
        "accuracy": round(correct / total_q * 100) if total_q else 0,
        "correct": correct,
        "total_questions": total_q,
        "net_profit": net_profit,
        "jump_count": jump_total,
        "avg_answer_sec": avg_sec,
        "wins": wins,
    }

    # --- 知識維度：依語法主題分組 ---
    # game_answer_logs.category 存的是 questions.topic（變數/迴圈/串列…），
    # 不是 basic/advanced 的模式分類，見 game.html:7510。
    by_topic: Dict[str, Dict[str, int]] = {}
    for l in logs:
        if not l.category:
            continue
        d = by_topic.setdefault(l.category, {"total": 0, "correct": 0})
        d["total"] += 1
        if l.is_correct:
            d["correct"] += 1

    dimensions = [{
        "topic": topic,
        "total": d["total"],
        "correct": d["correct"],
        "accuracy": round(d["correct"] / d["total"] * 100) if d["total"] else 0,
    } for topic, d in by_topic.items()]
    # 答得多的排前面，同樣題數時正確率低的優先（比較需要被看見）
    dimensions.sort(key=lambda x: (-x["total"], x["accuracy"]))

    # --- 近期對局 ---
    recent_games = [{
        "room_code": r.room_code,
        "rank": r.rank,
        "final_money": r.final_money,
        "net_profit": (r.final_money or 0) - STARTING_MONEY,
        "accuracy": round(r.correct_count / r.total_questions * 100) if r.total_questions else 0,
        "laps": r.laps,
        "jump_count": r.jump_count,
        "is_winner": bool(r.is_winner),
        "created_at": r.created_at,
    } for r in records[:5]]

    # --- 給 AI 的脈絡 ---
    sampled = [d for d in dimensions if d["total"] >= _WEAK_MIN_SAMPLES]
    weakest = [d["topic"] for d in sorted(sampled, key=lambda x: x["accuracy"])[:3]
               if d["accuracy"] < 100]
    strongest = [d["topic"] for d in sorted(sampled, key=lambda x: -x["accuracy"])[:3]
                 if d["accuracy"] >= 60]

    ai_context = {
        "username": username,
        "games_played": len(records),
        "accuracy": summary["accuracy"],
        "total_questions": total_q,
        "avg_answer_sec": avg_sec,
        "dimensions": [{"topic": d["topic"], "accuracy": d["accuracy"], "total": d["total"]}
                       for d in dimensions],
        "strongest": strongest,
        "weakest": weakest,
        # 只取最近 5 題，避免 prompt 過長；LLM 不需要看完整作答史
        "recent_wrong": [{
            "topic": l.category,
            "question": l.question_text,
            "chosen": l.chosen_answer,
            "correct": l.correct_answer,
        } for l in logs if not l.is_correct][:5],
    }

    return {
        "username": username,
        "games_played": len(records),
        "summary": summary,
        "dimensions": dimensions,
        "recent_games": recent_games,
        "ai_context": ai_context,
    }


@app.get("/learn/stats")
def learn_stats(username: str = None, authorization: str = Header(None),
                db: Session = Depends(database.get_db)):
    """學習統計。省略 username 時用 token 解出自己的身分。

    從未遊玩過的人回傳 games_played=0 的空統計而非 404——
    「還沒有資料」不是錯誤，前端要能顯示空狀態而不是報錯。
    """
    if not username:
        username = auth_utils.get_current_user(authorization)   # 無效 token 會拋 401
    return _build_learn_stats(username, db)


@app.post("/learn/ai_report")
async def learn_ai_report(request: Request,                     # 1. 這裡加入 request: Request (並將 def 改為 async def)
                          username: str = None, 
                          authorization: str = Header(None),
                          db: Session = Depends(database.get_db)):
    """AI 導師分析。實作在 learn_ai.py，那是留給組員的交接點。"""
    if not username:
        username = auth_utils.get_current_user(authorization)

    ctx = _build_learn_stats(username, db)["ai_context"]

    # 2. 關鍵加入：安全讀取前端傳來的發問與歷史對話，塞進 ctx
    try:
        body = await request.json()
        if isinstance(body, dict):
            ctx["message"] = body.get("message")
            ctx["history"] = body.get("history", [])
    except Exception:
        pass  # 第一次載入頁面無 body 時自動忽略，完全不影響原邏輯

    try:
        report = learn_ai.generate_report(ctx)
        if not report or not str(report).strip():
            raise ValueError("generate_report 回傳空內容")
        return {"status": "success", "source": "ai", "report": str(report)}
    except Exception as e:
        print(f"⚠️ AI 導師分析失敗，改用規則式退路：{e}")
        return {"status": "success", "source": "fallback",
                "report": learn_ai._rule_based(ctx)}


# ==========================================================
# 🏆 取得單一玩家的本局作答紀錄 (供結算頁面 results.html 使用)
# ==========================================================
@app.get("/game/answer_logs")
def get_user_answer_logs(room: str, user: str, db: Session = Depends(database.get_db)):
    if not room or not user:
        raise HTTPException(status_code=400, detail="缺少 room 或 user 參數")
        
    logs = db.query(models.GameAnswerLog).filter(
        models.GameAnswerLog.room_code == room.upper(),
        models.GameAnswerLog.username == user
    ).order_by(models.GameAnswerLog.created_at.asc()).all()

    return [{
        "question_text": l.question_text,
        "chosen_answer": l.chosen_answer,
        "correct_answer": l.correct_answer,
        "is_correct": l.is_correct,
        "category": l.category
    } for l in logs]

# Pydantic 驗證格式
class HandbookCreate(BaseModel):
    title: str
    category: str
    cat_name: str
    cat_class: Optional[str] = "cat-basic"
    level: Optional[str] = "★☆☆ 啟蒙"
    order_index: Optional[int] = 0
    description: str
    code_example: Optional[str] = ""
    tip: Optional[str] = ""

# 📖 1. 前台獲取所有學習手冊卡片 (依 order_index 排序)
@app.get("/handbook/list")
def get_handbook_cards(username: Optional[str] = None, db: Session = Depends(database.get_db)):
    # 先確認有沒有官方基底教材，沒有就初始化
    base_count = db.query(models.HandbookCard).filter(models.HandbookCard.class_id.is_(None)).count()
    if base_count == 0:
        seed_handbook.seed_handbook_data(db)

    # 查詢玩家是否有加入班級
    user_class_id = None
    if username:
        u = db.query(models.User).filter(models.User.username == username).first()
        if u and u.class_id:
            user_class_id = u.class_id

    # 🏆 核心邏輯：抓取「官方全域教材 (class_id IS NULL)」＋「該生所屬班級教材」
    from sqlalchemy import or_
    if user_class_id:
        cards = db.query(models.HandbookCard).filter(
            or_(models.HandbookCard.class_id.is_(None), models.HandbookCard.class_id == user_class_id)
        ).order_by(models.HandbookCard.order_index.asc(), models.HandbookCard.id.asc()).all()
    else:
        cards = db.query(models.HandbookCard).filter(
            models.HandbookCard.class_id.is_(None)
        ).order_by(models.HandbookCard.order_index.asc(), models.HandbookCard.id.asc()).all()

    return cards

# 📖 2. 後台管理員新增卡片
@app.post("/admin/handbook/add")
def add_handbook_card(card: HandbookCreate, db: Session = Depends(database.get_db)):
    new_card = models.HandbookCard(**card.dict())
    db.add(new_card)
    db.commit()
    db.refresh(new_card)
    return {"status": "success", "card_id": new_card.id}

# 📖 3. 後台管理員編輯卡片
@app.put("/admin/handbook/{card_id}")
def update_handbook_card(card_id: int, card: HandbookCreate, db: Session = Depends(database.get_db)):
    target = db.query(models.HandbookCard).filter(models.HandbookCard.id == card_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到此知識卡片")
    for key, value in card.dict().items():
        setattr(target, key, value)
    db.commit()
    return {"status": "success", "msg": "教材已更新"}

# 📖 4. 後台管理員刪除卡片
@app.delete("/admin/handbook/{card_id}")
def delete_handbook_card(card_id: int, db: Session = Depends(database.get_db)):
    target = db.query(models.HandbookCard).filter(models.HandbookCard.id == card_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到此知識卡片")
    db.delete(target)
    db.commit()
    return {"status": "success", "msg": "教材已刪除"}

# ==========================================================
# 🏆 教育版：自動補齊舊資料表欄位 & 玩家加入班級 API
# ==========================================================

def ensure_education_columns():
    """啟動時自動為舊資料表補上 class_id 與 created_by 欄位，免除手動改 DB 的麻煩"""
    alter_stmts = [
        "ALTER TABLE users ADD COLUMN class_id INT NULL",
        "ALTER TABLE questions ADD COLUMN class_id INT NULL",
        "ALTER TABLE questions ADD COLUMN created_by VARCHAR(50) NULL",
        "ALTER TABLE handbook_cards ADD COLUMN class_id INT NULL",
        "ALTER TABLE handbook_cards ADD COLUMN created_by VARCHAR(50) NULL",
    ]
    with database.engine.connect() as conn:
        for stmt in alter_stmts:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                # 欄位若已存在會報錯，直接安全略過即可
                pass

# 啟動時執行一次欄位檢查
ensure_education_columns()


class JoinClassRequest(BaseModel):
    username: str
    invite_code: str


@app.post("/classes/join")
def student_join_class(req: JoinClassRequest, db: Session = Depends(database.get_db)):
    code = req.invite_code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="請輸入班級邀請碼")

    classroom = db.query(models.Classroom).filter(models.Classroom.invite_code == code).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="找不到此邀請碼對應的班級，請向老師確認！")

    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到玩家帳號")

    user.class_id = classroom.id
    db.commit()
    return {
        "status": "success",
        "class_id": classroom.id,
        "class_name": classroom.name,
        "teacher": classroom.teacher_username
    }


@app.post("/classes/leave")
def student_leave_class(username: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到玩家帳號")
    user.class_id = None
    db.commit()
    return {"status": "success"}


# ==========================================================
# 🏆 第二階段：管理員監控 (班級列表/教師通知) & 教師端後台 API
# ==========================================================

def require_teacher(authorization: str = Header(None), db: Session = Depends(database.get_db)):
    """教師權限守衛：允許 role 為 teacher 或 admin 的帳號通行"""
    username = auth_utils.get_current_user(authorization)
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="需要老師或管理員權限")
    return user


# --- 管理員專用：查看所有老師建立的班級 ---
@app.get("/admin/classes")
def admin_list_classes(db: Session = Depends(database.get_db), admin: models.User = Depends(require_admin)):
    classes = db.query(models.Classroom).order_by(models.Classroom.id.desc()).all()
    result = []
    for c in classes:
        student_count = db.query(models.User).filter(models.User.class_id == c.id).count()
        result.append({
            "id": c.id,
            "name": c.name,
            "teacher_username": c.teacher_username,
            "invite_code": c.invite_code,
            "student_count": student_count,
            "created_at": c.created_at
        })
    return result


# --- 管理員專用：查看老師對題庫/手冊的更動提示 ---
@app.get("/admin/audit_logs")
def admin_get_audit_logs(db: Session = Depends(database.get_db), admin: models.User = Depends(require_admin)):
    logs = db.query(models.TeacherAuditLog).order_by(models.TeacherAuditLog.id.desc()).limit(50).all()
    unread_count = db.query(models.TeacherAuditLog).filter(models.TeacherAuditLog.is_read == False).count()
    return {
        "unread_count": unread_count,
        "items": [
            {
                "id": l.id,
                "teacher_username": l.teacher_username,
                "class_name": l.class_name,
                "action": l.action,
                "target_type": l.target_type,
                "detail": l.detail,
                "is_read": l.is_read,
                "created_at": l.created_at
            } for l in logs
        ]
    }


@app.post("/admin/audit_logs/read_all")
def admin_mark_logs_read(db: Session = Depends(database.get_db), admin: models.User = Depends(require_admin)):
    db.query(models.TeacherAuditLog).filter(models.TeacherAuditLog.is_read == False).update({"is_read": True})
    db.commit()
    return {"status": "success"}


# --- 教師專用：取得自己名下的所有班級 + 當前選定班級的學生名單 ---
@app.get("/teacher/my_class")
def teacher_get_my_class(
    class_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    perform_auto_cleanup(db)

    # 自動修復因改名而斷開連結的孤兒班級
    all_db_classes = db.query(models.Classroom).all()
    for c in all_db_classes:
        owner_exists = db.query(models.User).filter(models.User.username == c.teacher_username).first()
        if not owner_exists:
            c.teacher_username = teacher.username
            db.commit()

    # 撈出該名老師名下的「所有班級」
    my_classes = db.query(models.Classroom).filter(
        models.Classroom.teacher_username == teacher.username
    ).order_by(models.Classroom.id.asc()).all()

    if not my_classes:
        return {"has_class": False, "classes": []}

    # 決定目前選中的是哪一個班級（若前端有傳 class_id 且屬於該老師就用它，否則預設選第一個）
    active_class = None
    if class_id:
        active_class = next((c for c in my_classes if c.id == class_id), None)
    if not active_class:
        active_class = my_classes[0]

    students = db.query(models.User).filter(
        models.User.class_id == active_class.id
    ).order_by(models.User.is_online.desc(), models.User.username.asc()).all()

    return {
        "has_class": True,
        "class_id": active_class.id,
        "class_name": active_class.name,
        "invite_code": active_class.invite_code,
        "classes": [
            {
                "id": c.id,
                "name": c.name,
                "invite_code": c.invite_code
            } for c in my_classes
        ],
        "students": [
            {
                "username": s.username,
                "email": s.email,
                "is_online": s.is_online
            } for s in students
        ]
    }


# --- 教師專用：新增班級 或 修改既有班級名稱 ---
class CreateClassRequest(BaseModel):
    name: str
    class_id: Optional[int] = None  # 若有傳 class_id 代表「修改該班級名稱」；若為 None 代表「建立一個新班級」

@app.post("/teacher/create_class")
def teacher_create_or_update_class(
    req: CreateClassRequest,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="班級名稱不能為空")

    # 模式 A：修改既有班級名稱
    if req.class_id:
        classroom = db.query(models.Classroom).filter(
            models.Classroom.id == req.class_id,
            models.Classroom.teacher_username == teacher.username
        ).first()
        if not classroom:
            raise HTTPException(status_code=404, detail="找不到要修改的班級")
        classroom.name = name
        db.commit()
        return {
            "status": "updated",
            "class_id": classroom.id,
            "class_name": classroom.name,
            "invite_code": classroom.invite_code
        }

    # 模式 B：新增一個全新班級（先檢查同老師是否已有同名班級）
    duplicate = db.query(models.Classroom).filter(
        models.Classroom.teacher_username == teacher.username,
        models.Classroom.name == name
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"您已經建立過名為「{name}」的班級囉！")

    # 產生不重複的 6 位數邀請碼
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    invite_code = ""
    for _ in range(20):
        candidate = "".join(random.choices(chars, k=6))
        if not db.query(models.Classroom).filter(models.Classroom.invite_code == candidate).first():
            invite_code = candidate
            break
    if not invite_code:
        invite_code = f"C{random.randint(10000, 99999)}"

    new_class = models.Classroom(
        name=name,
        teacher_username=teacher.username,
        invite_code=invite_code
    )
    db.add(new_class)
    db.commit()
    db.refresh(new_class)
    return {
        "status": "created",
        "class_id": new_class.id,
        "class_name": new_class.name,
        "invite_code": new_class.invite_code
    }

# --- 教師專用：刪除（解散）班級 ---
@app.delete("/teacher/classes/{class_id}")
def teacher_delete_class(
    class_id: int,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    classroom = db.query(models.Classroom).filter(
        models.Classroom.id == class_id,
        models.Classroom.teacher_username == teacher.username
    ).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="找不到該班級或您無權限刪除此班級")

    deleted_name = classroom.name

    # 1. 將該班級所有學生的 class_id 設為 None（變回一般玩家，保留所有遊戲與答題紀錄）
    db.query(models.User).filter(models.User.class_id == class_id).update(
        {"class_id": None}, synchronize_session=False
    )

    # 2. 刪除該班級專屬的考題與學習手冊字卡（不影響官方基底題庫）
    db.query(models.Question).filter(models.Question.class_id == class_id).delete(synchronize_session=False)
    db.query(models.HandbookCard).filter(models.HandbookCard.class_id == class_id).delete(synchronize_session=False)

    # 3. 記錄一筆通知給管理員，並刪除該班級資料列
    _log_teacher_action(db, teacher, classroom, "刪除", "班級", f"已解散班級：{deleted_name}")
    db.delete(classroom)
    db.commit()

    return {"status": "success", "deleted_class_id": class_id, "deleted_class_name": deleted_name}


# --- 教師專用：手動將學生加入「當前選定的班級」 ---
class AddStudentRequest(BaseModel):
    student_username: str
    class_id: Optional[int] = None

@app.post("/teacher/add_student")
def teacher_add_student(
    req: AddStudentRequest,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    classroom = _get_teacher_classroom(db, teacher, req.class_id)

    target_username = req.student_username.strip()
    student = db.query(models.User).filter(models.User.username == target_username).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"找不到帳號為「{target_username}」的玩家")
    if student.role in ("admin", "teacher"):
        raise HTTPException(status_code=400, detail="無法將管理員或其他老師加入班級")

    student.class_id = classroom.id
    db.commit()
    return {"status": "success", "username": student.username, "class_name": classroom.name}


# --- 教師專用：將學生從班級中剔除 ---
@app.delete("/teacher/students/{student_username}")
def teacher_kick_student(
    student_username: str,
    class_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    my_class_ids = [c.id for c in db.query(models.Classroom).filter(
        models.Classroom.teacher_username == teacher.username
    ).all()]
    if not my_class_ids:
        raise HTTPException(status_code=404, detail="找不到班級")

    student = db.query(models.User).filter(
        models.User.username == student_username,
        models.User.class_id.in_(my_class_ids)
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="該名學生不在您的班級中")

    student.class_id = None
    db.commit()
    return {"status": "success"}


# --- 教師專用：查看單一學生的學習狀況與類別統計 ---
@app.get("/teacher/student_stats/{student_username}")
def teacher_get_student_stats(
    student_username: str,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    my_class_ids = [c.id for c in db.query(models.Classroom).filter(
        models.Classroom.teacher_username == teacher.username
    ).all()]
    student = db.query(models.User).filter(models.User.username == student_username).first()
    if not student:
        raise HTTPException(status_code=404, detail="找不到該名學生")
    if teacher.role != "admin" and student.class_id not in my_class_ids:
        raise HTTPException(status_code=403, detail="該名學生不在您的班級中")

    stats = _build_learn_stats(student_username, db)
    logs_total = sum(d["total"] for d in stats["dimensions"])
    logs_correct = sum(d["correct"] for d in stats["dimensions"])
    if logs_total > stats["summary"]["total_questions"]:
        stats["summary"]["total_questions"] = logs_total
        stats["summary"]["correct"] = logs_correct
        stats["summary"]["accuracy"] = round(logs_correct / logs_total * 100) if logs_total else 0

    return stats


# ==========================================================
# 🏆 第三階段（多班級版）：教師專屬考題庫 & 學習手冊 CRUD
# ==========================================================

def _get_teacher_classroom(db: Session, teacher: models.User, class_id: Optional[int] = None) -> models.Classroom:
    """根據前端指定的 class_id 取得該老師的班級；若未指定則取該老師的第一個班級"""
    query = db.query(models.Classroom).filter(
        models.Classroom.teacher_username == teacher.username
    )
    if class_id:
        classroom = query.filter(models.Classroom.id == class_id).first()
        if classroom:
            return classroom

    classroom = query.order_by(models.Classroom.id.asc()).first()
    if not classroom:
        raise HTTPException(status_code=400, detail="請先至「學生管理」建立您的班級後，再進行此操作！")
    return classroom


def _log_teacher_action(db: Session, teacher: models.User, classroom: models.Classroom, action: str, target_type: str, detail: str):
    log = models.TeacherAuditLog(
        teacher_username=teacher.username,
        class_id=classroom.id,
        class_name=classroom.name,
        action=action,
        target_type=target_type,
        detail=(detail or "")[:250],
        is_read=False
    )
    db.add(log)


# --- 教師考題庫 API (支援多班級切換) ---
@app.get("/teacher/questions/meta")
def teacher_question_meta(
    class_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    from sqlalchemy import or_
    my_classes = db.query(models.Classroom).filter(models.Classroom.teacher_username == teacher.username).all()
    active_c = next((c for c in my_classes if c.id == class_id), my_classes[0] if my_classes else None)
    c_id = active_c.id if active_c else -1

    topics = [t for (t,) in db.query(models.Question.topic)
              .filter(models.Question.topic.isnot(None),
                      or_(models.Question.class_id.is_(None), models.Question.class_id == c_id))
              .distinct().order_by(models.Question.topic).all()]
    return {
        "topics": topics,
        "qtypes": list(QTYPES),
        "difficulties": list(DIFFICULTIES),
        "categories": list(CATEGORIES),
    }


@app.get("/teacher/questions")
def teacher_list_questions(
    class_id: Optional[int] = None,
    qtype: Optional[str] = None,
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    source: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher),
):
    from sqlalchemy import or_
    my_classes = db.query(models.Classroom).filter(
        models.Classroom.teacher_username == teacher.username
    ).order_by(models.Classroom.id.asc()).all()

    active_c = next((c for c in my_classes if c.id == class_id), my_classes[0] if my_classes else None)
    c_id = active_c.id if active_c else None

    query = db.query(models.Question)
    if source == "class":
        if not c_id:
            return {"total": 0, "class_id": None, "class_name": None, "classes": [], "items": []}
        query = query.filter(models.Question.class_id == c_id)
    elif source == "official":
        query = query.filter(models.Question.class_id.is_(None))
    else:
        if c_id:
            query = query.filter(or_(models.Question.class_id.is_(None), models.Question.class_id == c_id))
        else:
            query = query.filter(models.Question.class_id.is_(None))

    if qtype:
        query = query.filter(models.Question.qtype == qtype)
    if difficulty:
        query = query.filter(models.Question.difficulty == difficulty)
    if topic:
        query = query.filter(models.Question.topic == topic)
    if q and q.strip():
        query = query.filter(models.Question.content.like("%" + q.strip() + "%"))

    class_priority = case((models.Question.class_id.isnot(None), 1), else_=0)
    rows = query.order_by(class_priority.desc(), models.Question.id.desc()).all()
    return {
        "total": len(rows),
        "class_id": c_id,
        "class_name": active_c.name if active_c else None,
        "classes": [{"id": c.id, "name": c.name} for c in my_classes],
        "items": [question_to_dict(r) for r in rows]
    }


@app.post("/teacher/questions")
def teacher_create_question(
    payload: QuestionPayload,
    class_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    classroom = _get_teacher_classroom(db, teacher, class_id)
    clean_data = validate_question(payload)
    row = models.Question(**clean_data, class_id=classroom.id, created_by=teacher.username)
    db.add(row)
    _log_teacher_action(db, teacher, classroom, "新增", "考題庫", f"[{row.topic}] {row.content[:60]}")
    db.commit()
    db.refresh(row)
    return question_to_dict(row)


@app.put("/teacher/questions/{question_id}")
def teacher_update_question(
    question_id: int,
    payload: QuestionPayload,
    class_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    my_classes = {c.id: c for c in db.query(models.Classroom).filter(models.Classroom.teacher_username == teacher.username).all()}
    row = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="找不到這一題")
    if row.class_id not in my_classes:
        raise HTTPException(status_code=403, detail="官方預設題目僅供檢視；您可以新增班級專屬題目！")

    classroom = my_classes[row.class_id]
    for k, v in validate_question(payload).items():
        setattr(row, k, v)
    _log_teacher_action(db, teacher, classroom, "修改", "考題庫", f"#{row.id} [{row.topic}] {row.content[:60]}")
    db.commit()
    db.refresh(row)
    return question_to_dict(row)


@app.delete("/teacher/questions/{question_id}")
def teacher_delete_question(
    question_id: int,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    my_classes = {c.id: c for c in db.query(models.Classroom).filter(models.Classroom.teacher_username == teacher.username).all()}
    row = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="找不到這一題")
    if row.class_id not in my_classes:
        raise HTTPException(status_code=403, detail="無法刪除官方預設題目")

    classroom = my_classes[row.class_id]
    detail_preview = f"#{row.id} [{row.topic}] {row.content[:60]}"
    db.delete(row)
    _log_teacher_action(db, teacher, classroom, "刪除", "考題庫", detail_preview)
    db.commit()
    return {"message": "success", "id": question_id}


# --- 教師學習手冊 API (支援多班級切換) ---
@app.get("/teacher/handbook/list")
def teacher_list_handbook(
    class_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    from sqlalchemy import or_
    base_count = db.query(models.HandbookCard).filter(models.HandbookCard.class_id.is_(None)).count()
    if base_count == 0:
        seed_handbook.seed_handbook_data(db)

    my_classes = db.query(models.Classroom).filter(
        models.Classroom.teacher_username == teacher.username
    ).order_by(models.Classroom.id.asc()).all()

    active_c = next((c for c in my_classes if c.id == class_id), my_classes[0] if my_classes else None)
    c_id = active_c.id if active_c else None

    if c_id:
        cards = db.query(models.HandbookCard).filter(
            or_(models.HandbookCard.class_id.is_(None), models.HandbookCard.class_id == c_id)
        ).order_by(models.HandbookCard.order_index.asc(), models.HandbookCard.id.asc()).all()
    else:
        cards = db.query(models.HandbookCard).filter(
            models.HandbookCard.class_id.is_(None)
        ).order_by(models.HandbookCard.order_index.asc(), models.HandbookCard.id.asc()).all()

    return {
        "class_id": c_id,
        "class_name": active_c.name if active_c else None,
        "classes": [{"id": c.id, "name": c.name} for c in my_classes],
        "items": cards
    }


@app.post("/teacher/handbook/add")
def teacher_add_handbook(
    card: HandbookCreate,
    class_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    classroom = _get_teacher_classroom(db, teacher, class_id)
    new_card = models.HandbookCard(**card.dict(), class_id=classroom.id, created_by=teacher.username)
    db.add(new_card)
    _log_teacher_action(db, teacher, classroom, "新增", "學習手冊", f"[{card.cat_name}] {card.title}")
    db.commit()
    db.refresh(new_card)
    return {"status": "success", "card_id": new_card.id}


@app.put("/teacher/handbook/{card_id}")
def teacher_update_handbook(
    card_id: int,
    card: HandbookCreate,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    my_classes = {c.id: c for c in db.query(models.Classroom).filter(models.Classroom.teacher_username == teacher.username).all()}
    target = db.query(models.HandbookCard).filter(models.HandbookCard.id == card_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到此知識卡片")
    if target.class_id not in my_classes:
        raise HTTPException(status_code=403, detail="官方預設手冊僅供檢視；您可以新增班級專屬字卡！")

    classroom = my_classes[target.class_id]
    for key, value in card.dict().items():
        setattr(target, key, value)
    _log_teacher_action(db, teacher, classroom, "修改", "學習手冊", f"[{card.cat_name}] {card.title}")
    db.commit()
    return {"status": "success", "msg": "教材已更新"}


@app.delete("/teacher/handbook/{card_id}")
def teacher_delete_handbook(
    card_id: int,
    db: Session = Depends(database.get_db),
    teacher: models.User = Depends(require_teacher)
):
    my_classes = {c.id: c for c in db.query(models.Classroom).filter(models.Classroom.teacher_username == teacher.username).all()}
    target = db.query(models.HandbookCard).filter(models.HandbookCard.id == card_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到此知識卡片")
    if target.class_id not in my_classes:
        raise HTTPException(status_code=403, detail="無法刪除官方預設字卡")

    classroom = my_classes[target.class_id]
    detail_preview = f"[{target.cat_name}] {target.title}"
    db.delete(target)
    _log_teacher_action(db, teacher, classroom, "刪除", "學習手冊", detail_preview)
    db.commit()
    return {"status": "success", "msg": "教材已刪除"}

# ==========================================================
# 🏆 教師資格申請與管理員審核系統 (含證書上傳 & 自動寄信通知)
# ==========================================================

CERT_UPLOAD_DIR = os.path.join("static", "uploads", "teacher_certs")
os.makedirs(CERT_UPLOAD_DIR, exist_ok=True)
ALLOWED_CERT_EXTS = {".pdf", ".jpg", ".jpeg", ".png"}


def _send_teacher_review_email(to_email: str, real_name: str, username: str, approved: bool, reason: str = "") -> tuple[bool, str]:
    """審核完成後寄發通知信，並回傳 (是否成功, 狀態訊息) 供管理員前端即時顯示"""
    # 每次寄信前重新載入一次 .env，避免重設環境變數沒讀到
    load_dotenv(override=True)
    sender_email = (os.getenv("SENDER_EMAIL") or SENDER_EMAIL or "").strip()
    sender_pwd = (os.getenv("SENDER_PASSWORD") or SENDER_PASSWORD or "").strip()

    if not sender_email or not sender_pwd:
        msg = "未讀取到 .env 的 SENDER_EMAIL 或 SENDER_PASSWORD（請確認 .env 與 main.py 同目錄，且檔名不是 .env.txt）"
        print(f"ℹ️ [略過寄信] {msg}")
        return False, msg

    try:
        if approved:
            subject = "【BeeRich 碼上致富】🎉 教師資格審核通過通知"
            body = (
                f"親愛的 {real_name} 老師（遊戲帳號：{username}）您好：\n\n"
                f"恭喜您！您提交的「BeeRich 教師資格審核」已經正式通過！\n"
                f"您的帳號身分已升級為「教師（Teacher）」。\n\n"
                f"現在您可以直接前往 BeeRich 遊戲系統登入，系統將自動引導您進入「教師管理後台」\n"
                f"（或可由遊戲大廳右側選單點選「🧑‍🏫 教師資格」進入教師後台），\n"
                f"開始建立您的專屬班級、查看學生學習狀況，以及管理班級專屬考題庫與學習手冊！\n\n"
                f"祝您教學愉快！\n"
                f"BeeRich 碼上致富 系統團隊 敬上"
            )
        else:
            subject = "【BeeRich 碼上致富】⚠️ 教師資格審核結果通知（未通過）"
            body = (
                f"親愛的 {real_name}（遊戲帳號：{username}）您好：\n\n"
                f"感謝您申請 BeeRich 教師資格。經管理員審核後，本次申請暫未通過，原因如下：\n"
                f"「{reason}」\n\n"
                f"請您登入 BeeRich 遊戲大廳，於右側選單點選「🧑‍🏫 教師資格」查看詳情，\n"
                f"修正並備妥相關資料後即可再次提交申請。\n\n"
                f"BeeRich 碼上致富 系統團隊 敬上"
            )

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            clean_pwd = sender_pwd.replace(" ", "")
            server.login(sender_email, clean_pwd)
            server.sendmail(sender_email, [to_email], msg.as_string())

        print(f"📧 已成功由 {sender_email} 寄出教師審核通知信至 {to_email}")
        return True, f"已成功寄送通知信至 {to_email}"
    except Exception as e:
        err_str = f"{type(e).__name__}: {e}"
        print(f"❌ 教師審核通知信寄送失敗: {err_str}")
        return False, err_str


# 1. 玩家端：查詢自己目前的最新申請狀態與身分
@app.get("/teacher_apply/my_status")
def get_my_teacher_apply_status(
    authorization: str = Header(None),
    db: Session = Depends(database.get_db)
):
    username = auth_utils.get_current_user(authorization)
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")

    latest_app = (
        db.query(models.TeacherApplication)
        .filter(models.TeacherApplication.username == username)
        .order_by(models.TeacherApplication.id.desc())
        .first()
    )

    # 🏆 核心修正：如果該帳號目前已是一般玩家 (player)，但過去曾有 approved 的舊紀錄，
    # 代表已被管理員撤銷教師身分，直接視為無申請狀態（回傳 None），讓前端顯示全新的申請表單！
    if user.role == "player" and latest_app and latest_app.status == "approved":
        latest_app = None

    return {
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "application": {
            "id": latest_app.id,
            "real_name": latest_app.real_name,
            "email": latest_app.email,
            "teaching_goal": latest_app.teaching_goal,
            "cert_file_url": latest_app.cert_file_url,
            "status": latest_app.status,  # pending / reviewing / approved / rejected
            "reject_reason": latest_app.reject_reason,
            "created_at": latest_app.created_at,
            "reviewed_at": latest_app.reviewed_at,
        } if latest_app else None
    }


# 2. 玩家端：提交（或重新提交）教師資格申請
@app.post("/teacher_apply/submit")
async def submit_teacher_application(
    real_name: str = Form(...),
    email: str = Form(...),
    teaching_goal: str = Form(...),
    cert_file: UploadFile = File(...),
    authorization: str = Header(None),
    db: Session = Depends(database.get_db)
):
    username = auth_utils.get_current_user(authorization)
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")

    # 檢查是否有正在「待審核」或「審核中」的申請，避免重複狂送
    active_app = (
        db.query(models.TeacherApplication)
        .filter(
            models.TeacherApplication.username == username,
            models.TeacherApplication.status.in_(["pending", "reviewing"])
        )
        .first()
    )
    if active_app:
        raise HTTPException(status_code=400, detail="您已有正在審核中的申請，請靜候審核結果！")

    real_name = real_name.strip()
    email = email.strip()
    teaching_goal = teaching_goal.strip()
    if not real_name or not email or not teaching_goal:
        raise HTTPException(status_code=400, detail="請完整填寫姓名、信箱與教學目標！")

    # 檢查檔案副檔名 (.pdf / .jpg / .png)
    orig_filename = cert_file.filename or ""
    ext = os.path.splitext(orig_filename)[1].lower()
    if ext not in ALLOWED_CERT_EXTS:
        raise HTTPException(status_code=400, detail="教師資格證僅限上傳 PDF、JPG 或 PNG 格式！")

    content = await cert_file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="檔案大小請勿超過 10MB")

    safe_name = f"cert_{username}_{int(datetime.utcnow().timestamp())}{ext}"
    save_path = os.path.join(CERT_UPLOAD_DIR, safe_name)
    with open(save_path, "wb") as f:
        f.write(content)

    file_url = f"/static/uploads/teacher_certs/{safe_name}"

    new_app = models.TeacherApplication(
        username=username,
        real_name=real_name,
        email=email,
        teaching_goal=teaching_goal,
        cert_file_url=file_url,
        status="pending"
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return {"status": "success", "application_id": new_app.id}


# 3. 管理員端：取得所有教師資格申請列表 (含待處理數量統計)
@app.get("/admin/teacher_applications")
def admin_list_teacher_applications(
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(require_admin)
):
    apps = db.query(models.TeacherApplication).order_by(models.TeacherApplication.id.desc()).all()
    pending_count = sum(1 for a in apps if a.status in ("pending", "reviewing"))
    return {
        "pending_count": pending_count,
        "items": [
            {
                "id": a.id,
                "username": a.username,
                "real_name": a.real_name,
                "email": a.email,
                "teaching_goal": a.teaching_goal,
                "cert_file_url": a.cert_file_url,
                "status": a.status,
                "reject_reason": a.reject_reason,
                "created_at": a.created_at,
                "reviewed_at": a.reviewed_at,
                "reviewed_by": a.reviewed_by,
            } for a in apps
        ]
    }


# 4. 管理員端：點進單筆申請時，將 pending 自動改為 reviewing (讓老師端看到「審核中」)
@app.post("/admin/teacher_applications/{app_id}/mark_reviewing")
def admin_mark_application_reviewing(
    app_id: int,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(require_admin)
):
    app_row = db.query(models.TeacherApplication).filter(models.TeacherApplication.id == app_id).first()
    if not app_row:
        raise HTTPException(status_code=404, detail="找不到該筆申請")

    if app_row.status == "pending":
        app_row.status = "reviewing"
        db.commit()
    return {"status": "success", "current_status": app_row.status}


# 5. 管理員端：審核通過或未通過
class ReviewApplicationRequest(BaseModel):
    action: str  # "approve" 或 "reject"
    reject_reason: Optional[str] = None

@app.post("/admin/teacher_applications/{app_id}/review")
def admin_review_teacher_application(
    app_id: int,
    req: ReviewApplicationRequest,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(require_admin)
):
    app_row = db.query(models.TeacherApplication).filter(models.TeacherApplication.id == app_id).first()
    if not app_row:
        raise HTTPException(status_code=404, detail="找不到該筆申請")

    applicant = db.query(models.User).filter(models.User.username == app_row.username).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="找不到該申請人的玩家帳號")

    if req.action == "approve":
        app_row.status = "approved"
        app_row.reject_reason = None
        app_row.reviewed_at = datetime.utcnow()
        app_row.reviewed_by = admin.username
        if applicant.role != "admin":
            applicant.role = "teacher"
        db.commit()

        sent, mail_msg = _send_teacher_review_email(
            app_row.email, app_row.real_name, app_row.username, True, ""
        )
        return {
            "status": "approved",
            "username": applicant.username,
            "email_sent": sent,
            "email_msg": mail_msg
        }

    elif req.action == "reject":
        reason = (req.reject_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="請填寫未通過的原因！")
        app_row.status = "rejected"
        app_row.reject_reason = reason
        app_row.reviewed_at = datetime.utcnow()
        app_row.reviewed_by = admin.username
        db.commit()

        sent, mail_msg = _send_teacher_review_email(
            app_row.email, app_row.real_name, app_row.username, False, reason
        )
        return {
            "status": "rejected",
            "username": applicant.username,
            "email_sent": sent,
            "email_msg": mail_msg
        }

    else:
        raise HTTPException(status_code=400, detail="無效的審核動作")