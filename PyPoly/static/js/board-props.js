// =============================================================
// 功能格的建築
//
// 道具店、監獄、開合跳、獎勵格這些「功能格」不套地形貼圖，
// 改在格子上放一棟代表該功能的建築，讓玩家在 3D 場上一眼認得出來。
// （先前 26 格全是白色方塊，只有起點是綠色，功能格完全看不出區別。）
//
// 全部用基本幾何體組成，風格比照 game.html 既有的 createHouse
// （Group + Box 屋身 + Cone 屋頂）。專案裡沒有任何 GLB/GLTF 模型，
// 也刻意不引入——這樣不會增加載入時間，配色也好統一。
//
// ⚠️ 每個函式都回傳 THREE.Group，座標是相對於格子中心的區域座標。
//    呼叫端必須用 tile.add(group) 掛成格子的子物件，不要 scene.add()：
//    setBoardVisibility() 只切換 allTileMeshes，直接加進 scene 的建築
//    在進入冒險全景時不會被隱藏，會浮在天空盒上。
// =============================================================

// 格子頂面在區域座標的高度
const PROP_GROUND = 0.25;   // = BOARD_TILE_THICK / 2

function _mat(color, opts) {
    return new THREE.MeshStandardMaterial(Object.assign({ color: color, roughness: 0.85 }, opts || {}));
}

/** 起點：拱門 + 旗幟 */
function createStartProp() {
    const g = new THREE.Group();
    const postMat = _mat(0x00897b);
    const beamMat = _mat(0x00cdac);

    // 兩根立柱
    [-1.6, 1.6].forEach(function (x) {
        const post = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 2.6, 8), postMat);
        post.position.set(x, PROP_GROUND + 1.3, 0);
        g.add(post);
    });
    // 橫樑
    const beam = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.4, 0.45), beamMat);
    beam.position.set(0, PROP_GROUND + 2.75, 0);
    g.add(beam);
    // 旗幟
    const flag = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.6, 0.06), _mat(0xffd54f));
    flag.position.set(0, PROP_GROUND + 3.3, 0);
    g.add(flag);

    return g;
}

/** 道具店：小屋 + 遮陽棚 + 招牌 */
function createShopProp() {
    const g = new THREE.Group();

    const body = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.4, 1.6), _mat(0xfff8e1));
    body.position.set(0, PROP_GROUND + 0.7, -0.3);
    g.add(body);

    // 屋頂（四角錐，轉 45 度讓稜線對齊屋身）
    const roof = new THREE.Mesh(new THREE.ConeGeometry(1.6, 0.9, 4), _mat(0xef6c00));
    roof.position.set(0, PROP_GROUND + 1.85, -0.3);
    roof.rotation.y = Math.PI / 4;
    g.add(roof);

    // 遮陽棚：紅白條紋用兩塊薄板交錯表示
    for (let i = 0; i < 5; i++) {
        const stripe = new THREE.Mesh(
            new THREE.BoxGeometry(0.4, 0.08, 0.8),
            _mat(i % 2 === 0 ? 0xe53935 : 0xfafafa));
        stripe.position.set(-0.8 + i * 0.4, PROP_GROUND + 1.05, 0.7);
        stripe.rotation.x = -0.25;
        g.add(stripe);
    }

    // 招牌
    const sign = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.45, 0.08), _mat(0xffb300));
    sign.position.set(0, PROP_GROUND + 1.55, 0.55);
    g.add(sign);

    return g;
}

/** 監獄：灰色方塊 + 直向鐵欄 */
function createJailProp() {
    const g = new THREE.Group();

    const body = new THREE.Mesh(new THREE.BoxGeometry(2.2, 1.8, 1.8), _mat(0x757575));
    body.position.set(0, PROP_GROUND + 0.9, 0);
    g.add(body);

    // 平屋頂
    const roof = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.25, 2.1), _mat(0x4e5b62));
    roof.position.set(0, PROP_GROUND + 1.9, 0);
    g.add(roof);

    // 正面的鐵欄杆
    const barMat = _mat(0x263238, { metalness: 0.5, roughness: 0.4 });
    for (let i = 0; i < 5; i++) {
        const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 1.2, 6), barMat);
        bar.position.set(-0.6 + i * 0.3, PROP_GROUND + 0.85, 0.92);
        g.add(bar);
    }
    // 橫向兩條
    [0.35, 1.35].forEach(function (y) {
        const cross = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.08, 0.08), barMat);
        cross.position.set(0, PROP_GROUND + y, 0.92);
        g.add(cross);
    });

    return g;
}

/** 開合跳：運動場地標（單槓 + 跑道標線） */
function createPunishProp() {
    const g = new THREE.Group();
    const frameMat = _mat(0xef5350, { metalness: 0.3 });

    // 單槓：兩根立柱 + 一根橫桿
    [-1.2, 1.2].forEach(function (x) {
        const post = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 2.0, 8), frameMat);
        post.position.set(x, PROP_GROUND + 1.0, -0.4);
        g.add(post);
    });
    const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 2.6, 8), frameMat);
    bar.rotation.z = Math.PI / 2;
    bar.position.set(0, PROP_GROUND + 2.0, -0.4);
    g.add(bar);

    // 跑道標線
    const lineMat = _mat(0xfafafa);
    for (let i = 0; i < 3; i++) {
        const line = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.04, 0.16), lineMat);
        line.position.set(0, PROP_GROUND + 0.02, 0.5 + i * 0.5);
        g.add(line);
    }

    return g;
}

/** 獎勵遊戲：禮物箱 + 緞帶 */
function createRewardProp() {
    const g = new THREE.Group();

    const box = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.3, 1.6), _mat(0x42a5f5));
    box.position.set(0, PROP_GROUND + 0.65, 0);
    g.add(box);

    // 十字緞帶
    const ribbonMat = _mat(0xffd54f);
    const rv = new THREE.Mesh(new THREE.BoxGeometry(0.28, 1.34, 1.66), ribbonMat);
    rv.position.set(0, PROP_GROUND + 0.65, 0);
    g.add(rv);
    const rh = new THREE.Mesh(new THREE.BoxGeometry(1.66, 1.34, 0.28), ribbonMat);
    rh.position.set(0, PROP_GROUND + 0.65, 0);
    g.add(rh);

    // 蝴蝶結：兩顆球充當
    [-0.35, 0.35].forEach(function (x) {
        const knot = new THREE.Mesh(new THREE.SphereGeometry(0.26, 8, 6), ribbonMat);
        knot.position.set(x, PROP_GROUND + 1.42, 0);
        g.add(knot);
    });

    return g;
}

/**
 * 依格子類型取得建築；沒有對應建築的類型（ADVENTURE / BLANK）回 null。
 * ADVENTURE 走地形裝飾（board-terrain.js），BLANK 是測試模式用的空白格，
 * 刻意保持空曠讓人一眼看出這局是測試地圖。
 */
function createFacilityProp(type) {
    switch (type) {
        case 'START':  return createStartProp();
        case 'SHOP':   return createShopProp();
        case 'JAIL':   return createJailProp();
        case 'PUNISH': return createPunishProp();
        case 'REWARD': return createRewardProp();
        default:       return null;
    }
}
