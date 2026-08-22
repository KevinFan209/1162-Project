import os
import requests
from dotenv import load_dotenv

# 強制讀取當前檔案所在目錄或工作目錄的 .env 檔案
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CWD_DIR = os.getcwd()

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(CWD_DIR, ".env"))

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
    抓取環境部 API 即時 AQI，並計算遊戲動態倍率與文字狀態。
    """
    print("\n" + "="*50)
    print(f"🔍 [查詢開始] 測站: {station_name}")

    if not station_name or station_name not in STATION_KEYWORDS:
        print(f"❌ 傳入的測站名稱 '{station_name}' 不在關鍵字表中")
        return None

    keywords = STATION_KEYWORDS[station_name]

    try:
        params = {
            "language": "zh",
            "api_key": API_KEY
        }
        response = requests.get(ENV_API_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            
            # 相容處理：環境部 API 回傳可能是 List 或包含 records 鍵值的 Dict
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = data.get("records", [])
            else:
                records = []

            print(f"📦 成功解析監測資料，共 {len(records)} 筆")

            for record in records:
                sitename = record.get("sitename", "")
                county = record.get("county", "")

                # 匹配南投縣與站名關鍵字
                if county == "南投縣" or any(kw in sitename for kw in keywords):
                    if any(kw in sitename for kw in keywords):
                        raw_aqi = record.get("aqi", "")
                        
                        # 安全轉型 AQI
                        if str(raw_aqi).isdigit():
                            aqi = int(raw_aqi)
                        else:
                            print(f"⚠️ 測站 {sitename} AQI 暫無數值: '{raw_aqi}'，給予預設值 25")
                            aqi = 25

                        status, multiplier = get_aqi_status_and_multiplier(aqi)

                        print(f"🎉 【比對成功】測站: {sitename} | 即時 AQI: {aqi} | 狀態: {status} | 倍率: {multiplier}")
                        print("="*50 + "\n")
                        return {
                            "has_event": True,
                            "station_name": station_name,
                            "aqi": aqi,
                            "status": status,
                            "multiplier": multiplier
                        }

            print(f"⚠️ 未在 API 資料中找到符合 {keywords} 的測站")
        else:
            print(f"❌ API 回應錯誤 (狀態碼 {response.status_code}): {response.text}")

    except requests.exceptions.Timeout:
        print("❌ [連線超時] 外部環境部 API 回應超過 10 秒")
    except Exception as e:
        print(f"❌ [執行例外]: {e}")

    # Fallback 備用值
    default_aqi = 35
    default_status, default_multiplier = get_aqi_status_and_multiplier(default_aqi)
    print(f"⚠️ 觸發 Fallback 備用值 (AQI: {default_aqi}, 狀態: {default_status})")
    print("="*50 + "\n")
    return {
        "has_event": True,
        "station_name": station_name,
        "aqi": default_aqi,
        "status": default_status,
        "multiplier": default_multiplier
    }

if __name__ == "__main__":
    test_result = fetch_aqi_by_name("埔里")
    print("終端測試回傳物件:", test_result)