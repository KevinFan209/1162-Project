from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import socket
import os

app = FastAPI()

# --- Mock auth 端點（讓 character.html 的 API 呼叫不報錯）---

@app.post("/auth/verify_and_refresh")
def verify_and_refresh(username: str = ""):
    return {"status": "success"}

@app.post("/auth/heartbeat")
def heartbeat(username: str = ""):
    return {"status": "alive"}

@app.post("/auth/logout")
def logout(username: str = "", confirm: str = ""):
    return {"status": "success"}

# --- 根路徑：自動設定假登入狀態，提供選擇頁面 ---

@app.get("/")
def root():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>BeeRich Demo</title>
<style>
  body { font-family: 'Segoe UI', sans-serif; background: #f1f5f9;
         display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
  .box { background: white; border-radius: 24px; padding: 40px 48px; text-align: center;
         box-shadow: 0 8px 30px rgba(0,0,0,0.08); }
  h1  { font-size: 2rem; font-weight: 900; margin-bottom: 8px; }
  p   { color: #64748b; margin-bottom: 28px; }
  .btn { display: block; width: 100%; padding: 14px; margin-bottom: 12px; border: none;
         border-radius: 13px; font-size: 1rem; font-weight: 800; cursor: pointer; text-decoration: none; }
  .a  { background: #4facfe; color: white; }
  .b  { background: #f1f5f9; color: #64748b; }
  .b:hover { background: #e2e8f0; }
</style>
</head>
<body>
<div class="box">
  <h1>BeeRich</h1>
  <p>請選擇要測試的版本</p>
  <a class="btn a" href="/Facial_features/方案A/character.html" id="lnkA">方案 A ─ Canvas 五官自定義</a>
  <a class="btn a" href="/Facial_features/方案B/character.html" style="background:#a78bfa">方案 B ─ 網路圖片 / Emoji 表情</a>
  <a class="btn b" href="/character.html">原版角色自定義</a>
</div>
<script>
  localStorage.setItem('username', 'demo');
  localStorage.setItem('token', 'demo-token');
</script>
</body>
</html>""")

# --- 靜態檔案掛載（順序：特定路徑在前，根目錄在後）---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# /Facial_features/ → my-work/Facial_features/（方案A/B 的 HTML 檔）
app.mount("/Facial_features", StaticFiles(directory=os.path.join(BASE_DIR, "Facial_features")), name="facial")

# /static/ → my-work/static/（方案A 的相對路徑 ../../static/ 會解析成 /static/）
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static_dir")

# / → my-work/static/（原有路由，向後相容）
app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "static"), html=True), name="static")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 55)
    print("  BeeRich 角色自定義展示伺服器")
    print("=" * 55)
    print(f"  本機網址：http://localhost:8000")
    print(f"  區網網址：http://{local_ip}:8000")
    print()
    print(f"  方案A 五官自定義：http://localhost:8000/Facial_features/方案A/character.html")
    print(f"  方案B 圖片表情  ：http://localhost:8000/Facial_features/方案B/character.html")
    print(f"  原版角色自定義  ：http://localhost:8000/character.html")
    print("=" * 55)
    print("\n按 Ctrl+C 關閉伺服器\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
