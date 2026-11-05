# 1162資管系專題-碼上致富BeeRich
用於與組員整合各自的檔案
## 主題
用遊戲化(大富翁)的方式結合影像辨識學習Python程式語言
## 組員&指導老師
- 葉諭玹
- 李宣穎
- 蘇嘉鈞
- 黃柏睿
- 范植鈞
- 導師: 鄭育評
## 複製檔案
```bash
git clone https://github.com/KevinFan209/1162-Project.git
cd 1162-Project
```

## 目前的專案結構（2026-08 整併後）

小組決議以原 `Fan` 分支為主要專案，並把散在根目錄的早期原型集中封存，
根目錄現在只保留實際在開發的東西：

| 位置 | 說明 |
|---|---|
| **`PyPoly/`** | **實際的遊戲專案**（FastAPI + Socket.IO 後端、Three.js 前端）。啟動方式見 `PyPoly/README.md` |
| `ops/` | 營運工具：ngrok 隧道腳本、Discord 控制 bot |
| `past/` | 已不再維護的早期原型封存，說明見 `past/README.md` |

啟動遊戲（詳細步驟與注意事項見 `PyPoly/README.md`）：

```bash
cd PyPoly
uvicorn main:sio_app --host 0.0.0.0 --port 8000   # 進入點必須是 sio_app
```

> 實際的系統架構、技術選擇、API／Socket.IO 事件、資料庫結構，一律以
> `PyPoly/` 的程式碼與 `PyPoly/changeLog.txt` 為單一事實來源——這裡
> 不重複維護一份架構說明，避免兩邊內容日後各自偏離變得矛盾。詳細的
> 啟動步驟、環境需求、初始化資料庫見 `PyPoly/README.md`。
