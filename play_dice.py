import cv2
import mediapipe as mp
import numpy as np
import random
import time
import os

# ==========================================
# 【參數設定】
# ==========================================
DICE_POS = (320, 180)  
DICE_SIZE = 100        
FACE_PATH = "dice_faces" 
# ==========================================

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
cap = cv2.VideoCapture(0)

faces = []
for i in range(1, 7):
    img = cv2.imread(f"{FACE_PATH}/{i}.png", cv2.IMREAD_UNCHANGED)
    if img is None: 
        img = np.full((DICE_SIZE, DICE_SIZE, 3), 255, np.uint8)
        cv2.putText(img, str(i), (30, 70), 0, 2, (0,0,0), 3)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    faces.append(cv2.resize(img, (DICE_SIZE, DICE_SIZE)))

is_rolling = False
roll_start_time = 0
roll_duration = 1.5
current_dice_val = 1
last_hand_y = 0

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
    pts_dst = np.array([
        rotate_point([-half, -half, 0], ax, ay),
        rotate_point([half, -half, 0], ax, ay),
        rotate_point([half, half, 0], ax, ay),
        rotate_point([-half, half, 0], ax, ay)
    ], dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(pts_src, pts_dst)
    warped = cv2.warpPerspective(face_img, matrix, (bg.shape[1], bg.shape[0]), 
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    
    if warped.shape[2] == 4:
        rgb_w = warped[:, :, :3]
        mask = warped[:, :, 3] / 255.0
        for c in range(3):
            bg[:, :, c] = (bg[:, :, c] * (1 - mask) + rgb_w[:, :, c] * mask).astype(np.uint8)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    fh, fw, _ = frame.shape
    curr_time = time.time()

    if is_rolling:
        elapsed = curr_time - roll_start_time
        angle = elapsed * 720 
        draw_3d_face(frame, faces[random.randint(0,5)], angle, angle*0.5, 0)
        if elapsed > roll_duration:
            is_rolling = False
            current_dice_val = random.randint(1, 6)
            # 修改處：在旋轉結束後才印出最終點數
            print(f"擊發成功！點數：{current_dice_val}")
    else:
        draw_3d_face(frame, faces[current_dice_val-1], 0, 0, 0)

    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)
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

    # 修改處：移除了 cv2.circle 畫出的感應圓圈

    cv2.imshow("Optimized 3D Dice", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()