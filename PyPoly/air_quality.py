# -*- coding: utf-8 -*-
"""環境部空氣品質 (AQI) 串接。

由 origin/vamos 分支的 990e880「接環境部API，特定格子有環境加成」移植而來，
原作者 specialstyle035@gmail.com。原版是根目錄的獨立小伺服器 + air_quality.py，
本檔把邏輯搬進 PyPoly，接到既有的 /game/adventure_analysis
（那裡原本有一行 random.randint(15,160) 的 AQI 佔位）。

加成規則沿用原版：
    AQI <= 50  (良好) → 地價與過路費 ×1.15
    AQI >  100 (不良) → ×0.85
    51~100     (普通) → ×1.0
"""
from __future__ import annotations

import os
import ssl

import requests
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MOENV_API_KEY", "")

ENV_API_URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"


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

# 南投縣環保局的 4 大監測站。scenarios.api_station_name 的值需落在這裡才會有環境事件；
# 例如「日月潭」沒有對應測站，會回 None，由呼叫端維持原本的定價流程。
STATION_KEYWORDS = {
    "埔里": ["埔里"],
    "南投": ["南投"],
    "鹿谷": ["鹿谷", "南投（鹿谷）", "南投(鹿谷)"],
    "竹山": ["竹山"],
}

# API 或網路異常時的保底值，確保遊戲流程不因外部服務中斷而卡住
_FALLBACK = {"aqi": 35, "status": "良好", "multiplier": 1.15}


def _multiplier_for(aqi: int) -> float:
    if aqi <= 50:
        return 1.15
    if aqi > 100:
        return 0.85
    return 1.0


def fetch_aqi_by_name(station_name: str | None) -> dict | None:
    """依監測站名稱取得即時 AQI 與加成倍率。

    非 4 大監測站（或空值）回傳 None，代表該格沒有環境事件。
    API 異常時回傳保底值而非 None，以免遊戲流程中斷。
    """
    if not station_name or station_name not in STATION_KEYWORDS:
        return None

    keywords = STATION_KEYWORDS[station_name]

    if not API_KEY:
        # 明確講清楚，否則會靜默退回保底值 35，看起來像功能正常但其實從未取得真實資料
        print("⚠️ MOENV_API_KEY 未設定，AQI 使用保底值（請於 PyPoly/.env 填入）")
        return {"has_event": True, "station_name": station_name, **_FALLBACK}

    try:
        # api_key 用 params 帶，避免金鑰出現在例外訊息或日誌的 URL 中
        res = _session.get(
            ENV_API_URL,
            params={"language": "zh", "api_key": API_KEY},
            timeout=5,
        )
        if res.status_code == 200:
            for record in res.json().get("records", []):
                if record.get("county") != "南投縣":
                    continue
                sitename = record.get("sitename", "")
                # 關鍵字比對，相容「南投（鹿谷）」這類官方寫法
                if any(kw in sitename for kw in keywords):
                    aqi = int(record.get("aqi") or _FALLBACK["aqi"])
                    return {
                        "has_event": True,
                        "station_name": station_name,
                        "aqi": aqi,
                        "status": record.get("status", "良好"),
                        "multiplier": _multiplier_for(aqi),
                    }
        else:
            print(f"⚠️ 環境部 API 回應 HTTP {res.status_code}，改用保底值")
    except Exception as e:
        print(f"⚠️ 讀取環境部 API 失敗（{type(e).__name__}），改用保底值")

    return {"has_event": True, "station_name": station_name, **_FALLBACK}
