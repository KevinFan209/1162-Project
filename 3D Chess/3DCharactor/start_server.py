import subprocess
import sys
import time
import os
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
PORT = 8000

uvicorn_proc = None
ngrok_proc = None


def kill_port(port):
    """結束佔用指定 port 的程序"""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True)
                print(f"  已結束 port {port} 上的程序 (PID {pid})")
                time.sleep(1)
                return
    except Exception as e:
        print(f"  警告：無法清除 port {port}：{e}")


def kill_existing_ngrok():
    """關閉所有已在運行的 ngrok 程序"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ngrok.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        if "ngrok.exe" in result.stdout:
            subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"],
                           capture_output=True)
            print("  已關閉舊有的 ngrok 程序")
            time.sleep(1)
    except Exception as e:
        print(f"  警告：無法關閉舊 ngrok：{e}")


def find_ngrok_api_port(max_retries=15, interval=1.0):
    import requests as req
    for i in range(max_retries):
        for port in range(4040, 4046):
            try:
                resp = req.get(f"http://localhost:{port}/api/tunnels", timeout=1)
                tunnels = resp.json().get("tunnels", [])
                if tunnels is not None:
                    return port, tunnels
            except Exception:
                pass
        print(f"  等待 ngrok 就緒... ({i + 1}/{max_retries})")
        time.sleep(interval)
    return None, []


def get_ngrok_url():
    port, tunnels = find_ngrok_api_port()
    if port is None:
        return None, None
    for t in tunnels:
        if t.get("proto") == "https":
            return t["public_url"], port
    if tunnels:
        return tunnels[0]["public_url"], port
    return None, port


def shutdown(signum=None, frame=None):
    print("\n正在關閉所有程序...")
    if ngrok_proc and ngrok_proc.poll() is None:
        ngrok_proc.terminate()
    if uvicorn_proc and uvicorn_proc.poll() is None:
        uvicorn_proc.terminate()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

if __name__ == "__main__":
    print("=" * 50)
    print("  PyPoly 伺服器啟動工具")
    print("=" * 50)

    print(f"\n[0/3] 清除舊有程序 (port {PORT} / ngrok)...")
    kill_port(PORT)
    kill_existing_ngrok()

    print("[1/3] 啟動 uvicorn 伺服器...")
    uvicorn_proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "main:sio_app",
         "--host", "127.0.0.1", f"--port", str(PORT), "--reload"],
        cwd=BASE_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(3)

    print("[2/3] 啟動 ngrok 通道...")
    ngrok_proc = subprocess.Popen(
        ["ngrok", "http", str(PORT)],
        cwd=BASE_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    print("[3/3] 等待取得公開網址...")
    url, api_port = get_ngrok_url()

    print("\n" + "=" * 50)
    if url:
        print(f"  伺服器已啟動！")
        print(f"  公開網址：{url}")
        print(f"  本機網址：http://127.0.0.1:{PORT}")
        print(f"  ngrok 管理頁：http://localhost:{api_port}")
    else:
        print("  無法自動取得 ngrok 網址")
        print(f"  請手動開啟 http://localhost:4040 查看")
    print("=" * 50)
    print("\n按 Ctrl+C 關閉所有程序\n")

    try:
        while True:
            if uvicorn_proc.poll() is not None:
                print("uvicorn 已意外結束，正在關閉...")
                shutdown()
            if ngrok_proc.poll() is not None:
                print("ngrok 已意外結束，正在關閉...")
                shutdown()
            time.sleep(3)
    except KeyboardInterrupt:
        shutdown()
