from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
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




# 🏆 自動建立 MySQL 資料庫表格
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")

sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# 🏆 用來存放所有線上房間的「記憶體筆記本」
# 只要伺服器沒關，房間資料都會存在這
active_rooms = {}

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

# 📧 Gmail SMTP 設定
SENDER_EMAIL = "pypoly.service@gmail.com" 
SENDER_PASSWORD = "qfdi cvye mwdu xbyh" 

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
    # 🏆 設定 30 秒為判定標準
    threshold = datetime.utcnow() - timedelta(seconds=60)
    
    # 找出那些「在線中」但「超過 30 秒沒說話」的人
    offline_users = db.query(models.User).filter(
        models.User.is_online == 1, 
        models.User.last_active < threshold
    ).all()
    
    if offline_users:
        for u in offline_users:
            u.is_online = 0
            print(f"🧹 [自動清理] 偵測到使用者 {u.username} 超時，已強制登出。")
        db.commit()

def clear_old_room(username):
    # 找到該用戶創立的舊房間
    old_room_code = find_room_by_host(username)
    if old_room_code:
        # 🏆 不要只刪除引用，要徹底清空數據
        rooms_data[old_room_code]['players'] = []
        del rooms_data[old_room_code]

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
    background_tasks.add_task(perform_auto_cleanup, db)
    
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
    background_tasks.add_task(perform_auto_cleanup, db)
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

# 6. 管理員：獲取所有用戶 (加權排序)
@app.get("/admin/users")
def get_all_users(db: Session = Depends(database.get_db)):
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
def update_user_role(target_username: str, data: dict, db: Session = Depends(database.get_db)):
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


# --- main.py 最終修復版本 (請確保這是檔案中唯一一個 /ws/vision/game_start) ---
# --- main.py 唯一版本 ---
# --- main.py 第二步修改：數據接收版 ---

@app.websocket("/ws/vision/game_start")
async def vision_game_start(websocket: WebSocket):
    await websocket.accept()
    detector = GestureDetector()
    try:
        while True:
            data = await websocket.receive_json()
            landmarks = data.get("landmarks")
            # 🏆 增加錯誤檢查，確保數據存在
            if not landmarks:
                await websocket.send_json({"status": "WAITING", "hand_x": None, "hand_y": None})
                continue

            # 運算並抓取可能的錯誤
            try:
                result = detector.process_data(landmarks, data.get("width"), data.get("height"))
                await websocket.send_json(result)
            except Exception as inner_e:
                print(f"🔥 GestureDetector 內部錯誤: {inner_e}")
                await websocket.send_json({"status": "ERROR_IN_LOGIC"})

            if result.get("done"):
                break
    except Exception as e:
        print(f"❌ WebSocket 斷開或異常: {e}")

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

@app.route('/rooms', methods=['GET'])
def get_rooms():
    active_rooms = []
    for name, data in rooms_data.items():
        active_rooms.append({
            'name': name,
            'mode': data.get('mode'),
            'laps': data.get('laps'),
            'difficulty': data.get('difficulty'), # 🚀 確保有傳出難度
            'max_players': data.get('max_players', 2),
            'players': data.get('players', []) # 🚀 傳出目前玩家清單以計算人數
        })
    return jsonify(active_rooms)

# 在 main.py 的獲取房間路由中加入過濾
@app.route('/rooms/public', methods=['GET'])
def get_public_rooms():
    active_rooms = []
    for code, room in rooms_data.items():
        # 🏆 增加條件：只有人數 > 0 且房主在線的房間才顯示
        if len(room.get('players', [])) > 0:
            active_rooms.append(room)
    return jsonify(active_rooms)

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

# --- 修正 2：handle_buy_land ---
@sio.on('buy_land')
async def handle_buy_land(sid, data): # 🏆 加入 sid 參數
    room = data['room']
    user = data['user']
    tile_index = data['tileIndex']
    
    player_colors = {"Player1": "#4facfe", "Player2": "#ffde59"}
    color = player_colors.get(user, "#ffffff")

    # 🏆 使用 await 並加上 async
    await sio.emit('land_bought_sync', {
        'user': user,
        'tileIndex': tile_index,
        'color': color
    }, room=room)
    
    await sio.emit('next_turn_trigger', {'next_player': 'opponent'}, room=room)

@sio.on('char_data_sync')
async def handle_char_data_sync(sid, data):
    room = data.get('room')
    if room:
        await sio.emit('char_data_sync', data, room=room, skip_sid=sid)