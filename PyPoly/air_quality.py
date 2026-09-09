import os
import requests
from dotenv import load_dotenv
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CWD_DIR = os.getcwd()

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(CWD_DIR, ".env"))

API_KEY = os.getenv("MOENV_API_KEY", "").strip()
ENV_API_URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"

# 4 大測站對應的關鍵字
STATION_KEYWORDS = {
    "埔里": ["埔里"],
    "南投": ["南投"],
    "鹿谷": ["鹿谷"],
    "竹山": ["竹山"]
}

def get_aqi_status_and_multiplier(aqi: int):
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
    print("\n" + "="*50)
    print(f"🔍 [查詢開始] 傳入地點: {station_name}")

    if not station_name:
        return None

    # 1. 只要傳入名稱包含四大測站關鍵字就算命中（例如：竹山天梯 -> 命中「竹山」）
    matched_station = None
    for st_name, keywords in STATION_KEYWORDS.items():
        if any(kw in station_name for kw in keywords):
            matched_station = st_name
            break

    # 包含非四大測站關鍵字的地點（例如：中寮土窯、魚池），回傳 None 顯示預設 --
    if not matched_station:
        print(f"ℹ️ 地點 '{station_name}' 無對應測站，顯示 '--'")
        print("="*50 + "\n")
        return None

    print(f"🎯 命中測站: [{matched_station}]，準備向環境部查詢...")

    try:
        params = {
            "language": "zh",
            "api_key": API_KEY
        }
        response = requests.get(ENV_API_URL, params=params, timeout=10, verify=False)

        if response.status_code == 200:
            data = response.json()
            records = data if isinstance(data, list) else data.get("records", [])

            for record in records:
                sitename = record.get("sitename", "")
                county = record.get("county", "")

                # 2. 比對環境部 API 中的測站名稱（精準對應「竹山」、「埔里」等）
                if county == "南投縣" and matched_station in sitename:
                    raw_aqi = record.get("aqi", "")
                    if str(raw_aqi).isdigit():
                        aqi = int(raw_aqi)
                        status, multiplier = get_aqi_status_and_multiplier(aqi)

                        print(f"🎉 【比對成功】測站: {sitename} | 即時 AQI: {aqi} | 狀態: {status} | 倍率: {multiplier}")
                        print("="*50 + "\n")
                        return {
                            "has_event": True,
                            "station_name": matched_station,
                            "aqi": aqi,
                            "status": status,
                            "multiplier": multiplier
                        }

            print(f"⚠️ API 中找不到 {matched_station} 測站資料")
        else:
            print(f"❌ API 回應錯誤: {response.status_code}")

    except Exception as e:
        print(f"❌ [執行例外]: {e}")

    print("="*50 + "\n")
    return None

if __name__ == "__main__":
    print("測試竹山天梯 ->", fetch_aqi_by_name("竹山天梯"))
    print("測試中寮土窯 ->", fetch_aqi_by_name("中寮土窯"))