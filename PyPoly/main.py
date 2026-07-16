# 🏆 UTF-8 輸出保險：避免在 cp950(繁中) 主控台下，含 emoji 的 print 造成 UnicodeEncodeError 讓請求崩潰
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models, auth_utils, database
import smtplib, random, requests, base64, cv2
import numpy as np
from email.mime.text import MIMEText
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import case
from game_start import GestureDetector
import asyncio
import socketio
from fastapi import Query
import game_start # 🏆 關鍵新增：把整個模組抓進來，準備竄改它的全域變數
from sqlalchemy import func
from collections import Counter  # 🏆 需求⑨：統計最常出現語法
# main.py
import os
import base64
from fastapi.staticfiles import StaticFiles
from PIL import Image # 需安裝 pillow: pip install Pillow
import io
from dotenv import load_dotenv

# 🏆 讀取 PyPoly/.env（機敏設定：SENDER_EMAIL / SENDER_PASSWORD / SECRET_KEY 等）
load_dotenv()



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

# 定義接收的資料結構
class RoomSchema(BaseModel):
    hostId: str
    name: str
    mode: str
    difficulty: str
    winLaps: str
    type: str
    code: str

@app.on_event("startup")
async def start_cleanup_task():
    async def cleanup_loop():
        while True:
            # 建立一個新的資料庫連線來清理
            db = database.SessionLocal()
            try:
                perform_auto_cleanup(db)
            finally:
                db.close()
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
GOOGLE_CLIENT_ID = "111298973031-n8e4s6353pgiqpc74p5hl4vul2j6c7pt.apps.googleusercontent.com"
ADMIN_EMAILS = ["admin@gmail.com"]

# 📧 Gmail SMTP 設定（改由環境變數提供；請於 PyPoly/.env 填入，切勿寫死於程式碼）
#    ⚠️ 原先寫死的應用程式密碼已移除，請至 Google 帳戶撤銷該密碼並重新產生。
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

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
    return {
        "username": user.username, 
        "is_online": user.is_online,
        "role": user.role,
        "email": user.email
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
@app.get("/admin/users")
def get_all_users(db: Session = Depends(database.get_db), admin: models.User = Depends(require_admin)):
    perform_auto_cleanup(db)
    
    # 🏆 admin 優先級高，排最前
    admin_priority = case(
        (models.User.role == 'admin', 1),
        else_=0
    )
    
    users = db.query(models.User).order_by(
        admin_priority.desc(),
        models.User.is_online.desc(),
        models.User.username.asc()
    ).all()
    
    return [
        {
            "username": u.username, 
            "email": u.email, 
            "role": u.role, 
            "is_online": u.is_online
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

# 8. 註冊與 ID 檢查
@app.get("/auth/check-id")
def check_id(username: str, db: Session = Depends(database.get_db)):
    exists = db.query(models.User).filter(models.User.username == username).first() is not None
    return {"exists": exists}

@app.post("/auth/register")
def register(user: UserCreate, db: Session = Depends(database.get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="ID 已被使用")
    user_role = "admin" if user.email in ADMIN_EMAILS else "player"
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=auth_utils.get_password_hash(user.password),
        role=user_role,
        is_online=0
    )
    db.add(new_user)
    db.commit()
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




class AvatarUpload(BaseModel):
    username: str
    image: str # Base64 字串

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
    if room.code in active_rooms:
        raise HTTPException(status_code=400, detail="代碼已存在")
    
    # 🏆 修正：初始化時就建立 players 陣列，並把房主放進去
    room_dict = room.dict()
    room_dict['players'] = [room.hostId] 
    room_dict['status'] = 'waiting'
    room_dict['is_started'] = False
    
    active_rooms[room.code] = room_dict
    return room_dict

# --- 核心邏輯：獲取所有公開房間 ---
@app.get("/rooms/public")
async def get_public_rooms():
    # 只回傳類型為「公開」或「public」的房間
    return [r for r in active_rooms.values() if r.get('type') in ['public', '公開']]

# --- 核心邏輯：刪除房間 (解決解散不掉的問題) ---
@app.delete("/rooms/delete/{code}")
async def delete_room(code: str):
    if code in active_rooms:
        del active_rooms[code]
        _clear_room_dice_state(code)  # 🏆 一併清掉擲骰暫存，避免同房號重開有殘留
        print(f"🔥 房間 {code} 已被刪除")
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="房間不存在")


@app.post("/rooms/join/{code}")
async def join_room(code: str, username: str):
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="房間不存在")
    
    room = active_rooms[code]
    if username not in room['players']:
        if len(room['players']) >= 2:
            raise HTTPException(status_code=400, detail="房間已滿")
        room['players'].append(username)
    
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
                print(f"🧹 房間 {code} 已空，自動清理完成")
            
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
    if room['hostId'] != username:
        raise HTTPException(status_code=403, detail="只有房主可以開始遊戲")

    room['status'] = 'gaming'
    room['is_started'] = True

    # 🏆 務必回傳整個 room，這樣房主端 localStorage.setItem(JSON.stringify(latestData)) 才有資料
    return room

# 🏆 修正：讓玩家連線進入 Socket 房間，否則訊息發不出去
# 在 handle_order_dice 附近加入這個函式
# 🏆 必須加入此監聽器，否則 emit(room=room) 會找不到對象
@sio.on('join_game_room')
async def handle_join_game_room(sid, data):
    room = data.get('room')
    user = data.get('user')
    if room:
        await sio.enter_room(sid, room)
        print(f"✅ [Socket 房門已開] 使用者 {user} 已進入房間: {room}")

# 在 main.py 中檢查或加入此段
@sio.on('start_game_request')
async def handle_start_game(sid, data):
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
    room = data.get('room')
    if room in room_dice_data:
        room_dice_data[room] = {}
        print(f"🔄 房間 {room} 點數已重置 (平手重新擲骰)")

# 在 main.py 中加入或修改此 Socket 監聽器
@sio.on('broadcast_dice_event')
async def handle_dice_event(sid, data):
    # data 格式範例: {"room": "ROOM123", "user": "玩家ID", "type": "ROLLING" 或 "RESULT", "point": 5}
    room = data.get('room')
    print(f"📣 廣播擲骰事件: {data}")
    await sio.emit('dice_event_sync', data, room=room)

# 在 main.py 中加入此段落
@sio.on('player_move_sync_request')
async def handle_move_request(sid, data):
    room = data.get('room')
    print(f"🚀 收到移動請求，正在廣播給房間 {room}: {data}")
    # 🏆 關鍵：將訊息廣播給房間內所有人 (包含發送者自己)
    # 這樣所有人的電腦都會觸發 socket.on('player_move_sync')
    await sio.emit('player_move_sync', data, room=room)

@sio.on('player_move_finished_event')
async def handle_move_finished(sid, data):
    room = data.get('room')
    # 通知所有人清空提示訊息
    await sio.emit('player_move_finished', data, room=room)

@app.get("/game/map_config")
async def get_map_config(mode: str, difficulty: str, db: Session = Depends(database.get_db)):
    try:
        # 修正中文模式轉為資料庫 Key
        db_mode = "basic" if "基礎" in mode else "advanced"
        
        # 🏆 修正點：直接使用 func.random()，不要透過 models.database
        questions = db.query(models.Question).filter(
            models.Question.category == db_mode,
            models.Question.difficulty == difficulty
        ).order_by(func.random()).limit(20).all()
        
        countries = db.query(models.CountryScenario).order_by(func.random()).limit(20).all()

        if not questions or not countries:
             return {"error": "資料庫資料不足", "q_count": len(questions), "c_count": len(countries)}

        adventure_tiles = []
        for i in range(20):
            q = questions[i % len(questions)]
            c = countries[i % len(countries)]
            
            adventure_tiles.append({
                "type": "ADVENTURE",
                "id": c.id,
                "data": { 
                    "name": c.name,
                    "scenario": c.scenario,
                    "skybox_url": c.skybox_url,
                    "base_price": c.base_price,  # 🏆 補上收購價
                    "base_toll": c.base_toll,    # 🏆 補上過路費
                    "question": {
                        "id": q.id,                # 🏆 需求⑨：作答紀錄用
                        "category": q.category,    # 🏆 需求⑨：最常出現語法統計用
                        "content": q.content,
                        # 🏆 需求①：加入 opt4，並濾掉 None（進階題無選項時才不會出現空泡泡）
                        "options": [o for o in [q.opt1, q.opt2, q.opt3, q.opt4] if o],
                        "answer": q.answer
                    }
                }
            })

        full_map = [None] * 26
        full_map[0] = {"type": "START", "name": "起點"}
        full_map[13] = {"type": "JAIL", "name": "監獄"}
        full_map[6] = {"type": "PUNISH", "name": "開合跳"}
        full_map[19] = {"type": "REWARD", "name": "獎勵遊戲"}
        full_map[3] = {"type": "SHOP", "name": "道具店"}
        full_map[16] = {"type": "SHOP", "name": "道具店"}

        adv_idx = 0
        for i in range(26):
            if full_map[i] is None:
                full_map[i] = adventure_tiles[adv_idx]
                adv_idx += 1

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
    room = data['room']
    user = data['user']
    tile_index = data['tileIndex']
    price = data.get('price', 500)

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
        'price': price
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

    # 2. 抓取該地點的「即時人流」與「AQI」 [需求：根據實際人流計算]
    real_crowd = await fetch_nantou_live_data(land.name)
    real_aqi = random.randint(15, 160) # 同理可串接環境監測 API

    # 3. ⚖️ 重新定義收購價計算
    # 總收購價 = 土地基本價 + (當下人流 * 加成權重)
    crowd_bonus = int(real_crowd * 0.8)
    total_acquisition_price = land.base_price + crowd_bonus

    # 4. 🏆 [需求修正] 過路費邏輯：
    # 這裡回傳的是「保底過路費」，直接從資料庫讀取，不進行 15% 的計算。
    # 這讓玩家知道：「即使沒人流，我至少能收多少錢」。
    display_base_toll = land.base_toll if hasattr(land, 'base_toll') else 200

    return {
        "name": land.name,
        "scenario": land.scenario,
        "base_price": land.base_price,
        "crowd": real_crowd,
        "crowd_bonus": crowd_bonus,
        "total_price": total_acquisition_price,
        "toll": display_base_toll, # 顯示的是保底過路費
        "aqi": real_aqi
    }

# main.py 確保包含這兩段 (刪除舊的 sync_adventure_start/state)
@sio.on('sync_adventure_phase')
async def handle_adv_phase(sid, data):
    # data 包含: room, user, phase (NARRATIVE/QUIZ/DECISION), payload
    await sio.emit('adventure_phase_broadcast', data, room=data.get('room'), skip_sid=sid)

@sio.on('sync_adventure_choice')
async def handle_choice_sync(sid, data):
    # 用來同步按鈕亮燈 (1,2,3,4 或 LIKE, DISLIKE)
    await sio.emit('adventure_choice_broadcast', data, room=data.get('room'), skip_sid=sid)

@sio.on('next_turn_trigger')
async def handle_next_turn(sid, data):
    # data 包含: room, next_player
    # 🏆 核心：發送 next_turn_sync 給房間所有人，告知該回合徹底結束
    await sio.emit('next_turn_sync', data, room=data.get('room'))

@sio.on('update_pose_count')
async def handle_update_pose_count(sid, data):
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