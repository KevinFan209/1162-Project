# 角色自定義模組 — 整合說明

## 整合包內容

```
整合包/
  static/
    character.html      角色自定義頁面（玩家在此調整顏色、貼人臉）
    pypoly_char.js      角色渲染模組（供 game.html 引入）
    models/
      minecraft_-_steve.glb   ← 請從 static/models/ 手動複製此二進位檔
  整合說明.md            本文件
```

> **GLB 模型**：`models/minecraft_-_steve.glb` 是二進位檔，整合包中未附上。
> 請直接從本專案的 `static/models/minecraft_-_steve.glb` 複製到你們的 `static/models/`。

---

## 整合步驟

### Step 1 — 複製檔案

將下列檔案放入你們專案的 `static/` 資料夾：

| 來源 | 目的地 |
|------|--------|
| `整合包/static/character.html` | `static/character.html` |
| `整合包/static/pypoly_char.js` | `static/pypoly_char.js` |
| `static/models/minecraft_-_steve.glb`（原專案） | `static/models/minecraft_-_steve.glb` |

---

### Step 2 — 修改 `game.html`

#### 2-1. 引入模組（加在 `<head>` 的 GLTFLoader `<script>` 之後）

```html
<script src="pypoly_char.js"></script>
```

---

#### 2-2. 移除以下程式碼區塊（已全數移入 `pypoly_char.js`）

搜尋並刪除下列內容（**整段**，含上下空行）：

```
const pendingCharData = {};
```

```
function makeDummyTexture() { ... }
function loadFaceTextureIntoMat(mat) { ... }
function applyCharDataToMat(mat, data) { ... }
function emitCharData() { ... }
```

```
const CHAR_VERT = `...`;
const CHAR_FRAG = `...`;
function loadPlayerModels() { ... }
```

> 若你們的 game.html 完全沒有上述程式碼（例如整合前的乾淨版本），
> 則跳過此步驟，只需執行 2-1 和 2-3 即可。

---

#### 2-3. 修改 socket 監聽器

找到：
```js
socket.on('char_data_sync', (data) => {
    ...
});
```

改為（一行即可）：
```js
socket.on('char_data_sync', onCharDataSync);
```

---

### Step 3 — 修改 `main.py`

在 Socket.IO 事件區段加入以下轉發邏輯
（建議放在其他 `@sio.on` 事件附近）：

```python
@sio.on('char_data_sync')
async def handle_char_data_sync(sid, data):
    room = data.get('room')
    if room:
        await sio.emit('char_data_sync', data, room=room, skip_sid=sid)
```

---

## 資料接口說明

### character.html 寫入 → game.html 讀取

| localStorage key | 格式 | 說明 |
|-----------------|------|------|
| `pypoly_char_colors` | JSON `{"head":"#...","arm":"#...","body":"#...","legs":"#...","feet":"#..."}` | 角色各部位顏色 |
| `pypoly_char_face` | base64 JPEG data URL | 人臉貼圖（相機擷取） |

### Socket.IO 事件

| 事件名稱 | 方向 | Payload 格式 |
|---------|------|-------------|
| `char_data_sync` | client → server → 對手 client | `{ room, user, colors, face }` |

玩家進入遊戲時，`loadPlayerModels()` 會自動呼叫 `emitCharData()`，
將自己的顏色與人臉資料透過 socket 廣播給對手。

---

## 對其他頁面的影響

- `character.html` 為獨立頁面，不影響其他任何頁面。
- `pypoly_char.js` 只在 `game.html` 引入，不影響其他頁面。
- 兩者之間透過 `localStorage` 傳遞資料，無共用狀態。
- 大廳頁面加一個「角色自定義」連結指向 `character.html` 即可
  （lobby.html 已有 `<a href="character.html">` 可直接使用）。
