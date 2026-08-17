/**
 * beerich_char.js — BeeRich 角色自定義整合模組
 *
 * 本檔案包含所有「角色自定義 → 棋盤顯示」的相關程式碼。
 * 在 game.html 中引入此檔案後，以下函式即可在全域使用：
 *
 *   loadPlayerModels()      載入所有玩家 3D 角色模型（含自定義外觀）
 *   onCharDataSync(data)    處理對方角色資料的 Socket.IO 回呼
 *
 * 依賴的全域變數（必須在 game.html 中已宣告）：
 *   THREE         — Three.js 主函式庫
 *   scene         — THREE.Scene 場景物件
 *   socket        — Socket.IO socket 實例
 *   playerModels  — {} 物件，供 game.html 其他程式碼存取角色模型
 *   mapBlocks     — [] 陣列，棋盤各格的世界座標
 *
 * localStorage 讀取的 key（由 character.html 寫入）：
 *   beerich_char_colors  — JSON {"head","arm","body","legs","feet"}
 *   beerich_char_face    — base64 JPEG data URL
 *   beerich_game_snapshot — 遊戲快照（game.html 本身也使用）
 *   beerich_active_room   — 房間資訊
 */

// ─────────────────────────────────────────────
//  緩衝：尚未載入模型時，暫存對方傳來的角色資料
// ─────────────────────────────────────────────
const pendingCharData = {};

// ─────────────────────────────────────────────
//  材質輔助函式
// ─────────────────────────────────────────────

function makeDummyTexture() {
    const c = document.createElement('canvas');
    c.width = c.height = 1;
    c.getContext('2d').fillStyle = '#f5c18a';
    c.getContext('2d').fillRect(0, 0, 1, 1);
    return new THREE.CanvasTexture(c);
}

function loadFaceTextureIntoMat(mat) {
    const dataUrl = localStorage.getItem('beerich_char_face');
    if (!dataUrl) return;
    const img = new Image();
    img.onload = () => {
        const fc = document.createElement('canvas');
        fc.width = 512; fc.height = 128;
        fc.getContext('2d').drawImage(img, 0, 0, 512, 128);
        const tex = new THREE.CanvasTexture(fc);
        tex.needsUpdate = true;
        mat.uniforms.faceTex.value = tex;
        mat.uniforms.hasFace.value = 1.0;
        mat.needsUpdate = true;
    };
    img.src = dataUrl;
}

function applyCharDataToMat(mat, data) {
    if (!mat) return;
    if (data.colors) {
        const c = data.colors;
        if (c.head) mat.uniforms.colorHead.value.set(c.head);
        if (c.arm)  mat.uniforms.colorArm.value.set(c.arm);
        if (c.body) mat.uniforms.colorBody.value.set(c.body);
        if (c.legs) mat.uniforms.colorLegs.value.set(c.legs);
        if (c.feet) mat.uniforms.colorFeet.value.set(c.feet);
    }
    if (data.face) {
        const img = new Image();
        img.onload = () => {
            const fc = document.createElement('canvas');
            fc.width = 512; fc.height = 128;
            fc.getContext('2d').drawImage(img, 0, 0, 512, 128);
            const tex = new THREE.CanvasTexture(fc);
            tex.needsUpdate = true;
            mat.uniforms.faceTex.value = tex;
            mat.uniforms.hasFace.value = 1.0;
            mat.needsUpdate = true;
        };
        img.src = data.face;
    }
}

// ─────────────────────────────────────────────
//  廣播自己的角色資料給對手
// ─────────────────────────────────────────────

function emitCharData() {
    const myName = localStorage.getItem('username');
    const activeRoom = JSON.parse(localStorage.getItem('beerich_active_room'));
    const room = activeRoom ? activeRoom.code : localStorage.getItem('room_code');
    if (!room) return;
    const rawColors = localStorage.getItem('beerich_char_colors');
    const colors = rawColors ? JSON.parse(rawColors) : null;
    const face = localStorage.getItem('beerich_char_face') || null;
    socket.emit('char_data_sync', { room, user: myName, colors, face });
}

// ─────────────────────────────────────────────
//  GLSL Shader（分區上色 + 人臉貼圖）
//
//  Y 軸分區（t = 0 腳底, t = 1 頭頂）：
//    t > 0.75            → 頭部（含人臉貼圖區域）
//    t > 0.375           → 上衣
//    t > 0.10            → 褲子
//    t ≤ 0.10            → 鞋子
//  |localX| > armThreshX && 0.245 < t < 0.755 → 手臂
//    t > 0.50            → 袖子顏色（arm）
//    t ≤ 0.50            → 皮膚顏色（head）
//
//  手臂偵測使用模型本地 X（反旋轉 modelYaw），
//  解決 lookAt() 旋轉後世界 X 不等於本地 X 的問題。
// ─────────────────────────────────────────────

const CHAR_VERT = `
    varying vec3 vWorldPos;
    varying vec3 vNorm;
    void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWorldPos = wp.xyz;
        vNorm = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * viewMatrix * wp;
    }
`;

const CHAR_FRAG = `
    uniform vec3      colorHead;
    uniform vec3      colorArm;
    uniform vec3      colorBody;
    uniform vec3      colorLegs;
    uniform vec3      colorFeet;
    uniform float     worldMinY;
    uniform float     worldMaxY;
    uniform float     armThreshX;
    uniform float     modelCenterX;
    uniform float     modelCenterZ;
    uniform float     modelYaw;
    uniform sampler2D faceTex;
    uniform float     hasFace;
    varying vec3      vWorldPos;
    varying vec3      vNorm;

    void main() {
        float t = clamp((vWorldPos.y - worldMinY) / (worldMaxY - worldMinY), 0.0, 1.0);

        float cosA  = cos(-modelYaw);
        float sinA  = sin(-modelYaw);
        float dx    = vWorldPos.x - modelCenterX;
        float dz    = vWorldPos.z - modelCenterZ;
        float localX  = dx * cosA - dz * sinA;
        float localNZ = vNorm.x * sinA + vNorm.z * cosA;

        vec3 base;
        if (abs(localX) > armThreshX && t > 0.245 && t < 0.755) {
            base = (t > 0.50) ? colorArm : colorHead;
        } else {
            if (t > 0.75) {
                base = colorHead;
                if (hasFace > 0.5 && localNZ > 0.3) {
                    float fu = clamp((localX + armThreshX) / (2.0 * armThreshX), 0.0, 1.0);
                    float fv = clamp((t - 0.75) / 0.25, 0.0, 1.0);
                    vec4 fc  = texture2D(faceTex, vec2(fu, fv));
                    base     = fc.rgb;
                }
            }
            else if (t > 0.375) base = colorBody;
            else if (t > 0.10)  base = colorLegs;
            else                base = colorFeet;
        }

        vec3 n   = normalize(vNorm);
        float d  = max(dot(n, normalize(vec3(5.0, 12.0, 8.0))), 0.0);
        float f  = max(dot(n, normalize(vec3(-5.0, 3.0, -5.0))), 0.0) * 0.4;
        float ambient = (hasFace > 0.5 && t > 0.75 && localNZ > 0.3) ? 0.95 : 0.85;
        vec3 lit = base * (ambient + 0.5 * d + 0.15 * f);
        gl_FragColor = vec4(clamp(lit, 0.0, 1.0), 1.0);
    }
`;

// ─────────────────────────────────────────────
//  載入所有玩家 3D 模型
//
//  呼叫時機：棋盤 3D 場景（scene）與 mapBlocks 建立完畢後，
//            與 game.html 原本呼叫 loadPlayerModels() 的位置相同。
// ─────────────────────────────────────────────

function loadPlayerModels() {
    const loader = new THREE.GLTFLoader();
    const gameSnapshot = JSON.parse(localStorage.getItem('beerich_game_snapshot'));
    const players = gameSnapshot.players;
    const myName = localStorage.getItem('username');

    const defaultColors = {
        head: '#f5c18a', arm: '#5cbaee', body: '#4a90d9',
        legs: '#2c4a8c', feet: '#2c1f14'
    };

    players.forEach((playerName, index) => {
        loader.load('models/minecraft_-_steve.glb', (gltf) => {
            const model = gltf.scene;

            // 自動縮放至目標高度
            const TARGET_HEIGHT = 2.5;
            const naturalBox    = new THREE.Box3().setFromObject(model);
            const naturalHeight = naturalBox.max.y - naturalBox.min.y;
            model.scale.setScalar(naturalHeight > 0 ? TARGET_HEIGHT / naturalHeight : 1);

            const box        = new THREE.Box3().setFromObject(model);
            const objMinY    = box.min.y;
            const objMaxY    = box.max.y;
            const charHeight = objMaxY - objMinY;
            const armThreshX = (box.max.x - box.min.x) * 0.25;

            // 自己：從 localStorage 讀取顏色；對手：先用預設，等 char_data_sync 到了再更新
            let colors = { ...defaultColors };
            if (playerName === myName) {
                const raw = localStorage.getItem('beerich_char_colors');
                if (raw) { try { Object.assign(colors, JSON.parse(raw)); } catch(e) {} }
            }

            const mat = new THREE.ShaderMaterial({
                uniforms: {
                    colorHead:    { value: new THREE.Color(colors.head) },
                    colorArm:     { value: new THREE.Color(colors.arm)  },
                    colorBody:    { value: new THREE.Color(colors.body) },
                    colorLegs:    { value: new THREE.Color(colors.legs) },
                    colorFeet:    { value: new THREE.Color(colors.feet) },
                    worldMinY:    { value: objMinY },
                    worldMaxY:    { value: objMaxY },
                    armThreshX:   { value: armThreshX },
                    modelCenterX: { value: 0.0 },
                    modelCenterZ: { value: 0.0 },
                    modelYaw:     { value: 0.0 },
                    faceTex:      { value: makeDummyTexture() },
                    hasFace:      { value: 0.0 }
                },
                vertexShader:   CHAR_VERT,
                fragmentShader: CHAR_FRAG
            });

            model.userData.charShader = mat;
            model.userData.objMinY    = objMinY;
            model.userData.charHeight = charHeight;

            if (playerName === myName) {
                loadFaceTextureIntoMat(mat);
                emitCharData();
            } else if (pendingCharData[playerName]) {
                // 對手資料比模型更早到，從暫存中取出並套用
                applyCharDataToMat(mat, pendingCharData[playerName]);
                delete pendingCharData[playerName];
            }

            model.traverse((child) => {
                if (child.isMesh) {
                    child.material = mat;
                    child.castShadow = true;
                    child.layers.set(0);
                }
            });

            const startPos = mapBlocks[0];
            const offset   = (index === 0) ? 0 : 1.5;
            model.position.set(startPos.x + offset, startPos.y + 0.25 - objMinY + 0.2, startPos.z);

            const nextPos = mapBlocks[1];
            model.lookAt(nextPos.x, model.position.y, nextPos.z);

            scene.add(model);
            playerModels[playerName] = model;
        });
    });
}

// ─────────────────────────────────────────────
//  接收對手廣播的角色資料（Socket.IO 回呼）
//
//  使用方式：
//    socket.on('char_data_sync', onCharDataSync);
// ─────────────────────────────────────────────

function onCharDataSync(data) {
    const myName = localStorage.getItem('username');
    if (data.user === myName) return;
    const model = playerModels[data.user];
    if (model) {
        applyCharDataToMat(model.userData.charShader, data);
    } else {
        // 模型尚未載入完成，先暫存
        pendingCharData[data.user] = data;
    }
}
