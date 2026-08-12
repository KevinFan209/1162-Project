import os
import requests
from dotenv import load_dotenv

# 自動載入同目錄下的 .env 環境變數檔
load_dotenv()

# 從 .env 中讀取 MOENV_API_KEY
API_KEY = os.getenv("MOENV_API_KEY", "")

# 環境部開放資料 API 網址
ENV_API_URL = f"https://data.moenv.gov.tw/api/v2/aqx_p_432?language=zh&api_key={API_KEY}"

# 南投縣環保局官方 4 大監測站關鍵字對應表
STATION_KEYWORDS = {
    "埔里": ["埔里"],
    "南投": ["南投"],
    "鹿谷": ["鹿谷", "南投（鹿谷）", "南投(鹿谷)"],
    "竹山": ["竹山"]
}

def fetch_aqi_by_name(station_name: str):
    """
    輸入監測站名稱（"埔里"、"南投"、"鹿谷"、"竹山"），
    抓取環境部 API 即時 AQI，並計算遊戲內的動態地價與過路費加成倍率[cite: 1]。
    若傳入非 4 大監測站或空值，則回傳 None（視為一般格子）。
    """
    if not station_name or station_name not in STATION_KEYWORDS:
        return None  # 一般格子，不安裝/不觸發環境氣候事件

    keywords = STATION_KEYWORDS[station_name]
    
    try:
        response = requests.get(ENV_API_URL, timeout=3)
        if response.status_code == 200:
            records = response.json().get("records", [])
            for record in records:
                # 僅篩選南投縣之監測站紀錄
                if record.get("county") == "南投縣":
                    sitename = record.get("sitename", "")
                    
                    # 進行關鍵字匹配（可相容 "南投（鹿谷）" 等官方名稱寫法）
                    if any(kw in sitename for kw in keywords):
                        aqi = int(record.get("aqi", 35))
                        status = record.get("status", "良好")
                        
                        # 動態加成演算機制[cite: 1]：
                        # AQI <= 50 (良好) -> 地價/過路費加成 +15% (1.15)
                        # AQI > 100 (不良) -> 地價/過路費打 85 折 (0.85)
                        # 51~100 (普通) -> 原價 (1.0)
                        multiplier = 1.15 if aqi <= 50 else (0.85 if aqi > 100 else 1.0)
                        
                        return {
                            "has_event": True,
                            "station_name": station_name,
                            "aqi": aqi,
                            "status": status,
                            "multiplier": multiplier
                        }
    except Exception as e:
        print(f"[air.py Warning] 讀取 API 或網路連線異常: {e}")

    # Fallback 防呆機制（當 API Key 未設定、網路斷線或 API 故障時，回傳預設優良數據確保遊戲流暢執行）
    return {
        "has_event": True,
        "station_name": station_name,
        "aqi": 35,
        "status": "良好",
        "multiplier": 1.15
    }