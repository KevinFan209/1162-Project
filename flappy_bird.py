import cv2
import mediapipe as mp
import numpy as np
import random
import time
import math
from PIL import Image, ImageDraw, ImageFont

# --- 初始化 MediaPipe ---
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.8, min_tracking_confidence=0.8)
mp_drawing = mp.solutions.drawing_utils

# --- 參數設定 ---
SCREEN_W, SCREEN_H = 1024, 576
BIRD_X = 150        
PIPE_WIDTH = 80
PIPE_GAP = 190      
PIPE_SPEED = 7      
COIN_RATE = 10      

# --- 物理常數 ---
GRAVITY = 0.42       
JUMP_BOOST = -7.0    
MAX_VELOCITY = 10   

# 狀態定義
STATE_WAITING, STATE_COUNTDOWN, STATE_PLAYING, STATE_GAMEOVER = 0, 1, 2, 3
current_game_state = STATE_WAITING

# 變數初始化
bird_y = SCREEN_H // 2
bird_velocity = 0
pipes = [] 
score = 0
total_coins = 0
countdown_start_time = 0
last_lw_y = None
last_rw_y = None
has_moved_down = False  

# 【修正：小鳥圖片路徑】
BIRD_IMG_PATH = "bird.png"

# --- 【核心修正：中文顯示函式】 ---
def draw_text_chinese(img, text, position, font_size, color):
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    try:
        font = ImageFont.truetype("msjh.ttc", font_size)
    except:
        font = ImageFont.load_default()
    draw.text(position, text, font=font, fill=(color[2], color[1], color[0]))
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def create_pipe():
    gap_y = random.randint(100, SCREEN_H - 100 - PIPE_GAP)
    return [SCREEN_W, gap_y]

# --- 【修正：只載入小鳥資產】 ---
def load_game_assets():
    bird_img = cv2.imread(BIRD_IMG_PATH, cv2.IMREAD_UNCHANGED)
    if bird_img is None:
        # 沒圖就用黃色圓球替代
        print(f"找不到 {BIRD_IMG_PATH}，將使用黃球代替。")
        bird_img = np.zeros((60, 60, 4), dtype=np.uint8)
        cv2.circle(bird_img, (30, 30), 30, (0, 255, 255, 255), -1)
    else:
        # 縮放到適合大小
        bird_img = cv2.resize(bird_img, (60, 60))
    return bird_img

# --- 【修正：PNG 透明疊加函式】 ---
def overlay_transparent(bg, fg, x, y):
    """將去背的 PNG 圖片疊加到攝影機畫面上"""
    h, w = fg.shape[:2]
    y1, y2 = max(0, y), min(bg.shape[0], y + h)
    x1, x2 = max(0, x), min(bg.shape[1], x + w)
    
    # 裁切圖片以適應邊界
    fg_cropped = fg[y1-y:y2-y, x1-x:x2-x]
    
    # 分離顏色通道和 Alpha 通道
    if fg_cropped.shape[2] == 4: # 如果有透明通道
        fg_rgb = fg_cropped[:, :, :3]
        alpha = fg_cropped[:, :, 3] / 255.0
        
        # 執行疊加
        for c in range(3):
            bg[y1:y2, x1:x2, c] = (alpha * fg_rgb[:, :, c] + (1.0 - alpha) * bg[y1:y2, x1:x2, c]).astype(np.uint8)
    else:
        # 無透明通道，直接覆蓋
        bg[y1:y2, x1:x2] = fg_cropped
    return bg

# --- 【修正：恢復原本程式畫綠色水管的方式】 ---
def draw_styled_pipes(bg, pipes_list):
    for p in pipes_list:
        px, gap_y = p
        # 畫上水管 (深綠色矩形)
        cv2.rectangle(bg, (px, 0), (px + PIPE_WIDTH, gap_y), (0, 180, 0), -1)
        # 畫上水管口 (深綠色框)
        cv2.rectangle(bg, (px, gap_y - 30), (px + PIPE_WIDTH, gap_y), (0, 100, 0), 4)
        
        # 畫下水管 (亮綠色矩形)
        cv2.rectangle(bg, (px, gap_y + PIPE_GAP), (px + PIPE_WIDTH, SCREEN_H), (0, 220, 0), -1)
        # 畫下水管口 (深綠色框)
        cv2.rectangle(bg, (px, gap_y + PIPE_GAP), (px + PIPE_WIDTH, gap_y + PIPE_GAP + 30), (0, 100, 0), 4)
    return bg

# --- 初始化遊戲 ---
pipes.append(create_pipe())
cap = cv2.VideoCapture(0)
bird_asset = load_game_assets()

print("=== Flappy Wings (色塊水管+圖片小鳥) 啟動 ===")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (SCREEN_W, SCREEN_H))
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(img_rgb)
    game_layer = frame.copy()
    jump_triggered = False

    if results.pose_landmarks:
        lm = results.pose_landmarks.landmark
        curr_lw_y, curr_rw_y = lm[15].y, lm[16].y
        if 0.1 < curr_lw_y < 0.9 and 0.1 < curr_rw_y < 0.9:
            if last_lw_y is not None:
                if (last_lw_y - curr_lw_y > 0.02) or (last_rw_y - curr_rw_y > 0.02):
                    jump_triggered = True
                    if current_game_state == STATE_WAITING and has_moved_down:
                        current_game_state = STATE_COUNTDOWN
                        countdown_start_time = time.time()
                if (last_lw_y - curr_lw_y < -0.015) or (last_rw_y - curr_rw_y < -0.015):
                    has_moved_down = True
            last_lw_y, last_rw_y = curr_lw_y, curr_rw_y
        mp_drawing.draw_landmarks(game_layer, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
    else:
        has_moved_down = False
        last_lw_y = None

    # --- 遊戲邏輯與繪製 ---
    if current_game_state == STATE_WAITING:
        bird_y = int(SCREEN_H // 2 + np.sin(time.time() * 4) * 10)
        msg = "揮動翅膀，開始遊戲！" if has_moved_down else "請向下擺手，再向上揮動開始！"
        game_layer = draw_text_chinese(game_layer, msg, (SCREEN_W//2-250, SCREEN_H//2-20), 40, (0, 255, 255))

    elif current_game_state == STATE_COUNTDOWN:
        bird_y = SCREEN_H // 2
        countdown_num = 3 - int(time.time() - countdown_start_time)
        if countdown_num > 0:
            game_layer = draw_text_chinese(game_layer, str(countdown_num), (SCREEN_W//2-20, SCREEN_H//2-50), 100, (0, 255, 0))
        else:
            current_game_state = STATE_PLAYING

    elif current_game_state == STATE_PLAYING:
        if jump_triggered: bird_velocity = JUMP_BOOST 
        bird_velocity += GRAVITY
        if bird_velocity > MAX_VELOCITY: bird_velocity = MAX_VELOCITY
        bird_y += int(bird_velocity)
        if bird_y > SCREEN_H - 25 or bird_y < 0: current_game_state = STATE_GAMEOVER
        for p in pipes: p[0] -= PIPE_SPEED
        if pipes[-1][0] < SCREEN_W - 400: pipes.append(create_pipe())
        if pipes[0][0] < -PIPE_WIDTH:
            pipes.pop(0)
            score += 1
            total_coins += COIN_RATE
        for p in pipes:
            px, gap_y = p
            if BIRD_X + 22 > px and BIRD_X - 22 < px + PIPE_WIDTH:
                if bird_y - 22 < gap_y or bird_y + 22 > gap_y + PIPE_GAP:
                    current_game_state = STATE_GAMEOVER

    elif current_game_state == STATE_GAMEOVER:
        game_layer = draw_text_chinese(game_layer, "遊戲結束", (SCREEN_W//2-80, SCREEN_H//2-50), 60, (0, 0, 255))
        game_layer = draw_text_chinese(game_layer, f"獲得金幣: {total_coins}", (SCREEN_W//2-80, SCREEN_H//2+30), 30, (255, 255, 255))
        game_layer = draw_text_chinese(game_layer, "按 'R' 重新開始", (SCREEN_W//2-80, SCREEN_H//2+80), 20, (200, 200, 200))

    # --- 【修正：分別繪製色塊水管與圖片小鳥】 ---
    # 1. 畫色塊水管 (不會卡)
    game_layer = draw_styled_pipes(game_layer, pipes)
    # 2. 畫圖片小鳥 (使用透明疊加)
    game_layer = overlay_transparent(game_layer, bird_asset, BIRD_X - 30, bird_y - 30)
    
    # 頂部狀態欄
    cv2.rectangle(game_layer, (0, 0), (280, 110), (40, 40, 40), -1)
    game_layer = draw_text_chinese(game_layer, f"得分: {score}", (20, 15), 35, (255, 255, 255))
    game_layer = draw_text_chinese(game_layer, f"金幣: {total_coins}", (20, 60), 35, (0, 215, 255))

    cv2.imshow('Flappy Wings - Stability Mode', game_layer)
    key = cv2.waitKey(1)
    if key == ord('q'): break
    if key == ord('r') and current_game_state == STATE_GAMEOVER:
        score, total_coins, bird_y, bird_velocity = 0, 0, SCREEN_H // 2, 0
        pipes = [create_pipe()]
        current_game_state = STATE_WAITING 
        last_lw_y, has_moved_down = None, False

cap.release()
cv2.destroyAllWindows()