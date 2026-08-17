import subprocess
import sys
import time
import os
import signal
import socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable  # 使用目前執行的 Python，不依賴 venv
PORT = 8000

uvicorn_proc = None


def kill_port(port):
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                print(f"  已結束 port {port} 上的程序 (PID {pid})")
                time.sleep(1)
                return
    except Exception as e:
        print(f"  警告：無法清除 port {port}：{e}")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def shutdown(signum=None, frame=None):
    print("\n正在關閉伺服器...")
    if uvicorn_proc and uvicorn_proc.poll() is None:
        uvicorn_proc.terminate()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

if __name__ == "__main__":
    print("=" * 50)
    print("  BeeRich 伺服器啟動工具")
    print("=" * 50)

    print(f"\n[1/2] 清除舊有程序 (port {PORT})...")
    kill_port(PORT)

    print("[2/2] 啟動 uvicorn 伺服器...")
    uvicorn_proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "main:sio_app",
         "--host", "0.0.0.0", "--port", str(PORT), "--reload"],
        cwd=BASE_DIR,
    )
    time.sleep(3)

    local_ip = get_local_ip()
    print("\n" + "=" * 50)
    print(f"  伺服器已啟動！")
    print(f"  本機網址：http://localhost:{PORT}")
    print(f"  區網網址：http://{local_ip}:{PORT}")
    print("=" * 50)
    print("\n按 Ctrl+C 關閉伺服器\n")

    try:
        while True:
            if uvicorn_proc.poll() is not None:
                print("uvicorn 已意外結束，正在關閉...")
                shutdown()
            time.sleep(3)
    except KeyboardInterrupt:
        shutdown()
