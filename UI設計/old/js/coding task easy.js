function runCheck() {
    const ans = document.getElementById('basic-ans').value.trim();
    const output = document.getElementById('output');

    // 基礎校核邏輯
    if (ans === '=') {
        output.innerHTML = '<span class="success">[SUCCESS] 語法正確。購買資格已確認。</span>';
        output.style.borderColor = '#4ee44e';
        
        setTimeout(() => {
            alert("任務達成！已獲得土地。");
        }, 400);
        
    } else {
        output.innerHTML = '<span class="error">[ERROR] 語法錯誤：無效的運算子 "' + ans + '"。</span>';
        output.style.borderColor = '#f05454';
        
        // 視窗震動效果
        document.querySelector('.task-window').animate([
            { transform: 'translateX(0)' },
            { transform: 'translateX(-8px)' },
            { transform: 'translateX(8px)' },
            { transform: 'translateX(0)' }
        ], { duration: 150, iterations: 2 });
    }
}

// 支援按下 Enter 鍵直接執行
document.getElementById('basic-ans').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        runCheck();
    }
});