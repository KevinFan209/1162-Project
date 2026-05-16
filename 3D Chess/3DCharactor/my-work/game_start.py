import json
import numpy as np
import random
import time
import math

class GestureDetector:
    def __init__(self):
        # 狀態定義
        self.STATE_ROLLING = 0     
        self.STATE_PAUSING = 1     
        self.STATE_DETECTING = 2   
        self.current_state = self.STATE_ROLLING

        # 載入手勢標準檔 (這部分保留，用來比對數據)
        try:
            with open('norm_hand_standards.json', 'r') as f:
                self.standards = json.load(f)
        except:
            self.standards = {}

        self.PAUSE_TIME = 2.0
        self.is_rolling = False
        self.roll_start_time = 0
        self.current_dice_val = 1
        self.target_dice = "1"
        self.stable_counter = 0
        self.pause_start_time = 0

    # 🏆 新增：純數據處理方法
    def process_data(self, landmarks, fw, fh):
        curr_time = time.time()
        status_msg = ""
        done = False
        
        # 取得感應點
        cx = landmarks[9]['x'] * fw if landmarks else None
        cy = landmarks[9]['y'] * fh if landmarks else None

        # --- 狀態 0：滾動 ---
        if self.current_state == self.STATE_ROLLING:
            if self.is_rolling:
                status_msg = "ROLLING"
                if curr_time - self.roll_start_time > 1.5:
                    self.is_rolling = False
                    self.current_dice_val = random.randint(1, 6)
                    self.target_dice = str(self.current_dice_val)
                    self.current_state = self.STATE_PAUSING
                    self.pause_start_time = curr_time
            else:
                status_msg = "PUNCH_UP_TO_ROLL"
                if cx and cy:
                    dist = math.sqrt((cx - 320)**2 + (cy - 180)**2)
                    if dist < 130:
                        self.is_rolling = True
                        self.roll_start_time = curr_time

        # --- 狀態 1：停頓 (解決定格關鍵) ---
        elif self.current_state == self.STATE_PAUSING:
            status_msg = f"GOT_{self.current_dice_val}"
            # 🏆 這裡絕對不能用 time.sleep()，必須用時間差判斷
            if curr_time - self.pause_start_time > 2.0:
                self.current_state = self.STATE_DETECTING
                self.stable_counter = 0

        # --- 狀態 2：辨識 ---
        elif self.current_state == self.STATE_DETECTING:
            status_msg = f"SHOW_{self.target_dice}"
            if landmarks:
                # 🏆 確保這裡呼叫的是你定義好的數據版方法
                actual_fingers = self.get_finger_count_from_data(landmarks, fw, fh)
                curr_norm = self.get_norm_from_data(landmarks)
                
                if curr_norm is not None and self.target_dice in self.standards:
                    stan_coords = np.array(self.standards[self.target_dice])
                    error = np.mean(np.linalg.norm(curr_norm - stan_coords, axis=1))
                    threshold = 0.25 if self.target_dice == "1" else 0.18
                    
                    if actual_fingers == int(self.target_dice) and error < threshold:
                        self.stable_counter += 1
                        status_msg = f"MATCHING_{self.stable_counter}"
                        if self.stable_counter >= 10:
                            done = True
                    else:
                        self.stable_counter = 0

        return {
            "status": status_msg,
            "dice_val": self.current_dice_val,
            "done": done,
            "hand_x": cx,
            "hand_y": cy
        }

    # --- 輔助運算函式 (將原本 OpenCV 相關的改成純數據處理) ---
    def get_finger_count_from_data(self, landmarks, w, h):
        p = [(l['x'] * w, l['y'] * h) for l in landmarks]
        def angle(v1, v2):
            dot = v1[0]*v2[0] + v1[1]*v2[1]
            norm = (v1[0]**2+v1[1]**2)**0.5 * (v2[0]**2+v2[1]**2)**0.5
            return math.degrees(math.acos(max(-1, min(1, dot/norm))))
        
        angles = [
            angle((p[0][0]-p[2][0], p[0][1]-p[2][1]), (p[3][0]-p[4][0], p[3][1]-p[4][1])),
            angle((p[0][0]-p[6][0], p[0][1]-p[6][1]), (p[7][0]-p[8][0], p[7][1]-p[8][1])),
            angle((p[0][0]-p[10][0], p[0][1]-p[10][1]), (p[11][0]-p[12][0], p[11][1]-p[12][1])),
            angle((p[0][0]-p[14][0], p[0][1]-p[14][1]), (p[15][0]-p[16][0], p[15][1]-p[16][1])),
            angle((p[0][0]-p[18][0], p[0][1]-p[18][1]), (p[19][0]-p[20][0], p[19][1]-p[20][1]))
        ]
        f = [a < 50 for a in angles]
        return sum(f)

    def get_norm_from_data(self, landmarks):
        coords = np.array([[l['x'], l['y']] for l in landmarks])
        center = coords[9]
        coords -= center
        span = np.linalg.norm(coords[0] - coords[9])
        return coords / span if span > 1e-6 else None