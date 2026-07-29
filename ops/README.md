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

---

## Discord bot（讓組員自己開伺服器）

不必每次都等主持人開機器，組員在 Discord 打 `/start` 就能開，`/url` 查網址。

### 指令

| 指令 | 行為 |
|---|---|
| `/start` | 啟動伺服器 + 建立隧道，回覆可直接點的遊戲網址 |
| `/restart` | 重啟伺服器與隧道，回覆**新的**網址 |
| `/url` | 只查目前網址，不改變任何狀態 |
| `/status` | 伺服器是否執行中、由誰啟動、房間內玩家數、目前網址 |
| `/stop` | 關掉隧道與伺服器 |

五個指令**都不接受任何自由文字參數**。

> `/restart` 之後網址一定會變（Quick Tunnel 特性），bot 會把新網址貼出來，
> 請組員以最新一則為準。若伺服器不是 bot 啟動的，`/restart` 會明確拒絕而
> 不會去關別人的行程。

### 一次性設定

1. 到 https://discord.com/developers/applications → **New Application**
2. 左側 **Bot** → **Reset Token** → 複製 token
3. 左側 **OAuth2 → URL Generator**：
   - Scopes 勾 `bot` 和 `applications.commands`
   - Bot Permissions 勾 `Send Messages`、`Embed Links`
   - 用產生的網址把 bot 邀進你們的伺服器
4. 在 Discord 設定裡開啟「進階 → 開發者模式」，對伺服器按右鍵複製伺服器 ID
5. 建立設定檔：

```powershell
Copy-Item .\ops\.env.example .\ops\.env
```

編輯 `ops\.env`，填入 `DISCORD_TOKEN` 與 `GUILD_ID`。

6. 安裝相依套件：

```powershell
python -m pip install -r .\ops\requirements.txt
```

### 啟動 bot

```powershell
cd ops
python bot.py
```

bot 必須跑在**裝有 MySQL 的那台機器**上（遊戲伺服器與資料庫綁在一起）。
它是主動對外連 Discord，**不需要開放任何對內的連接埠**。

關掉 bot（Ctrl+C）時會一併收掉它啟動的伺服器與隧道。

### 設計說明

**執行路徑與 LLM 路徑完全隔離。** slash 指令只能觸發四個寫死的動作，
`services/` 裡的子行程指令是固定字串陣列、不經過 shell、不接受任何來自 Discord
的字串拼接。因此即使頻道內所有人都能使用，能觸發的行為仍侷限在那四件事。

**權限取捨**：目前設定為頻道內所有人皆可使用，所以隧道網址等同於存取憑證。
請把該頻道設為私有，不要邀請組員以外的人。

### 檔案結構

```
ops/
├─ bot.py                     進入點：載入 cog、同步 slash commands
├─ config.py                  集中讀取 .env
├─ requirements.txt
├─ .env.example
├─ cogs/ops_cog.py            /start /stop /status /url
├─ services/
│  ├─ server_manager.py       uvicorn 子行程（固定指令）
│  └─ tunnel_manager.py       cloudflared 子行程 + 網址解析
├─ scripts/dev-tunnel.ps1     不透過 bot 的手動啟動方式
├─ bin/                       cloudflared.exe（gitignore）
└─ logs/                      子行程記錄（gitignore）
```

### 尚未實作

llama.cpp 問答功能（階段三）。屆時 `cogs/ask_cog.py` 只回文字、
不得 import `services/`，也不會有任何 function calling。
