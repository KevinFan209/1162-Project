# 角色自定義模組 — 整合說明

本整合包包含角色自定義功能所需的全部檔案，以及對現有檔案的最小改動說明。
整合包**不含**資料庫切換、IP 動態化等無關改動。

---

## 整合包內容

```
乾淨版整合包/
  main.py                         後端主程式（原版 + char_data_sync 事件）
  static/
    character.html                角色自定義頁面（全新，直接複製）
    beerich_char.js                角色渲染模組（全新，直接複製）
    game.html                     遊戲頁面（原版 + 角色系統程式碼）
    lobby.html                    大廳頁面（原版 + 角色自定義選單連結）
    models/
      minecraft_-_steve.glb       Steve 3D 模型（二進位，直接複製）
      steve_tex_0.png             模型預設貼圖（直接複製）
```

---

## 整合步驟

### Step 1 — 複製全新檔案

以下檔案為全新新增，直接複製到你們專案的對應路徑即可：

| 來源（整合包） | 目的地（你們的專案） |
|--------------|-------------------|
| `static/character.html` | `static/character.html` |
| `static/beerich_char.js` | `static/beerich_char.js` |
| `static/models/minecraft_-_steve.glb` | `static/models/minecraft_-_steve.glb` |
| `static/models/steve_tex_0.png` | `static/models/steve_tex_0.png` |

---

### Step 2 — 修改 `static/game.html`

> **選項 A（建議）：直接替換**
> 以整合包的 `static/game.html` 取代你們現有的版本。
> 此版本等於原版加上角色系統，其餘程式碼完全未動。

> **選項 B：手動加入**
> 若你們已對 game.html 有其他修改，請依下方說明手動加入三處改動。

#### 2-1. 引入模組腳本

在 `<head>` 裡 GLTFLoader 的 `<script>` 之後加入：

```html
<script src="beerich_char.js"></script>
```

#### 2-2. 加入角色系統程式碼

在 `<script>` 區塊中加入以下函式與常數（建議放在 `loadPlayerModels` 函式附近）：

```js
const pendingCharData = {};

function makeDummyTexture() {
    const c = document.createElement('canvas');
    c.width = c.height = 4;
    return new THREE.CanvasTexture(c);
}

function loadFaceTextureIntoMat(mat) {
    const b64 = localStorage.getItem('beerich_char_face');
    if (!b64) return;
    const img = new Image();
    img.onload = () => {
        const tex = new THREE.Texture(img);
        tex.needsUpdate = true;
        mat.uniforms.uFaceTex.value = tex;
        mat.uniforms.uHasFace.value = 1.0;
    };
    img.src = b64;
}

function applyCharDataToMat(mat, data) {
    if (data.colors) {
        const C = (hex) => {
            const r = parseInt(hex.slice(1,3),16)/255;
            const g = parseInt(hex.slice(3,5),16)/255;
            const b = parseInt(hex.slice(5,7),16)/255;
            return new THREE.Color(r,g,b);
        };
        mat.uniforms.uHeadColor.value  = C(data.colors.head);
        mat.uniforms.uBodyColor.value  = C(data.colors.body);
        mat.uniforms.uArmColor.value   = C(data.colors.arm);
        mat.uniforms.uLegsColor.value  = C(data.colors.legs);
        mat.uniforms.uFeetColor.value  = C(data.colors.feet);
    }
    if (data.face) {
        const img = new Image();
        img.onload = () => {
            const tex = new THREE.Texture(img);
            tex.needsUpdate = true;
            mat.uniforms.uFaceTex.value = tex;
            mat.uniforms.uHasFace.value = 1.0;
        };
        img.src = data.face;
    }
}

function emitCharData() {
    const colorsRaw = localStorage.getItem('beerich_char_colors');
    const face      = localStorage.getItem('beerich_char_face');
    const colors    = colorsRaw ? JSON.parse(colorsRaw) : null;
    const room      = localStorage.getItem('currentRoom');
    const user      = localStorage.getItem('username');
    if (room) socket.emit('char_data_sync', { room, user, colors, face });
}

const CHAR_VERT = `
    varying vec3 vWorldPos;
    varying vec3 vNormal;
    void main() {
        vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
        vNormal   = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
`;

const CHAR_FRAG = `
    uniform vec3  uHeadColor;
    uniform vec3  uBodyColor;
    uniform vec3  uArmColor;
    uniform vec3  uLegsColor;
    uniform vec3  uFeetColor;
    uniform float uMinY;
    uniform float uMaxY;
    uniform sampler2D uFaceTex;
    uniform float uHasFace;
    uniform float uModelYaw;
    varying vec3  vWorldPos;
    varying vec3  vNormal;

    void main() {
        float t = (vWorldPos.y - uMinY) / (uMaxY - uMinY);
        t = clamp(t, 0.0, 1.0);

        float cosA = cos(-uModelYaw);
        float sinA = sin(-uModelYaw);
        float localX = cosA * vWorldPos.x - sinA * vWorldPos.z;

        bool isArm = abs(localX) > 0.28;
        vec3 col;
        if (isArm) {
            col = uArmColor;
        } else if (t > 0.75) {
            col = uHeadColor;
        } else if (t > 0.375) {
            col = uBodyColor;
        } else if (t > 0.10) {
            col = uLegsColor;
        } else {
            col = uFeetColor;
        }

        if (uHasFace > 0.5 && t > 0.75 && !isArm) {
            vec3 n = normalize(vNormal);
            float cosY = cos(-uModelYaw);
            float sinY = sin(-uModelYaw);
            float nx = cosY * n.x - sinY * n.z;
            float nz = sinY * n.x + cosY * n.z;
            if (nz > 0.4) {
                float u = clamp((nx + 0.5) / 1.0, 0.0, 1.0);
                float v = clamp((t - 0.75) / 0.25, 0.0, 1.0);
                vec4 faceCol = texture2D(uFaceTex, vec2(u, v));
                col = mix(col, faceCol.rgb, faceCol.a);
            }
        }

        gl_FragColor = vec4(col, 1.0);
    }
`;

function loadPlayerModels() {
    if (typeof playerModels === 'undefined') {
        console.warn('[beerich_char] playerModels not found');
        return;
    }
    playerModels.forEach((pm, index) => {
        if (pm.visible === false || (pm.children && pm.children.length === 0)) {
            pm.visible = false;
        }
    });

    const loader = new THREE.GLTFLoader();
    loader.load('models/minecraft_-_steve.glb', (gltf) => {
        const colorsRaw = localStorage.getItem('beerich_char_colors');
        const colors    = colorsRaw ? JSON.parse(colorsRaw) : {
            head: '#f5c18a', arm: '#5cbaee', body: '#4a90d9', legs: '#2c4a8c', feet: '#2c1f14'
        };
        const C = (hex) => {
            const r = parseInt(hex.slice(1,3),16)/255;
            const g = parseInt(hex.slice(3,5),16)/255;
            const b = parseInt(hex.slice(5,7),16)/255;
            return new THREE.Color(r,g,b);
        };

        playerModels.forEach((pm, index) => {
            const clone = gltf.scene.clone(true);

            let minY = Infinity, maxY = -Infinity;
            clone.traverse(c => {
                if (c.isMesh) {
                    c.geometry.computeBoundingBox();
                    const bb = c.geometry.boundingBox;
                    minY = Math.min(minY, bb.min.y);
                    maxY = Math.max(maxY, bb.max.y);
                }
            });

            const mat = new THREE.ShaderMaterial({
                vertexShader: CHAR_VERT,
                fragmentShader: CHAR_FRAG,
                uniforms: {
                    uHeadColor: { value: C(colors.head) },
                    uBodyColor: { value: C(colors.body) },
                    uArmColor:  { value: C(colors.arm)  },
                    uLegsColor: { value: C(colors.legs) },
                    uFeetColor: { value: C(colors.feet) },
                    uMinY:      { value: minY },
                    uMaxY:      { value: maxY },
                    uFaceTex:   { value: makeDummyTexture() },
                    uHasFace:   { value: 0.0 },
                    uModelYaw:  { value: 0.0 }
                }
            });

            clone.traverse(c => { if (c.isMesh) c.material = mat; });

            if (index === 0) loadFaceTextureIntoMat(mat);

            clone.scale.set(1.5, 1.5, 1.5);
            pm.add(clone);
            pm.visible = true;

            if (typeof mapBlocks !== 'undefined') {
                const pos = mapBlocks[index]?.position;
                if (pos) clone.userData.yaw = Math.atan2(pos.x, pos.z);
            }
        });

        emitCharData();
    });
}
```

#### 2-3. 替換 socket 監聽器

找到原本的 `socket.on('char_data_sync', ...)` 並改為：

```js
socket.on('char_data_sync', onCharDataSync);
```

若原版沒有此監聽器，直接加入即可。

---

### Step 3 — 修改 `static/lobby.html`

在側邊選單（`<nav>` 或選單 `<ul>` 裡）加入一行連結：

```html
<a href="character.html" class="menu-item"><span>🎨</span> 角色自定義</a>
```

放在其他選單項目旁邊即可，不限定位置。

---

### Step 4 — 修改 `main.py`

在 Socket.IO 事件區段（其他 `@sio.on(...)` 附近）加入以下 6 行：

```python
@sio.on('char_data_sync')
async def handle_char_data_sync(sid, data):
    room = data.get('room')
    if room:
        await sio.emit('char_data_sync', data, room=room, skip_sid=sid)
```

---

## 資料接口說明

### localStorage（character.html 寫入，game.html 讀取）

| Key | 格式 | 說明 |
|-----|------|------|
| `beerich_char_colors` | JSON `{"head":"#...","arm":"#...","body":"#...","legs":"#...","feet":"#..."}` | 角色各部位顏色 |
| `beerich_char_face` | base64 JPEG data URL | 人臉貼圖（相機擷取） |

### Socket.IO 事件

| 事件名稱 | 方向 | Payload |
|---------|------|---------|
| `char_data_sync` | client → server → 對手 client | `{ room, user, colors, face }` |

玩家進入遊戲時，`loadPlayerModels()` 會自動呼叫 `emitCharData()`，
將顏色與人臉資料透過 Socket.IO 廣播給對手。

---

## `beerich_char.js` 所需的全域變數

`beerich_char.js` 直接使用 `game.html` 現有的全域變數，整合前請確認以下變數存在：

| 變數名稱 | 說明 |
|---------|------|
| `THREE` | Three.js 主物件（r128） |
| `scene` | Three.js 場景物件 |
| `socket` | Socket.IO 連線物件 |
| `playerModels` | 玩家棋子的 Object3D 陣列（index 0 = 自己，index 1 = 對手） |
| `mapBlocks` | 棋盤格子陣列，用於取得初始位置計算模型朝向 |

---

## 影響範圍

- `character.html`：全新獨立頁面，不影響任何現有功能。
- `beerich_char.js`：只在 `game.html` 引入，不影響其他頁面。
- `game.html`：僅新增角色渲染程式碼，其餘邏輯完全未動。
- `lobby.html`：只新增一行選單連結。
- `main.py`：只新增一個 Socket.IO 事件轉發。
