import cv2
import mediapipe as mp
import numpy as np

mp_drawing = mp.solutions.drawing_utils          # mediapipe 繪圖方法
mp_drawing_styles = mp.solutions.drawing_styles  # mediapipe 繪圖樣式
mp_pose = mp.solutions.pose                      # mediapipe 姿勢偵測

# 計數變數
counter = 0
stage = "DOWN"

cap = cv2.VideoCapture(0)

# 啟用姿勢偵測
with mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=1) as pose:

    if not cap.isOpened():
        print("Cannot open camera")
        exit()

    while True:
        ret, img = cap.read()
        if not ret:
            print("Cannot receive frame")
            break

        img = cv2.flip(img, 1) # 鏡像處理，比較好對準
        img = cv2.resize(img, (640, 480))             # 稍微加大一點點，增加偵測精準度
        img2 = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)   # 將 BGR 轉換成 RGB
        results = pose.process(img2)                  # 取得姿勢偵測結果

        # --- 邏輯判定區 ---
        if results.pose_landmarks:
            # 標記身體節點和骨架
            mp_drawing.draw_landmarks(
                img,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style())

            # 取得點位數據
            lm = results.pose_landmarks.landmark
            
            try:
                # 1. 取得座標 (手腕 15,16 | 肩膀 11,12 | 髖部 23,24 | 腳踝 27,28)
                lw_y, rw_y = lm[15].y, lm[16].y
                ls_y, rs_y = lm[11].y, lm[12].y
                
                # 2. 手部判定：手腕高於肩膀 (y值越小越高)
                hands_up = lw_y < ls_y and rw_y < rs_y
                
                # 3. 腿部判定：腳踝距離 > 髖部寬度的 1.5 倍
                ankle_dist = abs(lm[27].x - lm[28].x)
                hip_width = abs(lm[23].x - lm[24].x)
                legs_open = ankle_dist > (hip_width * 1.5)

                # 4. 狀態機計數
                if hands_up and legs_open:
                    if stage == "DOWN":
                        stage = "UP"
                
                if not hands_up and not legs_open:
                    if stage == "UP":
                        stage = "DOWN"
                        counter += 1
                        print(f"Count: {counter}")
            except:
                pass

        # --- UI 調整區 ---
        # 畫一個半透明黑色背景框
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (220, 100), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

        # 顯示計數與狀態
        cv2.putText(img, f"COUNT: {counter}", (30, 50), 
                    cv2.FONT_HERSHEY_DUPLEX, 1, (0, 255, 0), 2)
        cv2.putText(img, f"STAGE: {stage}", (30, 85), 
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow('Monopoly - Jumping Jacks', img)
        
        if cv2.waitKey(5) == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()