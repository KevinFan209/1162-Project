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

/**
 * 建立整個 26 格棋盤。
 * @param {THREE.Scene} scene  要加進去的場景
 * @param {Array} gameMap      26 格的資料（可為空，之後再用 applyBoardAppearanceTo 套）
 * @returns {{tiles: THREE.Mesh[], positions: THREE.Vector3[]}}
 */
function buildBoard(scene, gameMap) {
    const tiles = [];
    const positions = [];

    // 座標與高度由 board-layout.js 提供。
    // 抽成資料是為了讓版面看得懂也改得動，不再埋在四個 for 迴圈裡。
    const layout = BOARD_LAYOUT.tiles;
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
        conn.setRotationFromQuaternion(
            new THREE.Quaternion().setFromUnitVectors(
                new THREE.Vector3(1, 0, 0),
                new THREE.Vector3(ex - sx, ey - sy, ez - sz).normalize()
            )
        );
        conn.name = "board_connector";
        tile.add(conn);
    }
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
