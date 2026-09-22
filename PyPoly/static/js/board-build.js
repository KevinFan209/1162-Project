// =============================================================
// 棋盤組裝
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/game_board.html
// 要用同一份程式碼——複製一份的話，日後改棋盤就得記得改兩處，
// 遲早變成「預覽好看但遊戲裡不是那樣」。
//
// 與 game.html 裡的原版唯一的差別：原本直接讀 scene / allTileMeshes /
// mapBlocks / gameMap 這些全域變數，現在改成接參數，預覽頁才用得了。
// 行為完全相同。
//
// 相依：board-layout.js（版面座標與高度）
//       board-terrain.js（地形貼圖與裝飾）
//       board-props.js（功能格建築）
// =============================================================

// 裝飾物統一用這個名字，重新套用外觀時才知道哪些該清掉
// （支柱與連接橋另有名字，屬於結構的一部分，不隨外觀重建）
const BOARD_DECOR_NAME = "board_decor";

// 棋盤形狀的視覺尺度。
//
// ⚠️ 這個數字必須跟 board_geo.py 的 BOARD_SHAPE_RADIUS 保持一致——
//    Python（算座標）跟 JS（算地面/圍牆多大才蓋得過棋盤）是兩個獨立
//    的執行環境沒辦法共用同一個常數，只能各自定義、手動同步。以後要
//    調棋盤大小，這裡跟 board_geo.py 要一起改。
//
// GROUND_SIZE 用「無限符號（∞）在 x 方向的直徑」（BOARD_SHAPE_RADIUS
// *1.4*2）當基準，比圓形（直徑 2R）、方形/六邊形（外接圓直徑 2R）都
// 大，才能保證不管這局抽到哪個形狀，地面/圍牆都夠大蓋過整個棋盤。
const BOARD_SHAPE_RADIUS = 24.0;
const BOARD_MAX_EXTENT = BOARD_SHAPE_RADIUS * 1.4 * 2;
const GROUND_SIZE = BOARD_MAX_EXTENT * 3;
const GROUND_COLOR = 0x8fbc8f;
const GROUND_Y = -0.05;

// 陰影盡量薄——用一片沒有厚度的 PlaneGeometry，貼著地面、略高一點點
// （避免跟地面完全同高造成 z-fighting）。
const SHADOW_SCALE = 1.4;          // 陰影比格子本身大一圈，看起來更明顯
const SHADOW_WORLD_Y = GROUND_Y + 0.01;

/**
 * 建立整個 26 格棋盤。
 * @param {THREE.Scene} scene  要加進去的場景
 * @param {Array} gameMap      26 格的資料（可為空，之後再用 applyBoardAppearanceTo 套）
 * @returns {{tiles: THREE.Mesh[], positions: THREE.Vector3[]}}
 */
function buildBoard(scene, gameMap) {
    const tiles = [];
    const positions = [];

    // 🏆 座標與高度優先用 gameMap 帶來的真實地理座標（main.py 的
    //    /game/map_config 依每局實際抽到的地點座標/海拔算出來，每格
    //    都會有 x/y/z）。gameMap 沒有座標資訊時（例如預覽頁傳的假資料）
    //    才退回 board-layout.js 那份寫死的固定形狀，不會讓現有呼叫點
    //    忽然壞掉。
    const hasRealPositions = Array.isArray(gameMap) && gameMap.length === 26 &&
        gameMap.every((t) => t && typeof t.x === "number" &&
                             typeof t.y === "number" && typeof t.z === "number");
    const layout = hasRealPositions
        ? gameMap.map((t) => ({ x: t.x, y: t.y, z: t.z, size: 1 }))
        : BOARD_LAYOUT.tiles;
    const tileGeo = new THREE.BoxGeometry(BOARD_TILE_SIZE, BOARD_TILE_THICK, BOARD_TILE_SIZE);

    layout.forEach((td) => {
        // 每格各自的材質：買地後會改 material.color 當作擁有者標記，
        // 共用材質的話會一次染到全部。
        const tile = new THREE.Mesh(tileGeo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
        tile.position.set(td.x, td.y, td.z);
        tile.userData.layout = td;
        scene.add(tile);
        tiles.push(tile);
        positions.push(tile.position);

        // 抬高的格子底下補一根支柱，看起來才像空中步道而不是浮空方塊。
        // 掛在格子底下（tile.add）而不是 scene，才會跟著格子一起隱藏。
        if (td.y > 0.4) {
            const pillar = new THREE.Mesh(
                new THREE.BoxGeometry(BOARD_TILE_SIZE * 0.62, td.y, BOARD_TILE_SIZE * 0.62),
                new THREE.MeshStandardMaterial({ color: 0x78909c, roughness: 0.9 })
            );
            // 區域座標：從格子底面往下延伸 td.y
            pillar.position.set(0, -td.y / 2 - BOARD_TILE_THICK / 2, 0);
            pillar.name = "board_pillar";
            tile.add(pillar);
        }
    });

    buildBoardConnectors(layout, tiles);
    addGroundShadows(tiles, layout);
    applyBoardAppearanceTo(tiles, gameMap);

    return { tiles: tiles, positions: positions };
}

/**
 * 相鄰格之間的連接橋。有高低差時會自然形成斜坡。
 * 移植自 past/BoardEditor/game.html 的 buildTileConnectors，
 * 但改成掛在「前一格」底下，這樣切到冒險全景時會跟著棋盤一起隱藏。
 */
function buildBoardConnectors(layout, tiles) {
    const mat = new THREE.MeshStandardMaterial({ color: 0x8d9eab, roughness: 0.85, metalness: 0.05 });
    const SLAB_H = 0.22;
    const OVERLAP = 0.2;              // 插進格子邊緣的深度，讓接縫看不出來
    const HALF = BOARD_TILE_SIZE / 2;
    const worldUp = new THREE.Vector3(0, 1, 0);

    for (let i = 0; i < layout.length; i++) {
        const a = layout[i];
        const b = layout[(i + 1) % layout.length];
        const tile = tiles[i];
        if (!tile) continue;

        const dx = b.x - a.x, dz = b.z - a.z;
        const hd = Math.sqrt(dx * dx + dz * dz);
        if (hd < 0.01) continue;
        const nx = dx / hd, nz = dz / hd;

        // 先用世界座標算出橋的兩端，再換算成 tile 的區域座標
        const sx = a.x + nx * (HALF - OVERLAP), sy = a.y, sz = a.z + nz * (HALF - OVERLAP);
        const ex = b.x - nx * (HALF - OVERLAP), ey = b.y, ez = b.z - nz * (HALF - OVERLAP);
        const len = Math.sqrt((ex - sx) * (ex - sx) + (ey - sy) * (ey - sy) + (ez - sz) * (ez - sz));
        if (len < 0.05) continue;

        const conn = new THREE.Mesh(
            new THREE.BoxGeometry(len, SLAB_H, BOARD_TILE_SIZE * 0.55), mat);
        conn.position.set(
            (sx + ex) / 2 - a.x,
            (sy + ey) / 2 - a.y,
            (sz + ez) / 2 - a.z
        );

        // 旋轉：手動組一組正交基底，不要用 setFromUnitVectors。
        //
        // setFromUnitVectors(X軸, 連線方向) 只保證「長度軸」轉到對齊
        // 連線方向，完全不管轉完之後「寬度軸」（BoxGeometry 第三個
        // 維度）被帶去哪——沒有高度差時連線方向全在水平面，這個
        // 「最短路徑旋轉」剛好落在世界 Y 軸上，寬度軸不受影響；但只要
        // 連線帶了 y 分量（兩格有高度差），旋轉就會連帶把寬度軸從
        // 水平面扭出一個角度，橋看起來像往垂直於行進方向的方向傾斜，
        // 高度差越大扭得越明顯（已在 static/preview/game_board_shapes.html
        // 用 157 項自動檢查驗證過這個修法）。
        //
        // 改成手動組正交基底：
        //   forward = 連線方向（跟原本一樣）
        //   right   = forward × 世界向上向量，正規化——這個外積結果
        //             永遠沒有 y 分量（叉積跟兩個輸入向量都垂直，
        //             其中一個是純垂直的 (0,1,0)，結果必然落在水平的
        //             XZ 平面），所以寬度軸不管連線多陡都保證水平，
        //             不會再被意外扭轉
        //   up      = right × forward，正規化——橋的厚度方向，自然
        //             順著坡度傾斜（這是應該的，斜坡本來就該斜著搭）
        const dir = new THREE.Vector3(ex - sx, ey - sy, ez - sz).normalize();
        let right = new THREE.Vector3().crossVectors(dir, worldUp);
        if (right.length() < 1e-6) {
            // dir 剛好完全垂直（正上/正下）——理論上棋盤格子間的連線
            // 不會有這種情況，防呆退回世界 X 軸當寬度方向
            right = new THREE.Vector3(1, 0, 0);
        } else {
            right.normalize();
        }
        const up = new THREE.Vector3().crossVectors(right, dir).normalize();
        const basis = new THREE.Matrix4().makeBasis(dir, up, right);
        conn.quaternion.setFromRotationMatrix(basis);

        conn.name = "board_connector";
        tile.add(conn);
    }
}

let _shadowTextureCache = null;

/**
 * 產生陰影用的貼圖：邊界模糊、四角圓滑的深灰色色塊，畫在透明背景上
 * （跟下面 createTerrainTexture 同一套「程序化 canvas 貼圖」手法，
 * 128×128，不讀外部圖檔）。只算一次、快取起來全部 26 格共用同一個
 * texture 物件——這片陰影長什麼樣子不會因為格子不同而變，沒必要每格
 * 各畫一次，也不該被個別格子的材質 dispose 一起清掉（跟
 * createTerrainTexture 的快取理由一樣）。
 */
function createShadowTexture() {
    if (_shadowTextureCache) return _shadowTextureCache;

    const SZ = 128;
    const c = document.createElement('canvas');
    c.width = c.height = SZ;
    const ctx = c.getContext('2d');

    const SHADOW_COLOR = 0x555555;
    const blurPx = SZ * 0.08;       // 模糊半徑
    const margin = blurPx * 2.2;    // 留白，模糊暈開的部分才不會被畫布邊界硬生生切掉
    const radius = SZ * 0.18;       // 圓角半徑
    const x = margin, y = margin;
    const w = SZ - margin * 2, h = SZ - margin * 2;

    ctx.filter = `blur(${blurPx}px)`;
    ctx.fillStyle = '#' + SHADOW_COLOR.toString(16).padStart(6, '0');
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, radius);
    ctx.closePath();
    ctx.fill();

    const tex = new THREE.CanvasTexture(c);
    _shadowTextureCache = tex;
    return tex;
}

/**
 * 在每個格子正下方、貼著地面（略高一點點，避免跟地面 z-fighting）
 * 的地方，疊一片邊界模糊、圓角的深灰色貼圖模擬陰影，掛成每個 tile
 * 的子物件（跟著格子一起被清掉/隱藏，不用額外管理生命週期，但共用的
 * texture 本身不會被一起清掉，見 createShadowTexture 的說明）。
 *
 * 子物件座標是相對於父物件（tile）的區域座標，而 tile 已經被擺在
 * 世界座標 (td.x, td.y, td.z)。陰影要落在固定的世界高度
 * SHADOW_WORLD_Y（不管格子本身多高都一樣），區域座標就是
 * SHADOW_WORLD_Y - td.y。
 */
function addGroundShadows(tiles, layout) {
    const geo = new THREE.PlaneGeometry(BOARD_TILE_SIZE * SHADOW_SCALE, BOARD_TILE_SIZE * SHADOW_SCALE);
    const texture = createShadowTexture();
    for (let i = 0; i < layout.length; i++) {
        const tile = tiles[i];
        if (!tile) continue;
        const td = layout[i];

        const shadow = new THREE.Mesh(
            geo,
            new THREE.MeshStandardMaterial({
                map: texture,
                transparent: true,
                depthWrite: false,   // 避免這片半透明貼圖跟正下方的地面深度打架
                roughness: 1,
                metalness: 0,
            })
        );
        shadow.rotation.x = -Math.PI / 2;
        shadow.position.set(0, SHADOW_WORLD_Y - td.y, 0);
        shadow.name = "board_ground_shadow";
        tile.add(shadow);
    }
}

/**
 * 地面：一片淺綠色的平面，長寬是 GROUND_SIZE（比棋盤本身大至少 3
 * 倍）。只呼叫一次即可（不隨棋盤重蓋而重蓋），由呼叫端（例如
 * game.html 的 init3D()）在建立場景時加一次。
 */
function addGroundPlane(scene) {
    const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(GROUND_SIZE, GROUND_SIZE),
        // 用 MeshBasicMaterial，不是 MeshStandardMaterial：Standard 材質
        // 會受光照影響，同一個顏色會因為表面朝向跟光源的夾角不同，算出
        // 不一樣的亮度——地面朝正上方（幾乎正對光源）跟牆面朝水平方向
        // 拿到的光照量差很多，即使兩者材質顏色數值完全一樣，畫面上看
        // 起來還是會不一樣深。Basic 材質不吃光照，直接畫材質本身的
        // 顏色，地面和牆才能真的呈現同一個顏色，不受朝向影響。
        new THREE.MeshBasicMaterial({ color: GROUND_COLOR }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(0, GROUND_Y, 0);
    ground.name = "ground_plane";
    scene.add(ground);
    return ground;
}

/**
 * 用四片平面把整個棋盤「以正方體的形式」包圍起來：地面（GROUND_SIZE
 * 見方）當正方體的底面，四片側牆的寬跟地面邊長一樣，高度也刻意設成
 * 跟地面邊長相等（GROUND_SIZE）——嚴格符合「正方體」的定義（六面等
 * 長）。只呼叫一次即可，用法跟 addGroundPlane 一樣。
 *
 * 側牆材質用 side: THREE.DoubleSide——攝影機大機率會位在這個正方體
 * 內側（牆高遠大於整個棋盤的尺度），雙面材質不管鏡頭在內側還外側都
 * 看得到，不用為每片牆分別計算法向量要朝內還朝外。
 */
function addBoardEnclosure(scene) {
    const half = GROUND_SIZE / 2;
    const wallHeight = GROUND_SIZE;
    const wallCenterY = GROUND_Y + wallHeight / 2;

    const wallGeo = new THREE.PlaneGeometry(GROUND_SIZE, wallHeight);
    const wallMat = new THREE.MeshBasicMaterial({ color: GROUND_COLOR, side: THREE.DoubleSide });

    const walls = [
        { x: 0, z: -half, ry: 0 },           // 北牆
        { x: 0, z: half, ry: 0 },            // 南牆
        { x: half, z: 0, ry: Math.PI / 2 },  // 東牆
        { x: -half, z: 0, ry: Math.PI / 2 }, // 西牆
    ];

    walls.forEach((w) => {
        const wall = new THREE.Mesh(wallGeo, wallMat);
        wall.position.set(w.x, wallCenterY, w.z);
        wall.rotation.y = w.ry;
        wall.name = "board_enclosure_wall";
        scene.add(wall);
    });
}

/**
 * 依 gameMap 決定每格的地形貼圖與裝飾。
 *
 * 為什麼要獨立成一個函式：建棋盤時 gameMap 可能還沒到（它來自非同步的
 * /game/map_config，也可能晚一步由房主的 SYNC_MAP 送來）。所以這裡設計成
 * 可以重複呼叫，地圖到齊之後再套一次即可。
 */
function applyBoardAppearanceTo(tiles, gameMap) {
    if (!tiles || !tiles.length) return;
    if (typeof terrainForTile !== "function") return;   // 模組沒載到就維持原樣

    tiles.forEach((tile, idx) => {
        const data = Array.isArray(gameMap) ? gameMap[idx] : null;
        const terrain = terrainForTile(data);

        tile.material.map = createTerrainTexture(terrain);
        tile.material.needsUpdate = true;

        // 先清掉上一輪的裝飾，避免重複套用時越疊越多
        for (let i = tile.children.length - 1; i >= 0; i--) {
            if (tile.children[i].name === BOARD_DECOR_NAME) tile.remove(tile.children[i]);
        }

        const glow = createTileEdgeGlow(terrain);
        glow.name = BOARD_DECOR_NAME;
        tile.add(glow);

        const props = createTerrainProps(terrain);
        props.name = BOARD_DECOR_NAME;
        tile.add(props);

        // 功能格（道具店／監獄／開合跳／獎勵／起點）放對應的建築
        const facility = data ? createFacilityProp(data.type) : null;
        if (facility) {
            facility.name = BOARD_DECOR_NAME;
            tile.add(facility);
        }
    });
}
