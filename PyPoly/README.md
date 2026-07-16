# PyPoly 啟動說明

程式互動式大富翁（FastAPI + Socket.IO 後端，Three.js 前端）。

## 環境需求
- Python 3.11+
- MySQL（XAMPP 皆可），資料庫名稱 `pypoly_db`

## 安裝
```bash
cd PyPoly
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # 再填入實際值（Windows: copy .env.example .env）
```

## 初始化資料庫
啟動時 `models.Base.metadata.create_all` 會自動建表；種子資料請**依序**執行
（順序很重要：`init_adventure_data.py` 會覆蓋 `scenarios`，須最後跑正式情境）：
```bash
python seed_data.py            # 題庫（含 opt4）
python init_adventure_data.py  # 5 筆南投正式情境（含 skybox）
python create_admin.py         # 建立管理員帳號
```

## 啟動伺服器 ⚠️ 必須指向 sio_app
多人同步走 Socket.IO，入口是 `sio_app`（不是 `app`）。
用 `uvicorn main:app` 或 `fastapi dev main.py` 會讓 `/socket.io` 回 404、多人流程靜默失效。
且必須在 `PyPoly/` 目錄下啟動（`StaticFiles` 與手勢標準檔為相對路徑）：

```bash
cd PyPoly
uvicorn main:sio_app --host 0.0.0.0 --port 8000
```

啟動後開 `http://<主機IP>:8000/static/login.html`。
自我檢查：`http://<主機IP>:8000/socket.io/?EIO=4&transport=polling` 應回 Socket.IO 握手字串（非 404）。

## 備註
- 機敏設定（`SECRET_KEY` / `SENDER_EMAIL` / `SENDER_PASSWORD`）一律放 `.env`，勿寫死於程式碼。
- 前端 API 位址採 `location.hostname` 動態組出，本機與區網（平板/手機）皆通。
- 各需求的完善計畫見 `gitignore/claude-workspace/專案完善計畫(Fable二版).md`。
