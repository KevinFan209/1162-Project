import json
import numpy as np
import math
import random

class GestureDetector:
    def __init__(self):
        try:
            with open('norm_hand_standards.json', 'r') as f:
                self.standards = json.load(f)
        except:
            self.standards = {}
        self.stable_counter = 0
        self.prev_val = 0

    def process_data(self, landmarks, fw, fh, target=None):
        if isinstance(landmarks, dict):
            landmarks = [landmarks[str(i)] for i in range(len(landmarks))]

        cx = landmarks[9]['x'] * fw if landmarks else None
        cy = landmarks[9]['y'] * fh if landmarks else None
        status_msg = "WAITING"
        done = False
        detected_val = 0

        if landmarks:
            actual_fingers = self.get_finger_count_from_data(landmarks, fw, fh)
            
            # 🏆 決策階段 (LIKE/DISLIKE/ROCK)
            # 🚀 核心修正：如果偵測到 7, 8, 9（代表要發動道具或計算加成步數），不可被 LIKE/DISLIKE 的規則阻斷吞掉
            if (target in ["LIKE", "DISLIKE"] or actual_fingers == "ROCK") and actual_fingers not in [7, 8, 9]:
                if actual_fingers in ["LIKE", "DISLIKE", "ROCK"]:
                    if self.prev_val == actual_fingers:
                        self.stable_counter += 1
                    else:
                        self.stable_counter = 1
                        self.prev_val = actual_fingers
                    
                    # 穩定度門檻：ROCK 偵測 1 次即可，LIKE/DISLIKE 需 8 次
                    threshold = 1 if actual_fingers == "ROCK" else 8
                    if self.stable_counter >= threshold: 
                        res = {"status": "SUCCESS", "dice_val": actual_fingers, "done": True, "hand_x": cx, "hand_y": cy}
                        self.stable_counter = 0 
                        return res
                else:
                    self.stable_counter = 0
                return {"status": "WAITING", "dice_val": actual_fingers, "done": False}

            # 🎲 擲骰子與道具發動/結算階段 (數字 1-9)
            curr_norm = self.get_norm_from_data(landmarks)
            finger_key = str(actual_fingers)
            
            # 🚀 擴充：將辨識名單延伸到 7, 8, 9 
            if finger_key in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                
                # 🚀 智慧避錯：如果標準 JSON 中有記錄該數字就比對誤差值，若無（如剛加的7,8,9）則直接以骨架角度為準放行
                if finger_key in self.standards:
                    stan_coords = np.array(self.standards[finger_key])
                    error = np.mean(np.linalg.norm(curr_norm - stan_coords, axis=1))
                    is_valid = (error < 0.45)
                else:
                    is_valid = True 

                if is_valid: 
                    if self.prev_val == actual_fingers:
                        self.stable_counter += 1
                    else:
                        self.stable_counter = 1
                        self.prev_val = actual_fingers
                    
                    if self.stable_counter >= 8:
                        done = True
                        status_msg = "SUCCESS"
                        detected_val = actual_fingers
                        self.stable_counter = 0
                else:
                    self.stable_counter = 0
            else:
                self.stable_counter = 0

        return {"status": status_msg, "dice_val": detected_val if done else actual_fingers, "done": done, "hand_x": cx, "hand_y": cy}

    def vector_2d_angle(self, v1, v2):
        try:
            return math.degrees(math.acos((v1[0]*v2[0]+v1[1]*v2[1])/(((v1[0]**2+v1[1]**2)**0.5)*((v2[0]**2+v2[1]**2)**0.5))))
        except:
            return 180

    def get_finger_count_from_data(self, landmarks, w, h):
        hand_ = [(l['x'] * w, l['y'] * h) for l in landmarks]
        angle_list = []
        angle_list.append(self.vector_2d_angle(((hand_[0][0]- hand_[2][0]), (hand_[0][1]-hand_[2][1])), ((hand_[3][0]- hand_[4][0]), (hand_[3][1]-hand_[4][1]))))
        angle_list.append(self.vector_2d_angle(((hand_[0][0]-hand_[6][0]), (hand_[0][1]-hand_[6][1])), ((hand_[7][0]-hand_[8][0]), (hand_[7][1]-hand_[8][1]))))
        angle_list.append(self.vector_2d_angle(((hand_[0][0]- hand_[10][0]), (hand_[0][1]-hand_[10][1])), ((hand_[11][0]- hand_[12][0]), (hand_[11][1]-hand_[12][1]))))
        angle_list.append(self.vector_2d_angle(((hand_[0][0]- hand_[14][0]), (hand_[0][1]-hand_[14][1])), ((hand_[15][0]- hand_[16][0]), (hand_[15][1]-hand_[16][1]))))
        angle_list.append(self.vector_2d_angle(((hand_[0][0]- hand_[18][0]), (hand_[0][1]-hand_[18][1])), ((hand_[19][0]- hand_[20][0]), (hand_[19][1]-hand_[20][1]))))
        
        f1, f2, f3, f4, f5 = angle_list

        # ROCK (拇指、食指、小指伸直)
        if f1 < 50 and f2 < 50 and f3 >= 50 and f4 >= 50 and f5 < 50: return "ROCK"
        
        # LIKE / DISLIKE (拇指伸直，其餘捲縮)
        if f1 < 50 and f2 >= 50 and f3 >= 50 and f4 >= 50 and f5 >= 50:
            return "LIKE" if landmarks[4]['y'] < landmarks[5]['y'] - 0.05 else "DISLIKE"

        # 數字「6」 (拇指、小指伸直，其餘彎曲)
        if f1 < 50 and f2 >= 50 and f3 >= 50 and f4 >= 50 and f5 < 50: return 6

        # 🏆 補上新需求的手勢：7, 8, 9 (完全符合台灣/Oxxo Studio 手勢辨識標準)
        # 數字「7」 (大拇指、食指伸直，其餘小拇指等彎曲)
        if f1 < 50 and f2 < 50 and f3 >= 50 and f4 >= 50 and f5 >= 50: return 7
        
        # 數字「8」 (大拇指、食指、中指伸直，其餘無名指小指彎曲)
        if f1 < 50 and f2 < 50 and f3 < 50 and f4 >= 50 and f5 >= 50: return 8
        
        # 數字「9」 (大拇指、食指、中指、無名指伸直，僅小指彎曲)
        if f1 < 50 and f2 < 50 and f3 < 50 and f4 < 50 and f5 >= 50: return 9

        # 其他標準數字 1-5
        if f1 >= 50 and f2 < 50 and f3 >= 50 and f4 >= 50 and f5 >= 50: return 1
        if f1 >= 50 and f2 < 50 and f3 < 50 and f4 >= 50 and f5 >= 50: return 2
        if f1 >= 50 and f2 < 50 and f3 < 50 and f4 < 50 and f5 >= 50: return 3
        if f1 >= 50 and f2 < 50 and f3 < 50 and f4 < 50 and f5 < 50: return 4
        if f1 < 50 and f2 < 50 and f3 < 50 and f4 < 50 and f5 < 50: return 5
        
        return sum([1 if a < 50 else 0 for a in angle_list])

    def get_norm_from_data(self, landmarks):
        coords = np.array([[l['x'], l['y']] for l in landmarks])
        center = coords[9]
        coords -= center
        span = np.linalg.norm(coords[0] - coords[9])
        return coords / span if span > 1e-6 else None

class PoseDetector:
    def __init__(self):
        self.counter, self.stage = 0, "DOWN"
    def process_data(self, landmarks):
        if not landmarks: return {"count": self.counter, "stage": self.stage, "done": False}
        try:
            lm = landmarks
            if isinstance(lm, dict): lm = [lm[str(i)] for i in range(max(int(k) for k in lm.keys()) + 1)]
            if len(lm) < 33: return {"count": self.counter, "stage": self.stage, "done": False}
            lw_y, rw_y = lm[15]['y'], lm[16]['y']
            ls_y, rs_y = lm[11]['y'], lm[12]['y']
            hands_up = lw_y < ls_y and rw_y < rs_y
            ankle_dist = abs(lm[27]['x'] - lm[28]['x'])
            hip_width = abs(lm[23]['x'] - lm[24]['x'])
            legs_open = ankle_dist > (hip_width * 1.1)
            if hands_up and legs_open: self.stage = "UP"
            if not hands_up and not legs_open and self.stage == "UP":
                self.stage = "DOWN"
                self.counter += 1
        except: pass
        return {"count": self.counter, "stage": self.stage, "done": self.counter >= 10}

    
class BirdDetector:
    def __init__(self):
        self.SCREEN_W, self.SCREEN_H = 640, 480
        self.bird_y, self.bird_vel = 240, 0
        self.gravity, self.jump_boost = 0.5, -8.0
        self.pipes = [{"x": 640, "gap_y": 150}]
        self.pipe_gap, self.pipe_width = 180, 70
        self.coins, self.status = 0, "WAITING"
        self.last_hand_y, self.has_moved_down = None, False

    def process_data(self, landmarks):
        done = False
        jump_triggered = False
        if landmarks:
            # 取兩手平均高度
            curr_y = (landmarks[15]['y'] + landmarks[16]['y']) / 2
            if self.last_hand_y is not None:
                if self.last_hand_y - curr_y > 0.03: # 向上揮
                    jump_triggered = True
                    if self.status == "WAITING" and self.has_moved_down: self.status = "PLAYING"
                if self.last_hand_y - curr_y < -0.02: self.has_moved_down = True
            self.last_hand_y = curr_y

        if self.status == "PLAYING":
            if jump_triggered: self.bird_vel = self.jump_boost
            self.bird_vel += self.gravity
            self.bird_y += self.bird_vel
            for p in self.pipes: p["x"] -= 8
            if self.pipes[-1]["x"] < 350:
                self.pipes.append({"x": 640, "gap_y": random.randint(100, 250)})
            if self.pipes[0]["x"] < -self.pipe_width:
                self.pipes.pop(0)
                self.coins += 100
            if self.bird_y > self.SCREEN_H or self.bird_y < 0: self.status = "GAMEOVER"
            
            bx, by = 150, self.bird_y
            for p in self.pipes:
                if bx + 20 > p["x"] and bx - 20 < p["x"] + self.pipe_width:
                    if by - 20 < p["gap_y"] or by + 20 > p["gap_y"] + self.pipe_gap:
                        self.status = "GAMEOVER"
        
        if self.status == "GAMEOVER": done = True
        return {"status": self.status, "bird_y": self.bird_y, "pipes": self.pipes, "coins": self.coins, "done": done}