# past — 舊版原型封存

這個資料夾放的是**已不再維護的早期原型**，保留下來只為查閱與追溯，
不參與目前的專案運作。實際在開發的東西在上一層的 `PyPoly/` 與 `ops/`。

## 為什麼有這個資料夾

2026-08 小組決議以 `Fan` 分支為主要專案。整併時把散在根目錄的舊原型
集中到這裡，讓根目錄只留下實際在用的東西。

## 內容

| 目錄 | 說明 |
|---|---|
| `UI設計/` | 早期 UI 設計稿與頁面原型 |
| `影像辨識/` | 手勢／姿勢辨識的獨立原型（`game_start.py`、`jumping.py`、`flappy_bird.py` 等）。**目前正式使用的是 `PyPoly/game_start.py`**，兩者已分家 |
| `登出、入UI/` | 早期登入登出頁面，含 PHP 版本與 firebase JWT 函式庫 |
| `3D Chess/` | 3D 角色與棋子的實驗（由早期的 `TestCar` 演進而來） |
| `BoardEditor/` | 棋盤編輯器：2D/3D 視覺化編輯、格子屬性、匯入匯出 JSON。設計格子屬性時仍值得參考 |
| `main-branch/` | 舊 `main` 分支獨有的 93 個檔案（見下） |

## 關於 `main-branch/`

`main` 分支上有 93 個檔案是 `Fan` 分支沒有的——因為 Fan 當初刻意刪除或改名過
（例如 `TestCar` 被改名並演進為 `3D Chess`，`新UI設計` 被移除）。
合併 `main` 時 git 尊重了這些刪除，所以那些檔案不會自動回來。
為了不遺失，這裡明確保留一份：

- `TestCar/`（9 檔）— `3D Chess` 的前身，兩者檔案已無重疊
- `新UI設計/`（56 檔）— 後來被廢棄的 UI 改版
- `UI設計/page/`（28 檔）— main 上比 Fan 多出的頁面

其餘 62 個檔案 main 與 Fan 相同，已存在於上面各目錄，未重複放置。

> 這些檔案在 git 歷史中永久保存，即使日後刪除本資料夾也能從
> `origin/main`（合併前為 `e36f7ab`）取回。

## 環境部 AQI 功能

`origin/vamos` 分支的 `990e880` 實作了環境部空氣品質 API 串接。
該 commit 基於舊的目錄結構（`main.py` 在根目錄），未直接合併，
而是把邏輯移植到 `PyPoly/air_quality.py` 並接進既有的
`get_adventure_analysis()`。原始版本仍可在 `origin/vamos` 分支查閱。
