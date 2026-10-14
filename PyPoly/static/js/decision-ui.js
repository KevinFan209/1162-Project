// =============================================================
// 收購/加蓋決策面板
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_decision.html 要用同一份程式碼——複製一份的話，日後改收購規則
// 就得記得改兩處，遲早變成「預覽好看但遊戲裡不是那樣」。
//
// 與 game.html 裡的原版唯一的差別：原本直接讀 playerCurrentIndex／
// window.landOwnership 這兩個全域變數算出 landData，現在改成直接接
// landData 參數，呼叫端自己先查好再傳進來（遊戲裡查
// window.landOwnership[playerCurrentIndex[activePlayerName]]，預覽頁
// 直接手寫假的 landData）。行為完全相同。
//
// 依賴既有 DOM：#adv-ui-name / #adv-ui-base / #adv-ui-weather-desc /
// #adv-ui-temp-desc / #adv-ui-aqi-notice / #adv-ui-total / #adv-ui-toll
// 必須已經存在於頁面上。
//
// showNotice 參數：遊戲裡傳 showGameNotice，預覽頁可以傳一個簡化版或
// no-op——這個提示跟「收購面板長什麼樣子」無關，不算核心邏輯。
// =============================================================
function fillDecisionUI(data, activePlayerName, landData, showNotice) {
    showNotice = showNotice || function () {};

    window.isDiscountApplied = false;
    window.discountedPrice = 0;
    window.currentBuyoutTarget = null;
    window.currentBuyoutPrice = 0;
    window.isUpgrading = false; // 🏆 新增升級狀態
    window.upgradePrice = 0;
    window.newToll = 0;

    if (!data) return;

    const nameEl = document.getElementById('adv-ui-name');
    if (nameEl) nameEl.innerText = (landData && landData.name) ? landData.name : (data.name || "未知土地");

    const basePrice = landData ? (landData.originalPrice || data.base_price) : data.base_price;
    const currentToll = landData ? (landData.toll || data.toll) : data.toll;

    const baseEl = document.getElementById('adv-ui-base');
    if (baseEl) {
        if (landData && landData.owner !== activePlayerName) {
            baseEl.innerHTML = `$${basePrice}<br><span style="font-size: 0.75rem; color: #94a3b8; font-weight: 700;">(原地主購入價)</span>`;
        } else {
            baseEl.innerText = `$${basePrice}`;
        }
    }

    // ⛅ 即時天氣狀況（替換原人流計數）
    const weatherEl = document.getElementById('adv-ui-weather-desc');
    if (weatherEl) {
        if (data.has_temp_event) {
            weatherEl.innerText = `${data.weather || '晴'} (${data.temp_station}站)`;
        } else {
            weatherEl.innerText = '晴朗';
        }
    }

    // 🌡️ 即時氣溫與加成（替換原觀光加成）
    const tempEl = document.getElementById('adv-ui-temp-desc');
    if (tempEl) {
        if (data.has_temp_event) {
            tempEl.innerText = `${data.temp}°C (×${data.temp_multiplier})`;
        } else {
            tempEl.innerText = '適中 (×1.0)';
        }
    }

    const aqiTag = document.getElementById('adv-ui-aqi-notice');
    const totalEl = document.getElementById('adv-ui-total');
    const tollEl = document.getElementById('adv-ui-toll');

    // 🏆 情境 A：自己是地主 -> 加蓋升級模式
    if (landData && landData.owner === activePlayerName) {
        if (aqiTag) {
            aqiTag.innerText = `👑 您的領地 (可加蓋)`;
            aqiTag.style.background = "#00cdac";
            aqiTag.style.color = "white";
            aqiTag.style.display = "block";
        }

        window.upgradePrice = Math.floor(basePrice * 0.5);
        window.newToll = Math.floor(currentToll * 2);
        window.isUpgrading = true;

        if (totalEl) totalEl.innerHTML = `<span style="font-size: 1.5rem; color: #94a3b8; margin-right:10px;">加蓋費用</span> <span style="color:#00cdac;">$${window.upgradePrice}</span>`;
        if (tollEl) tollEl.innerHTML = `<span style="text-decoration: line-through; color: #94a3b8; font-size: 0.9rem;">$${currentToll}</span> <span style="color: #f08c00;">$${window.newToll}</span>`;

        setTimeout(() => showNotice(`🏠 歡迎回來！加蓋一層樓只需 $${window.upgradePrice}，過路費將提升！`, 3500), 800);
    }
    // 情境 B：別人是地主 -> 強制收購模式
    else if (landData && landData.owner !== activePlayerName) {
        if (aqiTag) {
            aqiTag.innerText = `👑 原地主：${landData.owner}`;
            aqiTag.style.background = "#ff4757";
            aqiTag.style.color = "white";
            aqiTag.style.display = "block";
        }

        const buyoutPrice = Math.floor(basePrice * 1.5);
        if (totalEl) totalEl.innerHTML = `<span style="font-size: 2rem; text-decoration: line-through; color: #94a3b8; margin-right:10px;">$${basePrice}</span> <span style="color:#ff4757;">$${buyoutPrice}</span>`;
        if (tollEl) tollEl.innerText = `$${currentToll}`;

        window.currentBuyoutTarget = landData.owner;
        window.currentBuyoutPrice = buyoutPrice;

        setTimeout(() => showNotice(`👑 此地主為 ${landData.owner}！強制收購需加價 50%！`, 3500), 800);
    }
    // 情境 C：空地 -> 一般收購（頂部只顯示 AQI 特殊事件）
    else {
        if (aqiTag) {
            if (data.has_env_event) {
                const em = data.env_multiplier;
                aqiTag.innerText = `🍃 ${data.env_station}站 AQI ${data.aqi}（${data.env_status}，×${em}）`;
                aqiTag.style.background = (em >= 1.0) ? "#00cdac" : "#ff7675";
                aqiTag.style.color = "white";
                aqiTag.style.padding = "6px 12px";
                aqiTag.style.display = "block";
            } else {
                aqiTag.style.display = "none"; // 無 AQI 事件時隱藏頂部標籤
            }
        }
        if (totalEl) totalEl.innerText = `$${data.total_price || 0}`;
        if (tollEl) tollEl.innerText = `$${data.toll || 0}`;
    }
}
