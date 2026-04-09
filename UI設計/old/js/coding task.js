function runCompile() {
    const code = document.getElementById('code-editor').value.trim();
    const output = document.getElementById('output');

    // 簡單模擬進階校核邏輯
    // 正確答案範例：if hp < 10: \n    print("Danger")
    const cleanCode = code.replace(/\s+/g, ' '); // 忽略空格換行影響
    
    if (cleanCode.includes('if hp < 10:') && cleanCode.includes('print("Danger")')) {
        output.innerHTML = '<span class="success">[SUCCESS] 編譯完成。土地權限已解鎖。</span>';
        output.style.borderColor = '#4ee44e';
        
        setTimeout(() => {
            alert("編譯成功！資產已同步至雲端。");
        }, 500);
        
    } else {
        output.innerHTML = '<span class="error">[ERROR] 語法錯誤：請確認冒號、縮進及引號使用。</span>';
        output.style.borderColor = '#f05454';
        
        // 視窗震動效果
        document.querySelector('.task-window').animate([
            { transform: 'translateX(0)' },
            { transform: 'translateX(-10px)' },
            { transform: 'translateX(10px)' },
            { transform: 'translateX(0)' }
        ], { duration: 200, iterations: 2 });
    }
}