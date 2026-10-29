// =============================================================
// 全螢幕通知（showGameNotice）＋對手斷線訊息組字串
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_disconnect.html 要用同一份程式碼驗證 #11（對手斷線時原本只顯示
// 文字、duration=0 永遠不會自動消失，玩家只能自己注意到側邊欄連結手動
// 離開——現在補一顆「返回大廳」按鈕）。
//
// ⚠️ 原樣搬移，沒有修正任何既有行為：showGameNoticeInto() 裡
// `window.noticeHideTimer` 被 clearTimeout 但從未真的被賦值，連續呼叫
// 時舊的自動隱藏 timer 不會真的被取消，是個既存的小 race condition。
// 這次只是要重現「#11 的修法」，不是來清理這個，所以照抄不動，只在
// 這裡標註給團隊之後清理。
// =============================================================

function showGameNoticeInto(contentEl, msg, duration = 3000) {
    if (!contentEl) return;

    if (window.noticeHideTimer) clearTimeout(window.noticeHideTimer);

    // 🏆 先隱藏內容以利重置動畫
    contentEl.style.opacity = "0";
    console.log("📢 準備顯示訊息:", msg);

    setTimeout(() => {
        contentEl.innerHTML = `
            <div style="display: flex; justify-content: center; align-items: center; width: 100vw; height: 100vh; pointer-events: none; position: fixed; top: 0; left: 0; background: rgba(240, 249, 255, 0.3); backdrop-filter: blur(8px);">
                <div style="
                    background: rgba(255, 255, 255, 0.9);
                    padding: 40px 80px;
                    border-radius: 40px;
                    border: 2px solid #ffffff;
                    box-shadow: 0 15px 40px rgba(0,0,0,0.06);
                    animation: noticePopIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                ">
                    <h2 style="
                        font-size: 3.2rem;
                        color: #1e293b;
                        font-weight: 900;
                        margin: 0;
                        text-align: center;
                        letter-spacing: -1px;
                        display: block !important;
                    ">
                        ${msg}
                    </h2>
                </div>
            </div>
        `;
        contentEl.style.opacity = "1";
    }, 100);

    if (duration > 0) {
        setTimeout(() => {
            contentEl.style.opacity = "0";
            setTimeout(() => { if (contentEl.style.opacity === "0") contentEl.innerHTML = ""; }, 800);
        }, duration);
    }
}

function buildDisconnectNoticeHtml(username) {
    return `🔌 ${username} 已離線<br>`
        + `<span style="font-size:1.2rem;">對局無法繼續</span><br>`
        + `<button onclick="leaveDisconnectedRoomAndGoLobby()" style="margin-top:20px; pointer-events:auto; padding:10px 28px; font-size:1rem; font-weight:900; border:3px solid #1e272e; background:#ffde59; cursor:pointer;">返回大廳</button>`;
}
