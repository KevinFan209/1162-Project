from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models, auth_utils, database
import smtplib, random, requests
from email.mime.text import MIMEText
from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import case
from game_start import GestureDetector
import asyncio
import socketio


models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

active_rooms: Dict[str, dict] = {}
otp_storage: Dict[str, str] = {}
room_dice_data: Dict[str, dict] = {}

# --- Pydantic models ---

class RoomSchema(BaseModel):
    hostId: str
    name: str
    mode: str
    difficulty: str
    winLaps: str
    type: str
    code: str

class UserLogin(BaseModel):
    username: str
    password: str

class GoogleTokenRequest(BaseModel):
    access_token: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# --- Config ---

GOOGLE_CLIENT_ID = "111298973031-n8e4s6353pgiqpc74p5hl4vul2j6c7pt.apps.googleusercontent.com"
ADMIN_EMAILS = ["admin@gmail.com"]
SENDER_EMAIL = "pypoly.service@gmail.com"
SENDER_PASSWORD = "qfdi cvye mwdu xbyh"

# --- Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/login.html")


# --- Startup ---

@app.on_event("startup")
async def start_cleanup_task():
    async def cleanup_loop():
        while True:
            db = database.SessionLocal()
            try:
                perform_auto_cleanup(db)
            finally:
                db.close()
            await asyncio.sleep(10)
    asyncio.create_task(cleanup_loop())

# --- Helpers ---

def send_otp_email(to_email: str, otp: str):
    msg = MIMEText(f"您的 BeeRich 驗證碼為：{otp}\n\n此驗證碼將在 10 分鐘內有效。", 'plain', 'utf-8')
    msg['Subject'] = "BeeRich 驗證碼"
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        pass  # log removed (non-ASCII)

def perform_auto_cleanup(db: Session):
    threshold = datetime.utcnow() - timedelta(seconds=60)
    offline_users = db.query(models.User).filter(
        models.User.is_online == 1,
        models.User.last_active < threshold
    ).all()
    if offline_users:
        for u in offline_users:
            u.is_online = 0
            pass  # log removed (non-ASCII)
        db.commit()

# --- Auth routes ---

@app.post("/auth/login")
def login(user: UserLogin, db: Session = Depends(database.get_db)):
    perform_auto_cleanup(db)
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth_utils.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    if db_user.role == "banned":
        raise HTTPException(status_code=403, detail="您的帳號已被封鎖，請聯繫管理員。")
    if db_user.is_online == 1:
        raise HTTPException(status_code=403, detail="該帳號已在其他地方登入中，請先登出。")
    db_user.is_online = 1
    db_user.last_active = datetime.utcnow()
    db.commit()
    token = auth_utils.create_access_token(data={"sub": db_user.username, "role": db_user.role})
    return {"access_token": token, "role": db_user.role, "username": db_user.username}

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

@app.post("/auth/heartbeat")
def heartbeat(username: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        user.last_active = datetime.utcnow()
        db.commit()
    return {"status": "alive"}

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

@app.post("/auth/logout")
def logout(username: str, db: Session = Depends(database.get_db), confirm: Optional[str] = None):
    if confirm == "true":
        db_user = db.query(models.User).filter(models.User.username == username).first()
        if db_user:
            db_user.is_online = 0
            db.commit()
            pass  # log removed (non-ASCII)
            return {"status": "success", "message": "Logged out"}
    pass  # log removed (non-ASCII)
    return {"status": "ignored"}

@app.post("/auth/verify_and_refresh")
def verify_and_refresh(username: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=401)
    user.is_online = 1
    user.last_active = datetime.utcnow()
    db.commit()
    return {"status": "success"}

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

@app.post("/auth/forgot-password")
def forgot_password(req: dict, db: Session = Depends(database.get_db)):
    email = req.get("email")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到此 Email 帳號")
    otp = str(random.randint(100000, 999999))
    otp_storage[email] = otp
    send_otp_email(email, otp)
    return {"message": "sent"}

@app.post("/auth/reset-password")
def reset_password(req: dict, db: Session = Depends(database.get_db)):
    email = req.get("email")
    code = req.get("code")
    new_password = req.get("new_password")
    if not email or not code or not new_password:
        raise HTTPException(status_code=400, detail="缺少必要欄位")
    stored_otp = otp_storage.get(email)
    if not stored_otp or stored_otp != code:
        raise HTTPException(status_code=400, detail="驗證碼錯誤或已過期")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到此帳號")
    user.hashed_password = auth_utils.get_password_hash(new_password)
    db.commit()
    del otp_storage[email]
    return {"message": "success"}

@app.post("/auth/send-otp-new-email")
def send_otp_new_email(req: dict, db: Session = Depends(database.get_db)):
    email = req.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email 不能為空")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="此 Email 已被使用")
    otp = str(random.randint(100000, 999999))
    otp_storage[f"new_email:{email}"] = otp
    send_otp_email(email, otp)
    return {"message": "sent"}

@app.put("/auth/update-profile")
def update_profile(
    req: dict,
    db: Session = Depends(database.get_db),
    current_user: str = Depends(auth_utils.get_current_user)
):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")

    new_username = req.get("new_username")
    new_email = req.get("new_email")
    email_otp = req.get("email_otp")
    old_password = req.get("old_password")
    new_password = req.get("new_password")

    if new_username and new_username != user.username:
        if db.query(models.User).filter(models.User.username == new_username).first():
            raise HTTPException(status_code=400, detail="此 ID 已被使用")
        user.username = new_username

    if new_email and email_otp:
        stored_otp = otp_storage.get(f"new_email:{new_email}")
        if not stored_otp or stored_otp != email_otp:
            raise HTTPException(status_code=400, detail="Email 驗證碼錯誤")
        user.email = new_email
        del otp_storage[f"new_email:{new_email}"]

    if old_password and new_password:
        if not auth_utils.verify_password(old_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="原密碼錯誤")
        user.hashed_password = auth_utils.get_password_hash(new_password)

    db.commit()
    db.refresh(user)
    new_token = auth_utils.create_access_token(data={"sub": user.username, "role": user.role})
    return {"message": "success", "access_token": new_token, "username": user.username}

# --- Admin routes ---

@app.get("/admin/users")
def get_all_users(db: Session = Depends(database.get_db)):
    perform_auto_cleanup(db)
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
        {"username": u.username, "email": u.email, "role": u.role, "is_online": u.is_online}
        for u in users
    ]

@app.put("/admin/users/{target_username}/role")
def update_user_role(target_username: str, data: dict, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == target_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到該用戶")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能更改管理員權限")
    new_role = data.get("role")
    user.role = new_role
    if new_role == "banned":
        user.is_online = 0
    db.commit()
    return {"message": "success"}

# --- WebSocket vision route ---

@app.websocket("/ws/vision/game_start")
async def vision_game_start(websocket: WebSocket):
    await websocket.accept()
    detector = GestureDetector()
    try:
        while True:
            data = await websocket.receive_json()
            landmarks = data.get("landmarks")
            if not landmarks:
                await websocket.send_json({"status": "WAITING", "hand_x": None, "hand_y": None})
                continue
            try:
                result = detector.process_data(landmarks, data.get("width"), data.get("height"))
                await websocket.send_json(result)
            except Exception as inner_e:
                pass  # log removed (non-ASCII)
                await websocket.send_json({"status": "ERROR_IN_LOGIC"})
                continue
            if result.get("done"):
                break
    except Exception as e:
        pass  # log removed (non-ASCII)

# --- Room routes ---

@app.post("/rooms/create")
async def create_room(room: RoomSchema):
    if room.code in active_rooms:
        raise HTTPException(status_code=400, detail="代碼已存在")
    room_dict = room.dict()
    room_dict['players'] = [room.hostId]
    room_dict['status'] = 'waiting'
    room_dict['is_started'] = False
    active_rooms[room.code] = room_dict
    return room_dict

@app.get("/rooms/public")
async def get_public_rooms():
    return [r for r in active_rooms.values()
            if r.get('type') in ['public', '公開'] and not r.get('is_started', False)]

@app.delete("/rooms/delete/{code}")
async def delete_room(code: str):
    if code in active_rooms:
        del active_rooms[code]
        pass  # log removed (non-ASCII)
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
            pass  # log removed (non-ASCII)
            if not room['players']:
                del active_rooms[code]
                pass  # log removed (non-ASCII)
            return {"status": "success", "count": len(room.get('players', []))}
    return {"status": "error", "message": "找不到房間或玩家"}

@app.post("/rooms/kick/{code}")
async def kick_player(code: str, username: str = Query(...)):
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="找不到房間")
    room = active_rooms[code]
    if 'players' not in room or username not in room['players']:
        raise HTTPException(status_code=404, detail="房間內找不到該玩家")
    room['players'].remove(username)
    pass  # log removed (non-ASCII)
    return {"status": "success", "message": f"已將 {username} 剔除"}

@app.get("/rooms/verify/{code}")
async def verify_room(code: str, username: Optional[str] = None):
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="房間不存在")
    room = active_rooms[code]
    return {
        "exists": True,
        "code": code,
        "name": room.get("name", "未命名房間"),
        "status": room.get("status", "waiting"),
        "is_started": room.get("is_started", False),
        "players": room.get("players", []),
        "hostId": room.get("hostId"),
        "mode": room.get("mode"),
        "difficulty": room.get("difficulty"),
        "winLaps": room.get("winLaps")
    }

@app.get("/rooms/status")
async def get_room_status(code: str):
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="找不到該房間")
    room = active_rooms[code]
    return {
        "code": code,
        "status": room.get("status", "waiting"),
        "players": room.get("players", []),
        "is_started": room.get("is_started", False),
        "hostId": room.get("hostId")
    }

@app.post("/rooms/start/{code}")
async def start_game(
    code: str,
    username: str,
    token: str = Depends(auth_utils.oauth2_scheme)
):
    code = code.upper()
    if code not in active_rooms:
        raise HTTPException(status_code=404, detail="找不到該房間")
    room = active_rooms[code]
    if room['hostId'] != username:
        raise HTTPException(status_code=403, detail="只有房主可以開始遊戲")
    room['status'] = 'gaming'
    room['is_started'] = True
    return room

# --- Socket.IO events ---

@sio.on('join_game_room')
async def handle_join_game_room(sid, data):
    room = data.get('room')
    user = data.get('user')
    if room:
        await sio.enter_room(sid, room)
        pass  # log removed (non-ASCII)

@sio.on('start_game_request')
async def handle_start_game(sid, data):
    room_code = data.get('room')
    pass  # log removed (non-ASCII)
    await sio.emit('start_game_command', {"status": "go"}, room=room_code)

@sio.on('submit_order_dice')
async def handle_order_dice(sid, data):
    room = data.get('room')
    user = data.get('user')
    points = data.get('points')
    if points is None or not room:
        pass  # log removed (non-ASCII)
        return
    if room not in room_dice_data:
        room_dice_data[room] = {}
    room_dice_data[room][user] = points
    pass  # log removed (non-ASCII)
    if len(room_dice_data[room]) >= 2:
        final_results = room_dice_data[room].copy()
        await sio.emit('dice_order_final', final_results, room=room)
        room_dice_data[room] = {}

@sio.on('reset_dice_order')
async def handle_reset_dice(sid, data):
    room = data.get('room')
    if room in room_dice_data:
        room_dice_data[room] = {}
        pass  # log removed (non-ASCII)

@sio.on('player_move_sync')
async def handle_player_move(sid, data):
    room = data.get('room')
    if room:
        await sio.emit('player_move_sync', data, room=room, skip_sid=sid)

@sio.on('next_turn')
async def handle_next_turn(sid, data):
    room = data.get('room')
    if room:
        await sio.emit('next_turn_trigger', {'next_player': 'opponent'}, room=room)

@sio.on('buy_land')
async def handle_buy_land(sid, data):
    room = data.get('room')
    user = data.get('user')
    tile_index = data.get('tileIndex')
    player_colors = {"Player1": "#4facfe", "Player2": "#ffde59"}
    color = player_colors.get(user, "#ffffff")
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

@app.get("/auth/verify")
def verify_token(username: str = Depends(auth_utils.get_current_user)):
    return {"username": username}

@app.get("/board-preview", response_class=HTMLResponse)
def board_preview_page():
    tmpl_path = _os.path.join(_BASE, "templates", "board_preview.html")
    with open(tmpl_path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# 根目錄靜態掛載須放在所有 API 路由之後，作為最後的兜底
# 讓 /login.html、/lobby.html 等相對路徑頁面可正常存取
app.mount("/", StaticFiles(directory="static", html=True), name="static_root")
