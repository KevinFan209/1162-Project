function toggleModal(show) {
    const display = show ? 'block' : 'none';
    document.getElementById('modal-overlay').style.display = display;
    document.getElementById('modal-content').style.display = display;
}

function setMode(mode) {
    const baseBtn = document.getElementById('btn-base');
    const advBtn = document.getElementById('btn-adv');
    if(mode === 'base') {
        baseBtn.classList.add('active'); advBtn.classList.remove('active');
    } else {
        advBtn.classList.add('active'); baseBtn.classList.remove('active');
    }
}

function startGame() {
    alert("房間建立成功！即將進入 PyPoly 世界...");
    toggleModal(false);
    // 這裡未來可以跳轉到主遊戲網頁
}