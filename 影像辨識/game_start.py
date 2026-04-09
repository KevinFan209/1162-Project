import cv2
import mediapipe as mp
import json
import numpy as np
import random
import time
import os
import math
from collections import deque, Counter

# ==========================================
# 【參數設定】
# ==========================================
DICE_POS = (320, 180)  # 骰子中心位置
DICE_SIZE = 100        # 單面大小
FACE_PATH = "dice_faces" # 1-6.png 資料夾
POS_X, POS_Y, SCALE = 120, 100, 0.5 # 手勢輪廓圖位置
PAUSE_TIME = 2.0  # 骰完停頓時間 (秒)
# ==========================================

# 隨機化種子：確保每次開啟程式的第一球都是隨機的
random.seed(time.time())

# 狀態定義
STATE_ROLLING = 0     
STATE_PAUSING = 1     
STATE_DETECTING = 2   
current_state = STATE_ROLLING

# 初始化 MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
cap = cv2.VideoCapture(0)

# 載入手勢標準檔 (確認檔案路徑正確)
try:
    with open('norm_hand_standards.json', 'r') as f:
        standards = json.load(f)
except:
    print("找不到 norm_hand_standards.json，請檢查檔案！")
    standards = {}

# 載入骰子面圖片 (支援去背 PNG)
faces = []
for i in range(1, 7):
    img = cv2.imread(f"{FACE_PATH}/{i}.png", cv2.IMREAD_UNCHANGED)
    if img is None:
        img = np.full((DICE_SIZE, DICE_SIZE, 3), 255, np.uint8)
        cv2.putText(img, str(i), (30, 70), 0, 2, (0,0,0), 3)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    faces.append(cv2.resize(img, (DICE_SIZE, DICE_SIZE)))

# 變數初始化
is_rolling = False
roll_start_time = 0
roll_duration = 1.5
current_dice_val = 1
last_hand_y = 0
target_dice = "1"
stable_counter = 0
finger_history = deque(maxlen=8)
pause_start_time = 0

# --- 核心功能函式 ---

def vector_2d_angle(v1, v2):
    """計算兩個向量之間的夾角 (Oxxo 邏輯)"""
    v1_x, v1_y = v1
    v2_x, v2_y = v2
    try:
        dot_product = v1_x * v2_x + v1_y * v2_y
        norm_product = ((v1_x**2 + v1_y**2)**0.5) * ((v2_x**2 + v2_y**2)**0.5)
        angle = math.degrees(math.acos(dot_product / norm_product))
    except:
        angle = 180
    return angle

def get_real_finger_count(lm_list, w, h):
    """使用向量角度法判定手指伸直數量"""
    hand_points = [(i.x * w, i.y * h) for i in lm_list]
    angles = []
    # 大拇指、食指、中指、無名指、小指的角度向量對
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[2][0], hand_points[0][1]-hand_points[2][1]),
                                  (hand_points[3][0]-hand_points[4][0], hand_points[3][1]-hand_points[4][1])))
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[6][0], hand_points[0][1]-hand_points[6][1]),
                                  (hand_points[7][0]-hand_points[8][0], hand_points[7][1]-hand_points[8][1])))
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[10][0], hand_points[0][1]-hand_points[10][1]),
                                  (hand_points[11][0]-hand_points[12][0], hand_points[11][1]-hand_points[12][1])))
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[14][0], hand_points[0][1]-hand_points[14][1]),
                                  (hand_points[15][0]-hand_points[16][0], hand_points[15][1]-hand_points[16][1])))
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[18][0], hand_points[0][1]-hand_points[18][1]),
                                  (hand_points[19][0]-hand_points[20][0], hand_points[19][1]-hand_points[20][1])))
    
    f = [a < 50 for a in angles] # 角度小於 50 度視為伸直
    if f[0] and not f[1] and not f[2] and not f[3] and f[4]: return 6 # 手勢 6 特殊判定
    return sum(f)

def get_normalized_shape(landmarks):
    coords = np.array([[l.x, l.y] for l in landmarks])
    center = coords[9]
    coords = coords - center
    palm_span = np.linalg.norm(coords[0] - coords[9])
    return coords / palm_span if palm_span > 1e-6 else None

def overlay_png_at_pos(bg, target_num, x, y, scale):
    path = f'outlines/{target_num}.png'
    fg = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if fg is None: return bg
    h, w = fg.shape[:2]
    new_w, new_h = int(w * scale), int(h * scale)
    fg_resized = cv2.resize(fg, (new_w, new_h))
    bh, bw = bg.shape[:2]
    x1, y1, x2, y2 = max(x,0), max(y,0), min(x+new_w, bw), min(y+new_h, bh)
    fg_crop = fg_resized[0:y2-y1, 0:x2-x1]
    b, g, r, a = cv2.split(fg_crop)
    mask = a / 255.0
    for c in range(3):
        bg[y1:y2, x1:x2, c] = (bg[y1:y2, x1:x2, c]*(1-mask) + fg_crop[:,:,c]*mask).astype(np.uint8)
    return bg

def draw_3d_face(bg, face_img, angle_x, angle_y, offset_z):
    h, w = face_img.shape[:2]
    pts_src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    ax, ay = np.deg2rad(angle_x), np.deg2rad(angle_y)
    def rotate_point(pt, ax, ay):
        x, y, z = pt
        y1 = y * np.cos(ax) - z * np.sin(ax)
        z1 = y * np.sin(ax) + z * np.cos(ax)
        x2 = x * np.cos(ay) + z1 * np.sin(ay)
        z2 = -x * np.sin(ay) + z1 * np.cos(ay)
        perspective = 500 / (500 + z2 + offset_z)
        return [DICE_POS[0] + x2 * perspective, DICE_POS[1] + y1 * perspective]
    half = DICE_SIZE / 2
    pts_dst = np.array([rotate_point([-half, -half, 0], ax, ay),
                        rotate_point([half, -half, 0], ax, ay),
                        rotate_point([half, half, 0], ax, ay),
                        rotate_point([-half, half, 0], ax, ay)], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(pts_src, pts_dst)
    warped = cv2.warpPerspective(face_img, matrix, (bg.shape[1], bg.shape[0]),
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    if warped.shape[2] == 4:
        rgb_w = warped[:, :, :3]
        mask = warped[:, :, 3] / 255.0
        for c in range(3):
            bg[:, :, c] = (bg[:, :, c] * (1 - mask) + rgb_w[:, :, c] * mask).astype(np.uint8)

# --- 主迴圈 ---

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    fh, fw, _ = frame.shape
    curr_time = time.time()

    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)
    
    display_msg = ""
    msg_color = (255, 255, 255)

    if current_state == STATE_ROLLING:
        # 擲骰子階段
        if is_rolling:
            elapsed = curr_time - roll_start_time
            angle = elapsed * 720
            # 旋轉期間隨機顯示面，增加隨機感
            draw_3d_face(frame, faces[random.randint(0, 5)], angle, angle * 0.5, 0)
            
            if elapsed > roll_duration:
                is_rolling = False
                current_dice_val = random.randint(1, 6) # 最終隨機結果
                target_dice = str(current_dice_val)
                current_state = STATE_PAUSING
                pause_start_time = curr_time
        else:
            draw_3d_face(frame, faces[current_dice_val-1], 0, 0, 0)
            display_msg = "PUNCH UP TO ROLL!"
        
        # 揮拳偵測邏輯
        if results.multi_hand_landmarks:
            lm = results.multi_hand_landmarks[0].landmark
            cx, cy = int(lm[9].x * fw), int(lm[9].y * fh)
            cv2.circle(frame, (cx, cy), 10, (0, 255, 0), -1)
            dist = np.sqrt((cx - DICE_POS[0])**2 + (cy - DICE_POS[1])**2)
            punch_speed = last_hand_y - cy
            if dist < 130 and punch_speed > 10 and not is_rolling:
                is_rolling = True
                roll_start_time = curr_time
            last_hand_y = cy

    elif current_state == STATE_PAUSING:
        # 停頓看點數階段
        draw_3d_face(frame, faces[current_dice_val-1], 0, 0, 0)
        display_msg = f"GOT {current_dice_val}! GET READY..."
        if curr_time - pause_start_time > PAUSE_TIME:
            current_state = STATE_DETECTING
            stable_counter = 0
            finger_history.clear()

    elif current_state == STATE_DETECTING:
        # 手勢辨識階段
        frame = overlay_png_at_pos(frame, target_dice, POS_X, POS_Y, SCALE)
        display_msg = f"PLEASE SHOW GESTURE: {target_dice}"

        if results.multi_hand_landmarks:
            lm_list = results.multi_hand_landmarks[0].landmark
            # 1. 向量角度判定手指數量
            current_val = get_real_finger_count(lm_list, fw, fh)
            finger_history.append(current_val)
            most_common = Counter(finger_history).most_common(1)
            actual_fingers = most_common[0][0] if most_common else 0
            
            # 2. 座標正規化誤差比對
            curr_norm = get_normalized_shape(lm_list)
            if curr_norm is not None and target_dice in standards:
                stan_coords = np.array(standards[target_dice])
                error = np.mean(np.linalg.norm(curr_norm - stan_coords, axis=1))
                is_finger_correct = (actual_fingers == int(target_dice))
                
                # 門檻值優化 (1號與6號)
                threshold = 0.25 if target_dice == "1" else (0.22 if target_dice == "6" else 0.15)
                is_pos_correct = (error < threshold)

                if is_finger_correct and is_pos_correct:
                    stable_counter += 1
                    display_msg = f"MATCH! ({stable_counter}/15)"
                    msg_color = (0, 255, 0)
                    if stable_counter >= 15:
                        print(f"辨識成功！骰子點數為：{target_dice}")
                        break # 成功即退出程式
                else:
                    stable_counter = 0
                    if not is_finger_correct:
                        display_msg = f"Finger Wrong! Need {target_dice}, got {actual_fingers}"
                        msg_color = (0, 0, 255)
                    else:
                        display_msg = "Align to outline!"

    # 繪製頂部 UI
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 65), (30, 30, 30), -1)
    cv2.putText(frame, display_msg, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, msg_color, 2)
    cv2.imshow("Monopoly AI Final System", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()