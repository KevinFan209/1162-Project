// =============================================================
// 冒險答題 UI（基礎手勢題／進階程式碼題）——題目填入畫面
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_quiz.html 要用同一份程式碼。
//
// ⚠️ 範圍跟 Phase 5（骰子）一樣刻意縮小：`startAdventureRecognition()`
// 本身牽涉鏡頭/計時器/Socket.IO 廣播/virtualScreen 定位，這些都是
// 對局限定的流程控制，留在 game.html 不搬。這裡只抽「題目長怎樣、
// 怎麼填進畫面」這段純 DOM 操作（不讀 socket／鏡頭／全域計時器）。
//
// 另外發現一個現有的附帶問題（這次沒有動它，只記錄下來）：
// `startAdventureRecognition()` 在 game.html 裡被宣告了兩次
// （目前抽取時參考的是檔案裡後面、實際生效的那份），前面那份是
// 死程式碼，建議團隊之後有空清掉。
//
// 真正送出答案/驗證程式碼/重試次數扣減這些邏輯，跟遊戲結果的連動
// （handleCodeSuccess/handleCodeFail/submitQuizAnswer）太深，不在
// 這次抽取範圍，繼續留在 game.html。
// =============================================================

// 基礎手勢題：先顯示「準備辨識」提示，過 revealDelayMs 毫秒才揭示
// 題目跟選項——這個延遲是原本就有的視覺設計（給玩家一點心理準備時間），
// 一併保留。回傳一個 Promise，題目真的揭示後才 resolve。
function renderBasicQuizQuestion(questionTextEl, optionsAreaEl, questionObj, revealDelayMs) {
    questionTextEl.innerHTML = "✋ 準備辨識，請用手勢比出答案";
    questionTextEl.style.display = "block";
    optionsAreaEl.style.display = 'none';

    return new Promise(resolve => {
        setTimeout(() => {
            questionTextEl.innerHTML = `【挑戰題目】${questionObj.content}`;
            optionsAreaEl.innerHTML = questionObj.options.map((opt, idx) =>
                `<div class="opt-pill">(${idx + 1}) ${opt}</div>`
            ).join("");
            optionsAreaEl.style.display = 'flex';
            resolve();
        }, revealDelayMs);
    });
}

// 進階程式碼題：填入題目文字、清空編輯器、重置嘗試次數跟提示文字/按鈕狀態。
// els = { questionEl, editorEl, feedbackEl, attemptsEl, submitBtnEl }
function renderCodeQuizQuestion(els, questionObj, maxAttempts) {
    els.questionEl.innerText = questionObj.content;
    els.editorEl.value = "";

    if (els.feedbackEl) {
        els.feedbackEl.innerText = "💡 請在下方編譯器輸入程式碼，並點擊執行驗證";
        els.feedbackEl.style.color = "#00cdac";
    }
    if (els.attemptsEl) els.attemptsEl.innerText = maxAttempts;
    if (els.submitBtnEl) {
        els.submitBtnEl.disabled = false;
        els.submitBtnEl.style.opacity = "1";
    }
}
