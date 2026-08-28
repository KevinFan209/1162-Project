# 用 Docker 跑 PyPoly

給組員的本機開發環境。裝好 Docker Desktop 之後，**不需要**再裝 Python、MySQL、XAMPP，
也不用自己建資料庫或灌題庫——全部自動完成。

---

## 一、只要做一次的準備

安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows 需要 WSL2，安裝程式會引導你開啟）。

老實說：Docker Desktop 本身約 2GB，不算輕。但只裝這一次，之後所有人的環境完全一致——
不必對 Python 版本、不必裝 MySQL、不會因為在錯的目錄啟動而看到 404。

## 二、啟動

在專案根目錄（有 `docker-compose.yml` 的那層）：

```bash
docker compose up -d --build
```

第一次會花幾分鐘下載映像與安裝套件，之後啟動只要幾秒。

然後開瀏覽器：

**http://localhost:8000/static/login.html**

管理員帳號 `admin` / 密碼 `123`（自動建立）。

## 三、三個一定要知道的地雷

**1. 網址不能只打 `localhost:8000`**

專案沒有根路徑的路由，直接開會看到 `{"detail":"Not Found"}`。
一定要帶 `/static/login.html`。

**2. 一定要用 `localhost`，不能用區網 IP**

瀏覽器只在 HTTPS 或 localhost 底下才給相機權限。
用 `http://192.168.x.x:8000` 的話，手勢辨識會完全拿不到畫面。

**3. 改 `models.py` 新增欄位後要跑遷移**

```bash
docker compose exec app python db_migrate.py
```

SQLAlchemy 的 `create_all()` 只會建**不存在的資料表**，不會替既有資料表補**欄位**。
少了這步，之後每次查詢都會撞上 `Unknown column`。

## 四、日常操作

| 目的 | 指令 |
|---|---|
| 啟動 | `docker compose up -d` |
| 看後端日誌 | `docker compose logs -f app` |
| 停止（資料保留） | `docker compose down` |
| 停止並清空資料庫 | `docker compose down -v` |
| 進容器裡下指令 | `docker compose exec app bash` |
| 改了 requirements.txt | `docker compose up -d --build` |

**改程式碼不用重建**：`PyPoly/` 是掛載進容器的，用你熟悉的編輯器改檔案存檔，
後端會自動重啟（`.py`），前端重整瀏覽器就好（`.html` / `.js`）。

## 五、資料庫

- 你的資料庫是**完全獨立的一份**，跑在 `db` 容器裡，不會影響到別人。
- 首次啟動自動灌入題庫、冒險格情境、admin 帳號。
- 資料存在 Docker 的 named volume，`docker compose down` 不會消失。
- 想砍掉重練：`docker compose down -v` 之後再 `up`，會重新 seed。
- 想用 HeidiSQL / DBeaver 連進去看資料：把 `docker-compose.yml` 裡 `db` 服務的
  `ports` 兩行註解拿掉，重啟後連 `localhost:3307`，帳號 `root` 密碼 `pypoly`。

## 六、有哪些功能在容器裡是關掉的

以下需要金鑰，容器刻意不提供（避免把金鑰散出去），**不影響遊戲主流程**：

- **忘記密碼寄 OTP**：需要 Gmail 應用程式密碼
- **空氣品質加成**：需要環境部 API 金鑰，未提供時冒險格會用保底值

要啟用的話，在 `docker-compose.yml` 的 `app.environment` 底下補上
`SENDER_EMAIL` / `SENDER_PASSWORD` / `MOENV_API_KEY`。

## 七、遇到問題

**`docker compose up` 卡在等資料庫**
MariaDB 第一次初始化要十幾秒，正常。超過 60 秒才會報錯。

**改了 .py 但沒有自動重啟**
compose 已經設了 `WATCHFILES_FORCE_POLLING=true`（Windows 的檔案變更事件傳不進
Linux 容器，少了這行 `--reload` 會安靜地沒反應）。若仍無效，`docker compose restart app`。

**想確認後端到底有沒有起來**
```bash
docker compose logs app | tail -20
```
看到 `🚀 啟動 PyPoly (main:sio_app)` 就是正常了。
