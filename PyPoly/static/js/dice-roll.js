// =============================================================
// 骰子畫面繪製
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_dice.html 要用同一份程式碼。
//
// ⚠️ 範圍比計畫原本想的小：原本想連「對局中擲骰的觸碰偵測/手勢辨識
// UI」一起抽，實際讀過程式碼後發現這塊比預期更深地纏在一起——
// `startRecognitionProcess()`（先後手擲骰的手勢偵測）跟對局中擲骰的
// 觸碰/手勢流程都直接讀寫一大串全域狀態（currentLandmarks、
// isOrderDecided、myDicePoint、cameraInstance、window.uiState...），
// 而且過程中發現這塊還藏著一個現有的死程式碼
// （`renderOrderFrame()`，整支函式定義了卻從來沒被呼叫過，是先前
// 改版留下的殘骸，不是這次造成的，這次也沒去動它，只是順手記錄
// 下來給團隊之後清）。勉強把這些也抽出來，風險會大於這次要做的事
// 本身值得冒的風險，所以這次只抽「畫一顆骰子長怎樣」這個已經被多處
// 呼叫、本身就是純函式的 drawDiceFace()，不碰攝影機/手勢偵測那段。
// 預覽頁用模擬按鈕展示骰子動畫，不是接真的攝影機。
// =============================================================

function drawDiceFace(ctx, img, x, y, isRollingEffect) {
    if (!img || !img.complete) return;
    const size = 120; // 調整骰子大小
    ctx.drawImage(img, x - size / 2, y - size / 2, size, size);

    if (isRollingEffect) {
        ctx.strokeStyle = "#ffde59";
        ctx.lineWidth = 4;
        ctx.strokeRect(x - size / 2 - 5, y - size / 2 - 5, size + 10, size + 10);
    }
}
