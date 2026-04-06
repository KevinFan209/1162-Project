# 1162資管系專題-PyPoly(暫定)
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
## 系統概述
本專題旨在開發一套結合遊戲化學習與影像辨識技術的Python程式語言教育系統。透過大富翁（Monopoly）遊戲形式，讓學習者在遊戲過程中透過實體互動（擲骰子、手勢辨識）與程式題目作答，達到寓教於樂的學習效果。
## 目標
- 提供互動式的Python程式語言學習環境
- 透過影像辨識技術增加遊戲互動性
- 採用金錢累積制遊戲模式，提升學習動機
- 支援線上/線下雙模式遊玩
- 提供完整的後台管理系統
- 目標客群為資訊管理相關科系學生、對程式設計有興趣者、以及相關教育機構
## 系統架構
本系統採用三層式架構（Three-Tier Architecture），分為：
- 表示層（Presentation Layer）：Web前端介面
- 業務邏輯層（Business Logic Layer）：遊戲邏輯與影像辨識
- 資料層（Data Layer）：資料庫與檔案儲存
  
|層級|技術|功能說明|
|---|---|---|
|前端展示層|HTML/CSS/JavaScript|遊戲介面、使用者互動|
|影像辨識層|Python + OpenCV|手勢辨識、骰子偵測|
|遊戲邏輯層|JavaScript/Node.js|遊戲規則、題目判斷|
|通訊層|WebSocket/UDP|前後端即時通訊|
|資料儲存層|MySQL/PostgreSQL|使用者資料、題目儲存|
## 使用技術
**前端**
|技術|用途|選擇理由|
|---|---|---|
|HTML5|網頁結構|跨平台支援、語義化標籤|
|CSS|樣式設計|響應式設計、動畫效果|
|JavaScript|互動邏輯|即時互動、遊戲邏輯處理|
|WebSocket|即時通訊|低延遲雙向通訊|

**後端**
|技術|用途|選擇理由|
|---|---|---|
|Python|影像辨識|OpenCV支援度高、開發快速|
|OpenCV|影像處理|ArUco辨識、手勢偵測|
|Node.js|伺服器端|前後端統一語言、高效能|
|Express.js|API框架|輕量級、易於擴展|

**資料庫**
|技術|用途|選擇理由|
|---|---|---|
|MySQL|關聯式資料庫|成熟穩定、社群支援廣|
|Redis|快取資料庫	提升即時遊戲效能|



## 模組設計
### 客戶端模組
- 登入與大廳模組：使用者註冊、登入、遊戲大廳  
- 主遊戲棋盤模組：遊戲地圖、玩家移動、事件觸發  
- 互動任務模組：程式題目顯示、作答介面、即時回饋  
- 遊戲結算模組：分數計算、排名顯示、歷史記錄  

### 伺服器端模組
- 使用者管理模組：帳號驗證、權限控管  
- 遊戲邏輯模組：遊戲規則、回合管理、金錢計算  
- 題目管理模組：題庫維護、難度分級、自動評分  
- 影像辨識模組：手勢辨識、骰子偵測、ArUco標記  

### 後台管理模組
- 題目管理系統（Question CMS）  
- 影像辨識偵錯頁（Vision Debugger）  
- 遊戲數據監控（Game Analytics）  
- 玩家帳號管理系統（User Management）  

## 資料庫設計
### 使用者表（users）
|欄位名稱|資料型態|說明|
|---|---|---|
|user_id|INT (PK)|使用者唯一識別碼|
|username|VARCHAR(50)|使用者名稱|
|password_hash|VARCHAR(255)|密碼雜湊值|
|email|VARCHAR(100)|電子郵件|
|created_at|DATETIME|建立時間|
|last_login|DATETIME|最後登入時間|

### 遊戲記錄表（game_records）
|欄位名稱|資料型態|說明|
|---|---|---|
|game_id|INT (PK)|遊戲唯一識別碼|
|user_id|INT (FK)|使用者識別碼|
|score|INT|遊戲分數|
|money|INT|遊戲金錢|
|rounds|INT|遊戲回合數|
|start_time|DATETIME|開始時間|
|end_time|DATETIME|結束時間|

### 題目表（questions）
|欄位名稱|資料型態|說明|
|---|---|---|
|question_id|INT (PK)|題目唯一識別碼|
|category|VARCHAR(50)|題目類別|
|difficulty|INT|難度等級（1-5）|
|content|TEXT|題目內容|
|answer|TEXT|正確答案|
|explanation|TEXT|題目解析|

## API 設計
### RESTful API
|方法|路徑|說明|
|---|---|---|
|POST|/api/auth/login|使用者登入|
|POST|/api/auth/register|使用者註冊|
|GET|/api/game/:id|取得遊戲資訊|
|POST|/api/game/start|開始新遊戲|
|POST|/api/game/move|玩家移動|
|GET|/api/questions/random|取得隨機題目|
|POST|/api/answers/submit|提交答案|
|GET|/api/leaderboard|排行榜|

### WebSocket 事件
|事件|方向|說明|
|---|---|---|
|dice_roll|Client → Server|骰子結果|
|player_move|Server → Client|玩家移動|
|question_show|Server → Client|顯示題目|
|answer_result|Server → Client|答題結果|
|game_state|Server → Client|狀態更新|

## UI/UX 設計
- 登入與大廳頁  
- 主遊戲棋盤頁  
- 任務作答視窗  
- 遊戲結算頁  

## 安全性
- JWT 身份驗證  
- bcrypt 密碼加密  
- HTTPS 通訊  
- 防 SQL Injection / XSS  

## 部署
**開發環境**
- VS Code  
- Node.js  
- Python + OpenCV  
- Git + GitHub  

**生產環境**
- Nginx  
- Node.js (PM2)  
- MySQL  
- AWS S3 / MinIO  
- CloudFlare  

## 開發時程
|階段|時間|內容|
|---|---|---|
|需求分析|3/4 - 3/9|需求確認|
|系統設計|3/9 - 3/15|架構/UI|
|前後端開發|3/15 - 4/15|功能實作|
|影像辨識|3/20 - 4/20|辨識模組|
|整合測試|4/15 - 4/30|測試|
|部署|5/1 - 5/7|上線|