from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from air_quality import fetch_aqi_by_name

app = FastAPI(title="Beerich PyPoly Backend API")

# 設定 CORS 跨域連線存取
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "running", "message": "PyPoly API 正常運作中"}

@app.get("/api/air-quality")
def get_air_quality(station: str = Query(None, description="監測站名稱，如：埔里, 南投, 鹿谷, 竹山")):
    """
    前端踩格時呼叫此 API：
    - 若為 4 大監測站之一：回傳 AQI 與加成倍率
    - 若為一般地點：回傳 has_event = False
    """
    result = fetch_aqi_by_name(station)
    if result:
        return result
    return {"has_event": False}