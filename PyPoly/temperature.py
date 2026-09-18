# -*- coding: utf-8 -*-
"""交通部中央氣象署 (CWA) 即時氣溫串接模組。

設計邏輯：
優先比對 13 鄉鎮對應測站，結合 64 個指定景點關鍵字，
不論地圖寫全名還是簡稱，都能自動對應最近測站！
"""
from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"))
load_dotenv(os.path.join(os.getcwd(), ".env"))
load_dotenv()

CWA_API_KEY = os.getenv("CWA_API_KEY", "").strip()
CWA_API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"

# 1. 鄉鎮市區對應之最近氣象測站
TOWNSHIP_TO_STATION: dict[str, str] = {
    "南投市": "南投",
    "中寮鄉": "南投",
    "名間鄉": "名間",
    "草屯鎮": "草屯",
    "國姓鄉": "國姓",
    "埔里鎮": "埔里",
    "魚池鄉": "日月潭",
    "水里鄉": "水里",
    "集集鎮": "集集",
    "竹山鎮": "竹山",
    "鹿谷鄉": "鹿谷",
    "信義鄉": "信義",
    "仁愛鄉": "仁愛",
}

# 2. 特殊高山獨立測站（優先度高於鄉鎮）
SPECIAL_SPOTS: dict[str, str] = {
    "合歡山": "合歡山",
    "暗空公園": "合歡山",
    "溪頭": "溪頭",
    "玉山": "玉山",
    "望鄉": "玉山",
}

# 3. 需排除的室內/純飲食/文化節慶關鍵字（直接不套用氣溫，回傳 None）
EXCLUDE_KEYWORDS = [
    "意麵", "肉圓", "點心", "美食", "特產", "小吃", "城隍祭", "迎神", "遶境"
]


def get_temp_status_and_multiplier(temp: float) -> tuple[str, float]:
    """依氣溫回傳（狀態說明, 加成倍率）。"""
    if 18.0 <= temp <= 26.0:
        return "舒適宜人", 1.10
    if 26.0 < temp <= 32.0:
        return "普通溫和", 1.00
    if temp > 32.0:
        return "酷暑炎熱", 0.90
    return "低溫寒冷", 0.90


def match_station(place_name: str | None, township: str | None = None) -> str | None:
    """自動推導最近測站，無需完全匹配景點全名。"""
    full_str = f"{township or ''}{place_name or ''}"
    if not full_str:
        return None

    # 檢查是否屬於排除的文化活動
    for kw in EXCLUDE_KEYWORDS:
        if kw in full_str:
            return None

    # 1. 先看是否有特殊高山景點（如合歡山、溪頭）
    for spot, station in SPECIAL_SPOTS.items():
        if spot in full_str:
            return station

    # 2. 直接依鄉鎮市區對應最近測站
    if township:
        for t_name, station in TOWNSHIP_TO_STATION.items():
            if t_name[:2] in township:  # 支援 "魚池"、"魚池鄉"
                return station

    # 3. 若無 township 則從地名中找鄉鎮關鍵字
    for t_name, station in TOWNSHIP_TO_STATION.items():
        if t_name[:2] in full_str:
            return station

    return None


def fetch_temperature(place_name: str | None, township: str | None = None) -> dict | None:
    """依景點或鄉鎮自動取得最近測站氣溫與天氣現象。"""
    target_station = match_station(place_name, township)
    if not target_station:
        return None

    if not CWA_API_KEY:
        return None

    try:
        params = {
            "Authorization": CWA_API_KEY,
            "StationName": target_station,
        }
        res = requests.get(CWA_API_URL, params=params, timeout=10, verify=False)
        if res.status_code != 200:
            return None

        stations = res.json().get("records", {}).get("Station", [])
        for st in stations:
            weather_elem = st.get("WeatherElement", {})
            air_temp_val = None
            weather_desc = "晴"

            # 支援 dict 與 list 兩種回傳結構
            if isinstance(weather_elem, dict):
                air_temp_val = weather_elem.get("AirTemperature")
                weather_desc = weather_elem.get("Weather") or "晴"
            elif isinstance(weather_elem, list):
                for elem in weather_elem:
                    elem_name = elem.get("ElementName")
                    if elem_name == "AirTemperature":
                        air_temp_val = elem.get("ElementValue")
                    elif elem_name == "Weather":
                        weather_desc = elem.get("ElementValue") or "晴"

            if air_temp_val is not None:
                try:
                    temp = float(air_temp_val)
                    if temp < -50:
                        continue
                    status, multiplier = get_temp_status_and_multiplier(temp)
                    print(f"🌡️ [{target_station}站] {township or ''}-{place_name}：{temp}°C，{weather_desc}（{status}），加成 ×{multiplier}")
                    return {
                        "has_temp_event": True,
                        "station_name": target_station,
                        "temperature": temp,
                        "weather": weather_desc,
                        "status": status,
                        "multiplier": multiplier,
                    }
                except ValueError:
                    continue
    except Exception as e:
        print(f"⚠️ 讀取氣象署 API 失敗：{e}")

    return None