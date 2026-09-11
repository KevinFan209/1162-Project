// =============================================================
// 棋盤版面：26 格的座標與高度
//
// 這份資料原本是寫死在 game.html 的 create3DBoard 裡的四個 for 迴圈。
// 抽出來的目的是讓版面成為可以閱讀與修改的資料，而不是藏在渲染程式中。
//
// ⚠️ 格子數與特殊格的位置必須與後端一致。
//    main.py 的 get_map_config 寫死了這些索引：
//        0 = START 起點      3, 16 = SHOP 道具店
//        6 = PUNISH 開合跳   13    = JAIL 監獄
//        19 = REWARD 獎勵    其餘 20 格 = ADVENTURE 冒險格
//    改動格子數或順序的話，兩邊要一起改，否則特殊格會錯位。
//
// 尺寸沿用現行值（間距 6、邊界 ±24/±15、格子 5×5），
// 刻意不採用 past/BoardEditor 的間距 4——那會讓相機距離、
// 房屋位移、雙人角色的左右 offset 全部要重新調整。
// =============================================================

const BOARD_TILE_SIZE = 5;     // 格子邊長
const BOARD_TILE_THICK = 0.5;  // 格子厚度
const BOARD_SPACING = 6;       // 格心間距（5 格寬 + 1 空隙）

// 高度樣式：讓棋盤像一條有起伏的環形步道，而不是一塊平板。
// 下邊由低漸高、右邊維持高處、上邊緩降、左邊回到地面，
// 剛好在走完一圈時回到起點高度。
const BOARD_HEIGHTS = [
    // 下邊 9 格：0 → 4，緩緩爬升
    0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4,
    // 右邊 5 格：高處平台，尾端開始下降
    4, 4, 4, 3.5, 3,
    // 上邊 8 格：3 → 0，一路下坡
    3, 2.5, 2, 2, 1.5, 1, 0.5, 0,
    // 左邊 4 格：貼近地面收尾
    0, 0.5, 0.5, 0,
];

/**
 * 產生 26 格的版面資料。
 * 回傳 [{ x, y, z, size }, ...]，順序即為玩家前進的順序。
 */
function buildBoardLayout() {
    const S = BOARD_SPACING;
    const pos = [];

    // 四個邊接成一個環。數量 9 + 5 + 8 + 4 = 26。
    // 每邊的起始 i 錯開，是為了不重複計算轉角那一格。
    for (let i = 0; i < 9; i++) pos.push({ x: -24 + i * S, z: 15 });
    for (let i = 1; i < 6; i++) pos.push({ x: 24, z: 15 - i * S });
    for (let i = 1; i < 9; i++) pos.push({ x: 24 - i * S, z: -15 });
    for (let i = 1; i < 5; i++) pos.push({ x: -24, z: -15 + i * S });

    return pos.map((p, i) => ({
        x: p.x,
        y: BOARD_HEIGHTS[i] ?? 0,
        z: p.z,
        size: 1,
    }));
}

const BOARD_LAYOUT = {
    version: 1,
    tileCount: 26,
    tiles: buildBoardLayout(),
};
