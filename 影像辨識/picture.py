import os # 匯入處理檔案路徑、移動檔案及打亂順序的內建工具
import shutil
import random
import time
from bing_image_downloader import downloader # 匯入從網路（Bing）抓取圖片

# 1. 定義手勢類別與路徑
gestures = ['hand gesture 1', 'hand gesture 2', 'hand gesture 3', 
            'hand gesture 4', 'hand gesture 5', 'hand gesture 6']
base_dir = "dataset" # 設定資料集的最外層資料夾名稱
images_dir = os.path.join(base_dir, "images") # 使用 os.path.join 建立符合 YOLO 規範的路徑字串
train_dir = os.path.join(images_dir, "train")
val_dir = os.path.join(images_dir, "val")

# 建立結構資料夾 這行會實際在你的電腦裡建立 images/train、images/val（存照片）以及 labels/train、labels/val（存標籤）
for path in [train_dir, val_dir, os.path.join(base_dir, "labels/train"), os.path.join(base_dir, "labels/val")]:
    os.makedirs(path, exist_ok=True) # 代表如果資料夾已經存在，會直接跳過

# 2. 從網路抓取圖片
for i, gesture in enumerate(gestures):
    print(f"\n[開始抓取類別 {i+1}]: {gesture}...")
    
    try:
        # limit 設為 1000。加入 timeout=10，若連續 10 秒沒抓到新圖會嘗試結束 
        # 註：此套件若在網路上找不到更多圖，通常會自動停止並換下一類
        downloader.download(
            gesture, 
            limit=1000, 
            output_dir='temp_download', 
            adult_filter_off=True, 
            force_replace=False, 
            timeout=10 
        )
    except Exception as e:
        print(f"抓取 {gesture} 時發生錯誤或已達上限，自動跳過並處理現有檔案。")

    # 3. 立即分配已抓到的圖片到 train 和 val 
    src_folder = os.path.join('temp_download', gesture)
    if os.path.exists(src_folder):
        all_files = [f for f in os.listdir(src_folder) if os.path.isfile(os.path.join(src_folder, f))]
        
        random.shuffle(all_files) # 確保資料多樣性 
        
        # 依照簡報建議：80% 訓練, 20% 驗證 
        split_idx = int(len(all_files) * 0.8) 
        
        print(f"-> 類別 {i+1} 共抓到 {len(all_files)} 張圖。正在進行分配...")

        # 搬移到train
        for f in all_files[:split_idx]:
            new_name = f"gesture_{i+1}_{int(time.time()*1000)}_{f}" # 加入時間戳避免檔名重複
            shutil.move(os.path.join(src_folder, f), os.path.join(train_dir, new_name)) # 將圖片從暫存資料夾正式搬移到 dataset/images/train/ 或 dataset/images/val/
            
        # 搬移到val
        for f in all_files[split_idx:]:
            new_name = f"gesture_{i+1}_{int(time.time()*1000)}_{f}"
            shutil.move(os.path.join(src_folder, f), os.path.join(val_dir, new_name))
            
        # 清理暫存資料夾
        shutil.rmtree(src_folder)

print("\n任務結束！所有可用的圖片已下載並依 8:2 比例分配完成。")
print(f"請檢查 {train_dir} 與 {val_dir} 產生的照片。")