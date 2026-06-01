# 115-05-29 更新內容

## 新增檔案

### board-editor.html — 棋盤編輯器
視覺化棋盤設計工具，支援以下功能：
- **2D 編輯**：在畫布上拖曳格子調整位置，並可啟用格線吸附
- **3D 預覽**：切換至 Three.js 3D 預覽，支援旋轉、縮放、平移
- **格子屬性編輯**：可調整格子的座標、高度、大小、類型與標籤文字
- **匯入 / 匯出 JSON**：將棋盤設定儲存為 JSON 或從檔案載入
- **套用到遊戲**：將棋盤設定寫入 `localStorage`，供 `game.html` 讀取使用
![image](https://github.com/KevinFan209/1162-Project/blob/Fan/115-05-29/img/board_editor_2D.png)
![image](https://github.com/KevinFan209/1162-Project/blob/Fan/115-05-29/img/board_editor_3D.png)