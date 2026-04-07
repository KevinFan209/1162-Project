import cv2
import mediapipe as mp
import json
import numpy as np
import os

# ==========================================
# 【自定義調整區】請修改以下數值來移動輪廓
# ==========================================
POS_X = 120    # 往右移動的像素 (0 是最左邊)
POS_Y = 100    # 往下移動的像素 (0 是最上面)
SCALE = 0.5    # 縮放比例 (0.5 代表縮小一半，1.0 是原圖大小)
# ==========================================

# 初始化 MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils
cap = cv2.VideoCapture(0)

# 讀取現有的標準檔
if os.path.exists('norm_hand_standards.json'):
    with open('norm_hand_standards.json', 'r') as f:
        standards = json.load(f)
else:
    standards = {}

current_target = "1" 
rec_counter = 0
temp_records = []

def get_normalized_shape(landmarks):
    coords = np.array([[lm.x, lm.y] for lm in landmarks])
    center = coords[9] 
    coords = coords - center
    palm_span = np.linalg.norm(coords[0] - coords[9])
    return coords / palm_span if palm_span > 1e-6 else None

def overlay_png_at_pos(bg, target_num, x, y, scale):
    """在指定位置疊加縮放後的輪廓圖"""
    path = f'outlines/{target_num}.png'
    fg = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if fg is None: return bg
    
    # 縮放輪廓圖
    h, w = fg.shape[:2]
    new_w, new_h = int(w * scale), int(h * scale)
    fg_resized = cv2.resize(fg, (new_w, new_h))
    
    # 取得背景尺寸
    bh, bw = bg.shape[:2]
    
    # 計算疊加邊界，防止超出螢幕
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + new_w, bw), min(y + new_h, bh)
    
    # 裁切對應的區域
    fg_w, fg_h = x2 - x1, y2 - y1
    if fg_w <= 0 or fg_h <= 0: return bg
    
    fg_crop = fg_resized[0:fg_h, 0:fg_w]
    b, g, r, a = cv2.split(fg_crop)
    mask = a / 255.0
    
    # 合併背景與前景
    for c in range(3):
        bg[y1:y2, x1:x2, c] = (bg[y1:y2, x1:x2, c] * (1 - mask) + 
                               fg_crop[:, :, c] * mask).astype(np.uint8)
    return bg

print("=== 全手勢錄製模式 (位置可調版) ===")
print(f"目前設定：位置({POS_X}, {POS_Y}), 縮放 {SCALE}")
print("按鍵說明：1-6 切換, 長按 'S' 錄製, 'q' 儲存退出")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]

    # 疊加目標輪廓 (使用自定義位置與比例)
    frame = overlay_png_at_pos(frame, current_target, POS_X, POS_Y, SCALE)

    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)

    key = cv2.waitKey(1) & 0xFF
    
    # 切換目標
    if ord('1') <= key <= ord('6'):
        current_target = chr(key)
        temp_records = []
        rec_counter = 0
        print(f"切換至：{current_target}")

    if results.multi_hand_landmarks:
        lm = results.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)
        
        # 按住 S 錄製 (確保手在輪廓內時操作)
        if key == ord('s') and rec_counter < 100:
            norm_coords = get_normalized_shape(lm.landmark)
            if norm_coords is not None:
                temp_records.append(norm_coords.tolist())
                rec_counter += 1

    # 錄滿 100 筆自動存入 standards 緩存
    if rec_counter >= 100 and len(temp_records) > 0:
        standards[current_target] = np.mean(np.array(temp_records), axis=0).tolist()
        print(f"--- 手勢 {current_target} 錄製完成！ ---")
        rec_counter = 0 
        temp_records = []

    # UI 顯示
    cv2.rectangle(frame, (0, 0), (w, 80), (30, 30, 30), -1)
    cv2.putText(frame, f"Target: {current_target} | Progress: {rec_counter}/100", (20, 30), 0, 0.7, (255, 255, 0), 2)
    cv2.putText(frame, "Hold 'S' to record | Press 'q' to save all", (20, 60), 0, 0.6, (255, 255, 255), 1)

    cv2.imshow("Multi-Gesture Recorder", frame)
    if key == ord('q'): break

# 儲存到 JSON
with open('norm_hand_standards.json', 'w') as f:
    json.dump(standards, f)

print(f"所有手勢已成功儲存至 norm_hand_standards.json")
cap.release()
cv2.destroyAllWindows()