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

# --- 根路徑：自動設定假登入狀態再跳轉到角色自定義頁 ---

@app.get("/")
def root():
    return HTMLResponse("""
    <script>
        localStorage.setItem('username', 'demo');
        localStorage.setItem('token', 'demo-token');
        window.location.href = '/character.html';
    </script>
    """)

# --- 靜態檔案（放在所有路由之後）---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
    print("=" * 50)
    print("  角色自定義展示伺服器")
    print("=" * 50)
    print(f"  本機網址：http://localhost:8000")
    print(f"  區網網址：http://{local_ip}:8000")
    print("=" * 50)
    print("\n按 Ctrl+C 關閉伺服器\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
