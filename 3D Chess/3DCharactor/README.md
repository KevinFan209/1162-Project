# 3DCharactor — 資料夾說明

本資料夾包含 PyPoly 3D 大富翁專案中，角色自定義功能的所有開發成果。

---

## 資料夾結構

```
3DCharactor/
  my-work/             目前的完整開發版本
  full-integration/    完整整合包（含所有改動）
  clean-integration/   乾淨整合包（僅角色自定義功能）
```

---

## my-work

目前在本機上的完整工作版本，包含開發過程中的所有改動：角色自定義、資料庫從 MySQL 改為 SQLite、API URL 動態化、離房邏輯、OTP 寄信等雜項修正。

若需要在本機執行或測試專案，請使用此資料夾。

---

## full-integration

在原版專案基礎上，**所有改動**的交付包。

包含內容：
- `static/character.html` — 3D 角色自定義頁面
- `static/pypoly_char.js` — 供 game.html 引入的角色渲染模組
- `static/models/` — Steve GLB 模型與貼圖
- `static/game.html` — 加入完整角色系統、離房邏輯、API URL 動態化
- `static/lobby.html` — 加入角色自定義選單連結、API URL 動態化
- `static/index.html` — 根路徑重導向頁
- `templates/board_preview.html` — 3D 棋盤預覽頁
- `database.py` — 資料庫從 MySQL 改為 SQLite
- `demo_server.py` / `demo.bat` / `demo_requirements.txt` — 獨立展示伺服器
- `整合說明.md` — 整合步驟說明
- `個人完整修改紀錄.md` — 完整改動紀錄

---

## clean-integration

在原版專案基礎上，**僅包含角色自定義功能**的交付包，不含任何無關改動。
若整合者希望自行處理其餘修改，建議使用此版本。

包含內容：
- `static/character.html` — 3D 角色自定義頁面（全新）
- `static/pypoly_char.js` — 角色渲染模組（全新）
- `static/models/minecraft_-_steve.glb` — Steve 3D 模型（全新）
- `static/models/steve_tex_0.png` — 模型貼圖（全新）
- `static/game.html` — 原版 + 僅加入角色系統（其餘未動）
- `static/lobby.html` — 原版 + 僅加入角色自定義選單連結
- `main.py` — 原版 + 僅加入一個 Socket.IO 事件（`char_data_sync`）
- `整合說明.md` — 逐步整合說明

詳細整合步驟請參閱 `clean-integration/整合說明.md`。
