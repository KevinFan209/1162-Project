// =============================================================
// 小地圖（2D 格子總覽）
//
// 從 game.html 抽出來的共用模組。抽離的原因是
// static/preview/game_minimap.html 要用同一份程式碼——複製一份的話，
// 之後改格子配色或圖示就得記得改兩處。
//
// 與原版的差別：原本直接讀 gameMap / window.landOwnership，
// 並呼叫 getPlayerLandColor 與 showTileInfo（都在 game.html 裡），
// 現在全部改成接參數，預覽頁才用得了。行為完全相同。
//
// 樣式在 static/css/minimap.css。
// =============================================================

const miniMapGridPositions = [
    "6/1", "6/2", "6/3", "6/4", "6/5", "6/6", "6/7", "6/8", "6/9", // 0-8: 下邊
    "5/9", "4/9", "3/9", "2/9", "1/9",                             // 9-13: 右邊
    "1/8", "1/7", "1/6", "1/5", "1/4", "1/3", "1/2", "1/1",        // 14-21: 上邊
    "2/1", "3/1", "4/1", "5/1"                                     // 22-25: 左邊
];

/**
 * 把小地圖畫進指定的容器。
 * @param {HTMLElement} container   放格子的容器（通常是 #minimap-grid-content）
 * @param {Array} gameMap           26 格的資料
 * @param {Object} landOwnership    {格子索引: {owner}}，可傳 null
 * @param {Function} colorFn        依擁有者名稱回傳顏色
 * @param {Function} onTileClick    點擊格子時的回呼，可省略
 */
function renderMiniMapTilesInto(container, gameMap, landOwnership, colorFn, onTileClick) {
    container.innerHTML = ''; // 清空重建

    gameMap.forEach((tile, idx) => {
        const gridArea = miniMapGridPositions[idx];
        const landData = (landOwnership || {})[idx];
        
        let bgColor = "#f8fafc"; // 預設空地顏色
        let icon = "";
        let borderColor = "#e2e8f0";

        // 判斷特殊格子圖示
        if (tile.type === 'START') { bgColor = "#dcfce7"; borderColor = "#22c55e"; icon = "🎈"; }
        else if (tile.type === 'JAIL') { bgColor = "#e2e8f0"; borderColor = "#64748b"; icon = "⛓️"; }
        else if (tile.type === 'SHOP') { bgColor = "#fef9c3"; borderColor = "#eab308"; icon = "🛒"; }
        else if (tile.type === 'PUNISH') { bgColor = "#fee2e2"; borderColor = "#ef4444"; icon = "💦"; }
        else if (tile.type === 'REWARD') { bgColor = "#e0f2fe"; borderColor = "#0ea5e9"; icon = "🦅"; }
        else if (tile.type === 'ADVENTURE') {
            // 如果是被買走的土地，同步 3D 棋盤的顏色！
            if (landData && landData.owner) {
                bgColor = colorFn(landData.owner);
                borderColor = "#ffffff";
                icon = "🏠";
            }
        }

        const tileEl = document.createElement('div');
        tileEl.className = 'minimap-tile';
        tileEl.style.gridArea = gridArea;
        tileEl.style.backgroundColor = bgColor;
        tileEl.style.borderColor = borderColor;
        tileEl.innerHTML = icon;
        
        // 綁定點擊事件
        tileEl.onclick = (e) => {
            e.stopPropagation(); // 防止點擊穿透關閉地圖
            if (onTileClick) onTileClick(idx, tile);
        };
        
        container.appendChild(tileEl);
    });
}
