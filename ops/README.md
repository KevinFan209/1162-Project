# ops —— PyPoly 遠端協作測試環境

這個目錄放的是**營運工具**，不是遊戲程式本身。遊戲程式在 `../PyPoly/`。

存在的理由：PyPoly 是雙人即時連線遊戲，但團隊四個人不在同一個區網，
沒辦法一起測可玩性。這裡的腳本會把本機伺服器透過 Cloudflare 隧道
開成一個公開的 HTTPS 網址，讓組員從任何地方連進來一起玩。

---

## 給主持測試的人（目前是 Kevin 的機器）

### 一次性準備

下載 cloudflared 獨立執行檔到 `ops\bin\`（約 52 MB，已被 gitignore，每個人各自下載）：

```powershell
New-Item -ItemType Directory -Force -Path .\ops\bin | Out-Null
Invoke-WebRequest -UseBasicParsing -OutFile .\ops\bin\cloudflared.exe `
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
```

> 不建議用 `winget install --id Cloudflare.cloudflared` —— 實測在非互動的終端機下會卡住不動。

另外確認 `..\PyPoly\.env` 存在（沒有的話依 `.env.example` 建立，填入隨機 `SECRET_KEY`）。
XAMPP 的 MySQL 也要先開起來。

### 每次要揪團測試時

```powershell
.\ops\scripts\dev-tunnel.ps1
```

腳本會依序：啟動 uvicorn（`main:sio_app`，在 `PyPoly/` 目錄下）→ 建立 Cloudflare 隧道
→ 印出網址並複製到剪貼簿。把網址貼到 Discord 給組員即可。

按 `Ctrl+C` 會一併關掉伺服器與隧道。

> **網址每次重新啟動都會變**，這是 Cloudflare Quick Tunnel 的特性。
> 之後做了 Discord bot，就會由 bot 自動把新網址貼到頻道。

---

## 給組員

主持人會在 Discord 貼一個像這樣的網址：

```
https://xxxx-xxxx-xxxx.trycloudflare.com/static/login.html
```

點開就能玩，**不需要安裝任何東西**。

### 幾個要知道的事

- **一定要用主持人給的 HTTPS 網址**。之前用區網 IP（`http://192.168.x.x:8000`）時，
  瀏覽器會因為不是安全來源而**完全禁止使用相機** —— 手勢和開合跳辨識都無法啟動。
  換成 HTTPS 之後這些功能才第一次能真的測到。
- 第一次進去瀏覽器會問**相機權限，請按允許**。
- 建議用 Chrome 或 Edge。
- 網址失效代表主持人把伺服器關了，在 Discord 問一下即可。

### 目前已知、還沒修的問題（測到時不用回報）

| 現象 | 原因 |
|---|---|
| 有人中途關掉分頁，另一人就卡住不動 | 後端沒有斷線處理，還在等對方 |
| 決定先後手時對方離線 → 永遠停在等待畫面 | 同上，要兩人都擲骰才會繼續 |
| 結算報表的「開合跳次數」永遠是 0 | 前端沒把這個數字送給後端 |
| 選了「25 回合」「30 回合」實際只打 20 回合 | 選單的值填錯 |
| 個人資料頁的修改功能沒反應 | 後端缺對應 API |

**其他任何問題都歡迎回報**，回報時請附上：做了什麼動作、預期什麼、實際發生什麼，
以及瀏覽器 F12 主控台的紅色錯誤訊息截圖。

---

## 之後要加的東西（尚未實作）

Discord bot，讓組員自己用 `/start` 開伺服器、`/url` 查網址，不必每次都等主持人。
設計已完成，見專案計劃書。核心原則是**執行路徑與 LLM 路徑完全隔離**：
slash 指令走固定白名單動作，接 llama.cpp 的問答功能只回文字、沒有任何執行權限。
