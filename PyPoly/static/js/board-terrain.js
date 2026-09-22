// =============================================================
// 格子外觀：地形貼圖與裝飾物
//
// 設計原則（與 past/BoardEditor 的做法不同，刻意分開）：
//   · 冒險格 → 依「情境地點所在的鄉鎮」決定地形，讓走一圈像繞南投一圈
//   · 功能格 → 不套地形，改放對應的建築（見 board-props.js）
//
// 地形貼圖是程序化產生的 canvas，沒有外部圖檔相依。
// 移植自 past/BoardEditor/game.html 的 createTileTexture，
// 並把南投沒有的地貌（沙漠、熔岩）換成水岸與雪地。
// =============================================================

// ── 鄉鎮 → 地形 ──────────────────────────────────────────────
// 未列出的鄉鎮會落到 grass。map_config 現在會回傳 township
// （main.py 的 adventure_tiles，欄位名就叫 township）。
const TOWNSHIP_TERRAIN = {
    // 平地與市鎮
    '南投市': 'grass',  '草屯鎮': 'grass',  '埔里鎮': 'grass',  '集集鎮': 'grass',
    // 林區與茶園
    '鹿谷鄉': 'forest', '竹山鎮': 'forest', '名間鄉': 'forest',
    // 山區岩地
    '中寮鄉': 'stone',  '國姓鄉': 'stone',  '信義鄉': 'stone',
    // 水域（日月潭、水庫）
    '魚池鄉': 'water',  '水里鄉': 'water',
    // 高山（合歡山、清境）
    '仁愛鄉': 'snow',
};

// 每種地形的（底色, 紋路色, 邊緣發光色）
const TERRAIN_PALETTE = {
    grass:  ['#7cb342', '#33691e', 0x8bc34a],
    forest: ['#2e7d32', '#1b5e20', 0x43a047],
    stone:  ['#90a4ae', '#455a64', 0x78909c],
    water:  ['#4fc3f7', '#0277bd', 0x29b6f6],
    snow:   ['#eceff1', '#b0bec5', 0xe1f5fe],
    // 功能格用中性鋪面色，重點在上面的建築而不是地面
    facility: ['#d7ccc8', '#8d6e63', 0xffb74d],
    start:    ['#00cdac', '#00897b', 0x00e5b0],
};

/** 依格子資料決定地形代號。 */
function terrainForTile(tile) {
    if (!tile) return 'grass';
    if (tile.type === 'START') return 'start';
    if (tile.type === 'ADVENTURE') {
        const town = tile.data && tile.data.township;
        return TOWNSHIP_TERRAIN[town] || 'grass';
    }
    // SHOP / JAIL / PUNISH / REWARD / BLANK
    return 'facility';
}

// 貼圖只跟地形有關，同地形的格子共用一張，避免產生 26 張 canvas
const _terrainTextureCache = {};

/**
 * 產生地形貼圖（128×128 的程序化 canvas）。
 * 不讀外部圖檔，所以不會有載入失敗或跨網域的問題。
 */
function createTerrainTexture(terrain) {
    if (_terrainTextureCache[terrain]) return _terrainTextureCache[terrain];

    const SZ = 128;
    const c = document.createElement('canvas');
    c.width = c.height = SZ;
    const ctx = c.getContext('2d');
    const pal = TERRAIN_PALETTE[terrain] || TERRAIN_PALETTE.grass;
    const light = pal[0], dark = pal[1];

    ctx.fillStyle = light;
    ctx.fillRect(0, 0, SZ, SZ);

    if (terrain === 'grass') {
        // 短草叢
        ctx.fillStyle = dark;
        for (let r = 0; r < 12; r++) {
            ctx.fillRect(8 + (r % 4) * 30, 10 + Math.floor(r / 4) * 30, 5, 12);
        }
    } else if (terrain === 'forest') {
        // 較密的深色葉叢
        ctx.fillStyle = dark;
        for (let r = 0; r < 20; r++) {
            const x = 6 + (r % 5) * 25;
            const y = 8 + Math.floor(r / 5) * 30;
            ctx.beginPath();
            ctx.arc(x + 6, y + 6, 7, 0, Math.PI * 2);
            ctx.fill();
        }
    } else if (terrain === 'stone') {
        // 交錯的石磚
        ctx.strokeStyle = dark;
        ctx.lineWidth = 3;
        for (let row = 0; row < 4; row++) {
            const xoff = (row % 2) * 32;
            for (let col = 0; col < 3; col++) {
                ctx.strokeRect(xoff + col * 64 - 28, row * 32 + 5, 56, 24);
            }
        }
    } else if (terrain === 'water') {
        // 波紋
        ctx.strokeStyle = dark;
        ctx.lineWidth = 3;
        for (let row = 0; row < 5; row++) {
            ctx.beginPath();
            for (let x = 0; x <= SZ; x += 8) {
                const y = row * 26 + 12 + Math.sin(x * 0.12 + row) * 6;
                if (x === 0) { ctx.moveTo(x, y); } else { ctx.lineTo(x, y); }
            }
            ctx.stroke();
        }
    } else if (terrain === 'snow') {
        // 雪花結晶
        ctx.strokeStyle = dark;
        ctx.lineWidth = 2;
        const flakes = [[38, 40], [92, 52], [60, 96]];
        flakes.forEach(function (f) {
            for (let a = 0; a < 6; a++) {
                const ang = (a * Math.PI) / 3;
                ctx.beginPath();
                ctx.moveTo(f[0], f[1]);
                ctx.lineTo(f[0] + Math.cos(ang) * 16, f[1] + Math.sin(ang) * 16);
                ctx.stroke();
            }
        });
    } else if (terrain === 'facility') {
        // 鋪面磚，與自然地形明顯區隔
        ctx.strokeStyle = dark;
        ctx.lineWidth = 2;
        for (let i = 0; i <= SZ; i += 32) {
            ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, SZ); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(SZ, i); ctx.stroke();
        }
    } else if (terrain === 'start') {
        ctx.fillStyle = dark;
        ctx.font = 'bold 52px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('GO', SZ / 2, SZ / 2 + 2);
    }

    // 外框讓格子邊界清楚
    ctx.strokeStyle = 'rgba(0,0,0,0.30)';
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, SZ - 4, SZ - 4);

    const tex = new THREE.CanvasTexture(c);
    _terrainTextureCache[terrain] = tex;
    return tex;
}

/**
 * 格子邊緣的發光線框。
 * ⚠️ 回傳物件供呼叫端掛到格子底下（tile.add），不要直接加進 scene——
 *    setBoardVisibility() 只切換 allTileMeshes，直接加到 scene 的東西
 *    在進入冒險全景時不會被隱藏，會浮在天空盒上。
 */
function createTileEdgeGlow(terrain) {
    const pal = TERRAIN_PALETTE[terrain] || TERRAIN_PALETTE.grass;
    return new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(BOARD_TILE_SIZE, BOARD_TILE_THICK, BOARD_TILE_SIZE)),
        new THREE.LineBasicMaterial({ color: pal[2] })
    );
}

/**
 * 依地形產生裝飾物（樹、岩石、冰晶…），回傳一個 Group。
 * 座標是相對於格子中心的區域座標，呼叫端直接 tile.add() 即可。
 *
 * 移植自 past/BoardEditor/game.html 的 addTileProps，但改為回傳 Group
 * 而非往 scene 塞——理由同 createTileEdgeGlow 的說明。
 * 尺寸也依現行的 5×5 格子放大（原版是 3.5×3.5）。
 */
function createTerrainProps(terrain) {
    const g = new THREE.Group();
    const top = BOARD_TILE_THICK / 2;   // 格子頂面（區域座標）

    function put(mesh, x, y, z) {
        mesh.position.set(x, y, z);
        g.add(mesh);
    }

    if (terrain === 'grass' || terrain === 'forest') {
        const dense = terrain === 'forest';
        const trunkMat = new THREE.MeshStandardMaterial({ color: 0x5d4037, roughness: 1 });
        const crownMat = new THREE.MeshStandardMaterial({
            color: dense ? 0x1b5e20 : 0x2e7d32, roughness: 0.9,
        });
        const spots = dense
            ? [[-1.4, -1.2], [1.2, 1.1], [1.3, -1.3], [-1.1, 1.4]]
            : [[-1.4, -1.2], [1.2, 1.1]];
        spots.forEach(function (p) {
            const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.2, 0.9, 6), trunkMat);
            put(trunk, p[0], top + 0.45, p[1]);
            const crown = new THREE.Mesh(
                dense ? new THREE.ConeGeometry(0.62, 1.3, 7)
                      : new THREE.SphereGeometry(0.6, 7, 5),
                crownMat);
            put(crown, p[0], top + (dense ? 1.45 : 1.2), p[1]);
        });
    } else if (terrain === 'stone') {
        const mat = new THREE.MeshStandardMaterial({ color: 0x78909c, roughness: 1, flatShading: true });
        const rots = [[0.6, 0.8, 0.4], [0.3, 2.1, 0.7], [1.1, 1.4, 0.2]];
        const rocks = [[1.2, -0.9, 0.40], [-1.1, 0.9, 0.34], [0.2, 1.3, 0.28]];
        rocks.forEach(function (r, i) {
            const rock = new THREE.Mesh(new THREE.OctahedronGeometry(r[2], 0), mat);
            rock.rotation.set(rots[i][0], rots[i][1], rots[i][2]);
            put(rock, r[0], top + r[2] * 0.6, r[1]);
        });
    } else if (terrain === 'water') {
        // 蘆葦與淺灘的石頭，暗示是水岸而不是水面本身
        const reedMat = new THREE.MeshStandardMaterial({ color: 0x689f38, roughness: 0.9 });
        [[-1.3, -1.0], [-1.0, -1.4], [1.3, 1.1]].forEach(function (p) {
            const reed = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 1.1, 5), reedMat);
            put(reed, p[0], top + 0.55, p[1]);
        });
        const stoneMat = new THREE.MeshStandardMaterial({ color: 0x90a4ae, roughness: 1, flatShading: true });
        put(new THREE.Mesh(new THREE.OctahedronGeometry(0.3, 0), stoneMat), 1.0, top + 0.18, -1.2);
    } else if (terrain === 'snow') {
        const iceMat = new THREE.MeshStandardMaterial({
            color: 0xb3e5fc, transparent: true, opacity: 0.85, roughness: 0.1, metalness: 0.3,
        });
        [[-1.0, -0.8, 1.2], [0.9, 1.0, 0.9], [0.1, -1.3, 1.4]].forEach(function (p) {
            const crystal = new THREE.Mesh(new THREE.ConeGeometry(0.22, p[2], 4), iceMat);
            put(crystal, p[0], top + p[2] / 2, p[1]);
        });
    }
    // facility / start 不加地形裝飾，改由 board-props.js 的建築負責

    return g;
}
