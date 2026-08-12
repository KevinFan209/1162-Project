// 🏆 1. 側邊選單切換邏輯 (原本的功能)
function toggleMenu() {
    document.getElementById('sideMenu').classList.toggle('open');
    document.getElementById('overlay').classList.toggle('open');
}

// 🏆 2. 踩格檢查與 AQI 數據請求
/**
 * 當玩家小車停留在某個地標格時呼叫此函式
 * @param {string} stationName - 監測站名稱（"埔里", "南投", "鹿谷", "竹山"），一般格傳入 null 或 "" 即可
 */
async function onPlayerLand(stationName) {
    // 判斷 1：一般格子直接跳過，不安裝與請求 API
    if (!stationName || stationName.trim() === "") {
        console.log("一般格子：無視氣候 API，進入一般買地/解題流程");
        return;
    }

    // 判斷 2：為 4 大監測站之一，向 FastAPI 後端發送請求
    try {
        const apiUrl = `http://127.0.0.1:8000/api/air-quality?station=${encodeURIComponent(stationName)}`;
        const response = await fetch(apiUrl);
        const data = await response.json();

        if (data.has_event) {
            showAQICard(data);
        }
    } catch (error) {
        console.error("連線後端 API 失敗，無法讀取 AQI:", error);
    }
}

// 🏆 3. 跳出空氣品質加成卡片
function showAQICard(data) {
    alert(
        `🍃【${data.station_name}空氣品質監測站】\n\n` +
        `即時 AQI 指數：${data.aqi} (${data.status})\n` +
        `💰 本區地價與過路費加成：× ${data.multiplier}\n\n` +
        `（按下確定後進入本區 Python 挑戰）`
    );

    // 觸發解題視窗 (如 basic.js / modal.js 裡面的開啟卡片函式)
    if (typeof openTaskModal === "function") {
        openTaskModal();
    }
}

// 🏆 4. 模擬測試腳本：在地圖畫面上按下鍵盤 T 鍵可測試跳卡
document.addEventListener('keydown', function(event) {
    if (event.key === 't' || event.key === 'T') {
        console.log("【測試模組】模擬小車踩到埔里監測站...");
        onPlayerLand("埔里");
    }
});