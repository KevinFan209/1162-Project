import cv2
import mediapipe as mp
import json
import numpy as np
import math
from collections import deque, Counter

# ==========================================
# 【同步調整區】
# ==========================================
POS_X, POS_Y, SCALE = 120, 100, 0.5 
# ==========================================

# --- 向量角度計算法 ---
def vector_2d_angle(v1, v2):
    v1_x, v1_y = v1
    v2_x, v2_y = v2
    try:
        # 計算向量夾角
        dot_product = v1_x * v2_x + v1_y * v2_y
        norm_product = ((v1_x**2 + v1_y**2)**0.5) * ((v2_x**2 + v2_y**2)**0.5)
        angle = math.degrees(math.acos(dot_product / norm_product))
    except:
        angle = 180
    return angle

def get_hand_angles(hand_points):
    """計算五根手指的彎曲角度"""
    angles = []
    # 大拇指 (點0,2 與 點3,4 向量)
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[2][0], hand_points[0][1]-hand_points[2][1]),
                                  (hand_points[3][0]-hand_points[4][0], hand_points[3][1]-hand_points[4][1])))
    # 食指 (點0,6 與 點7,8 向量)
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[6][0], hand_points[0][1]-hand_points[6][1]),
                                  (hand_points[7][0]-hand_points[8][0], hand_points[7][1]-hand_points[8][1])))
    # 中指
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[10][0], hand_points[0][1]-hand_points[10][1]),
                                  (hand_points[11][0]-hand_points[12][0], hand_points[11][1]-hand_points[12][1])))
    # 無名指
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[14][0], hand_points[0][1]-hand_points[14][1]),
                                  (hand_points[15][0]-hand_points[16][0], hand_points[15][1]-hand_points[16][1])))
    # 小指
    angles.append(vector_2d_angle((hand_points[0][0]-hand_points[18][0], hand_points[0][1]-hand_points[18][1]),
                                  (hand_points[19][0]-hand_points[20][0], hand_points[19][1]-hand_points[20][1])))
    return angles

def get_real_finger_count(lm_list, w, h):
    """使用向量角度法判定 1-6 手勢"""
    # 先將座標轉換為像素座標
    hand_points = [(i.x * w, i.y * h) for i in lm_list]
    angles = get_hand_angles(hand_points)
    
    # 小於 50 度表示手指伸直 (True)
    f = [a < 50 for a in angles]

    # --- 根據角度布林值判定手勢 ---
    # 判定 6 (大拇指和小指伸直，其餘彎曲)
    if f[0] and not f[1] and not f[2] and not f[3] and f[4]:
        return 6
    # 判定 1-5 (直接加總伸直的手指數量)
    # 注意：這裡採用簡單加總，若要更嚴格可比照 hand_pos 的 elif 邏輯
    return sum(f)

# --- 原有座標與繪圖函式 ---
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

# --- 主程式啟動 ---
with open('norm_hand_standards.json', 'r') as f:
    standards = json.load(f)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.8)
cap = cv2.VideoCapture(0)

target_dice = "1" 
stable_counter = 0
finger_history = deque(maxlen=8)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    fh, fw = frame.shape[:2]
    
    # 繪製輪廓圖
    frame = overlay_png_at_pos(frame, target_dice, POS_X, POS_Y, SCALE)
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)

    display_msg = f"Waiting for {target_dice}..."
    msg_color = (255, 255, 255)

    if results.multi_hand_landmarks:
        lm_list = results.multi_hand_landmarks[0].landmark
        
        # 1. 使用「向量角度法」計算指尖數量
        current_val = get_real_finger_count(lm_list, fw, fh)
        finger_history.append(current_val)
        
        # 2. 取多數決
        most_common = Counter(finger_history).most_common(1)
        actual_fingers = most_common[0][0] if most_common else 0
        
        # 3. 座標誤差比對
        curr_norm = get_normalized_shape(lm_list)
        if curr_norm is not None and target_dice in standards:
            stan_coords = np.array(standards[target_dice])
            error = np.mean(np.linalg.norm(curr_norm - stan_coords, axis=1))

            is_finger_correct = (actual_fingers == int(target_dice))
            threshold = 0.22 if target_dice == "6" else 0.15
            is_pos_correct = (error < threshold) 

            if is_finger_correct and is_pos_correct:
                stable_counter += 1
                display_msg = f"MATCH! ({stable_counter}/15)"
                msg_color = (0, 255, 0)
                if stable_counter >= 15:
                    display_msg = "SUCCESS!"
            else:
                stable_counter = 0
                if not is_finger_correct:
                    display_msg = f"Finger Wrong! Need {target_dice}, got {actual_fingers}"
                else:
                    display_msg = "Please align to the outline!"
                msg_color = (0, 0, 255)

    # UI 顯示
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 65), (30, 30, 30), -1)
    cv2.putText(frame, display_msg, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, msg_color, 2)
    cv2.imshow("Monopoly AI - Angle Optimized", frame)
    
    key = cv2.waitKey(1) & 0xFF
    if ord('1') <= key <= ord('6'): 
        target_dice = chr(key)
        stable_counter = 0
        finger_history.clear()
    if key == ord('q'): break

cap.release()
cv2.destroyAllWindows()