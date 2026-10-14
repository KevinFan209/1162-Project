// =============================================================
// 後台遊戲數據頁——統計卡/LIVE 對局列表填值
//
// 從 game_data.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_data_stats.html 要用同一份程式碼驗證 #37（原本整頁是寫死假
// 資料，現在改接 GET /admin/game_stats）的畫面渲染邏輯，不想讓預覽頁
// 跟 game_data.html 各自維護一份、最後演化成兩邊不一致。
//
// 「伺服器延遲」卡跟趨勢圖本身是純靜態文字（沒有對應 DOM id，後端也
// 沒有回傳對應欄位），不在這個模組處理範圍內。
//
// els = { onlineEl, ongoingEl, accuracyEl, liveListEl }
// data = { online_count, ongoing_matches, today_accuracy, live_rooms }
// =============================================================

function renderGameStats(els, data) {
    els.onlineEl.innerHTML = `${data.online_count}<span>人</span>`;
    els.ongoingEl.innerHTML = `${data.ongoing_matches}<span>場</span>`;
    els.accuracyEl.innerHTML = `${data.today_accuracy}<span>%</span>`;

    if (!data.live_rooms || data.live_rooms.length === 0) {
        els.liveListEl.innerHTML = `<div class="match-item"><div class="match-info"><p>目前沒有進行中的對局</p></div></div>`;
        return;
    }
    els.liveListEl.innerHTML = data.live_rooms.map(room => `
        <div class="match-item">
            <div class="match-info">
                <h4>${room.name}</h4>
                <p>${room.players.join(' | ')} | 難度：${room.difficulty || '--'}</p>
            </div>
            <div class="match-progress">
                <span class="prog-tag">房號：${room.code}</span>
            </div>
        </div>
    `).join('');
}
