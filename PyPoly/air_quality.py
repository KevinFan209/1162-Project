# -*- coding: utf-8 -*-
"""環境部空氣品質 (AQI) 串接。

由 origin/vamos 分支的 990e880「接環境部API，特定格子有環境加成」移植而來，
原作者 specialstyle035@gmail.com。原版是根目錄的獨立小伺服器 + air_quality.py，
本檔把邏輯搬進 PyPoly，接到既有的 /game/adventure_analysis
（那裡原本有一行 random.randint(15,160) 的 AQI 佔位）。

解析與比對邏輯來自 teca 分支（環境部 API 實際回傳的是裸 list，不是
{"records": [...]}，舊版在此直接拋 AttributeError 而永遠取不到真實資料）。

加成規則：
    AQI <= 50  (良好) → 地價與過路費 ×1.15
    51~100     (普通) → ×1.0
    AQI >  100 (不良) → ×0.85
"""
from __future__ import annotations

import os
import ssl

import requests
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv

# 從模組所在目錄與目前工作目錄各讀一次：直接跑 uvicorn 與在容器內執行時
# 工作目錄不同，兩邊都試才不會漏掉 .env。
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"))
load_dotenv(os.path.join(os.getcwd(), ".env"))

API_KEY = os.getenv("MOENV_API_KEY", "").strip()

ENV_API_URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"

# 南投縣 4 大監測站。值是「環境部 API 的站名」——比對時用它，
# 而不是拿 key 去做子字串比對：API 裡的「南投（鹿谷）」也包含「南投」，
# 用 in 比對會讓查南投時誤中鹿谷站（先前只是靠 API 回傳順序僥倖正確）。
STATION_SITENAMES = {
    "埔里": "埔里",
    "南投": "南投",
    "鹿谷": "南投（鹿谷）",
    "竹山": "竹山",
}


class _MoenvAdapter(HTTPAdapter):
    """放寬 X.509 嚴格檢查的 HTTPS adapter。

    為什麼需要：Python 3.13 起 ssl.create_default_context() 預設啟用
    VERIFY_X509_STRICT，而環境部 data.moenv.gov.tw 的憑證缺少
    Subject Key Identifier 擴充欄位，於是 requests 直接拋
    SSLCertVerificationError('Missing Subject Key Identifier')。
    實測 curl（走 Windows schannel）連得上，證明問題出在 Python 端的嚴格檢查。

    這裡只關閉 STRICT 這一項 RFC 形式檢查，
    CA 鏈、主機名、有效期的驗證全部保留——
    不是 verify=False，不會讓連線變成不驗證憑證。
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


_session = requests.Session()
_session.mount("https://", _MoenvAdapter())


def get_aqi_status_and_multiplier(aqi: int) -> tuple[str, float]:
    """依環境部官方分級回傳（狀態文字, 遊戲加成倍率）。"""
    if aqi <= 50:
        return "良好", 1.15
    if aqi <= 100:
        return "普通", 1.0
    if aqi <= 150:
        return "對敏感族群不健康", 0.85
    if aqi <= 200:
        return "對所有族群不健康", 0.85
    if aqi <= 300:
        return "非常不健康", 0.85
    return "危害", 0.85


def _match_station(place: str) -> str | None:
    """把地點名稱對應到四大測站之一，對應不到回 None。

    用「包含」而非相等，是為了讓 scenarios 的地點名（竹山天梯、埔里酒廠）
    也能命中。非四大測站的地點（日月潭、魚池）回 None，
    由 main.py 的 has_env_event 判定為「沒有環境事件」並顯示 --。
    """
    if not place:
        return None
    for station in STATION_SITENAMES:
        if station in place:
            return station
    return None


def fetch_aqi_by_name(station_name: str | None) -> dict | None:
    """依地點名稱取得即時 AQI 與加成倍率。

    取不到資料時回 None 而非保底值：舊版失敗時回 AQI 35「良好」，
    看起來像成功取得資料其實是假的。回 None 時 main.py:1416 的
    has_env_event 為 False、倍率退回 1.0，介面顯示 --，比較誠實。
    """
    station = _match_station(station_name)
    if not station:
        return None

    if not API_KEY:
        print("⚠️ MOENV_API_KEY 未設定，冒險格不會有空氣品質加成（請於 PyPoly/.env 填入）")
        return None

    target_sitename = STATION_SITENAMES[station]

    try:
        # api_key 用 params 帶，不要自己拼進網址
        res = _session.get(
            ENV_API_URL,
            params={"language": "zh", "api_key": API_KEY},
            timeout=10,
        )
        if res.status_code != 200:
            print(f"⚠️ 環境部 API 回應 HTTP {res.status_code}，本次不套用空氣品質加成")
            return None

        data = res.json()
        # 環境部這支 API 回傳的是裸 list；保留 dict 分支以防日後格式再變
        records = data if isinstance(data, list) else data.get("records", [])

        for record in records:
            if record.get("county") != "南投縣":
                continue
            if record.get("sitename") != target_sitename:
                continue

            raw_aqi = record.get("aqi", "")
            if not str(raw_aqi).isdigit():
                # 測站維護中或當下沒有數值，不要用假資料頂替
                print(f"⚠️ 測站 {target_sitename} 目前無 AQI 數值（{raw_aqi!r}）")
                return None

            aqi = int(raw_aqi)
            status, multiplier = get_aqi_status_and_multiplier(aqi)
            print(f"🌤️ {station}：AQI {aqi}（{status}），加成 ×{multiplier}")
            return {
                "has_event": True,
                "station_name": station,
                "aqi": aqi,
                "status": status,
                "multiplier": multiplier,
            }

        print(f"⚠️ 環境部資料中找不到測站 {target_sitename}")
    except Exception as e:
        print(f"⚠️ 讀取環境部 API 失敗（{type(e).__name__}），本次不套用空氣品質加成")

    return None


if __name__ == "__main__":
    # 直接執行本檔做手動測試時，主控台若是 cp950(繁中) 會因 emoji 拋
    # UnicodeEncodeError（與 main.py / seed_data.py 開頭相同的處理）。
    # 由伺服器 import 時不會走到這裡，main.py 已在自己開頭處理過。
    import sys as _sys
    for _s in (_sys.stdout, _sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # 傳入的是 scenarios.api_station_name（南投/埔里/竹山/日月潭），
    # 不是情境名稱——見 main.py:1415。
    for station in ("竹山", "埔里", "南投", "鹿谷", "日月潭"):
        print(f"{station} -> {fetch_aqi_by_name(station)}")
