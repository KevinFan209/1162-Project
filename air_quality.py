import os
import requests
from dotenv import load_dotenv

# 強制抓取當前檔案所在目錄的 .env 檔案
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# 讀取 API Key
API_KEY = os.getenv("MOENV_API_KEY", "").strip()

# 環境部開放資料 API 基礎網址
ENV_API_URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"

# 南投縣 4 大監測站關鍵字表
STATION_KEYWORDS = {
    "埔里": ["埔里"],
    "南投": ["南投"],
    "鹿谷": ["鹿谷", "南投（鹿谷）", "南投(鹿谷)"],
    "竹山": ["竹山"]
}

def get_aqi_status_and_multiplier(aqi: int):
    """
    根據台灣環境部官方標準判定狀態文字與大富翁遊戲加成倍率
    """
    if aqi <= 50:
        return "良好", 1.15
    elif aqi <= 100:
        return "普通", 1.0
    elif aqi <= 150:
        return "對敏感族群不健康", 0.85
    elif aqi <= 200:
        return "對所有族群不健康", 0.85
    elif aqi <= 300:
        return "非常不健康", 0.85
    else:
        return "危害", 0.85

def fetch_aqi_by_name(station_name: str):
    """
    輸入監測站名稱（"埔里"、"南投"、"鹿谷"、"竹山"），
    抓取環境部 API 即時 AQI，並精確計算遊戲動態倍率與文字狀態。
    """
    if not station_name or station_name not in STATION_KEYWORDS:
        return None

    keywords = STATION_KEYWORDS[station_name]
    print(f"\n[AirQuality] 收到查詢請求: {station_name}")
    print(f"[AirQuality] 讀取到的 API Key 長度: {len(API_KEY)} (前4碼: {API_KEY[:4]}***)")

    try:
        params = {
            "language": "zh",
            "api_key": API_KEY
        }
        response = requests.get(ENV_API_URL, params=params, timeout=6)
        print(f"[AirQuality] API 回應狀態碼: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])
            print(f"[AirQuality] 成功取得 {len(records)} 筆監測站資料")

            for record in records:
                # 篩選南投縣
                if record.get("county") == "南投縣":
                    sitename = record.get("sitename", "")
                    
                    # 匹配關鍵字
                    if any(kw in sitename for kw in keywords):
                        raw_aqi = record.get("aqi", "")
                        
                        # 安全轉型 AQI（防止空字串崩潰）
                        if str(raw_aqi).isdigit():
                            aqi = int(raw_aqi)
                        else:
                            print(f"[AirQuality] 測站 {sitename} AQI 暫無數值: '{raw_aqi}'，給予預設值 25")
                            aqi = 25

                        # 依據標準計算狀態文字與倍率
                        status, multiplier = get_aqi_status_and_multiplier(aqi)
                        
                        print(f"🎉 [成功比對] 站名: {sitename} | 即時 AQI: {aqi} | 狀態: {status} | 倍率: {multiplier}")

                        return {
                            "has_event": True,
                            "station_name": station_name,
                            "aqi": aqi,
                            "status": status,
                            "multiplier": multiplier
                        }

            print(f"⚠️ [比對失敗] 在南投縣紀錄中未找到符合 {keywords} 的測站")
        else:
            print(f"❌ [API 拒絕] 狀態碼 {response.status_code}，錯誤訊息: {response.text}")

    except requests.exceptions.Timeout:
        print("❌ [連線超時] 外部環境部 API 回應超過 6 秒")
    except Exception as e:
        print(f"❌ [執行例外]: {e}")

    # Fallback 備用值（同樣經過標準函式換算）
    default_aqi = 35
    default_status, default_multiplier = get_aqi_status_and_multiplier(default_aqi)
    
    print(f"⚠️ 觸發 Fallback 備用值 (AQI: {default_aqi}, 狀態: {default_status})")
    return {
        "has_event": True,
        "station_name": station_name,
        "aqi": default_aqi,
        "status": default_status,
        "multiplier": default_multiplier
    }