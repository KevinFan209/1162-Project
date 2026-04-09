function check() {
    const input = document.getElementById('answerHard').value.trim();
    const feedback = document.getElementById('feedback');
    
    // 判斷邏輯：檢查是否包含關鍵變數與數值 (忽略空格)
    const sanitizedInput = input.replace(/\s/g, "");
    
    if (sanitizedInput.includes("price=1500")) {
        feedback.innerHTML = '<span class="success">✅ 編譯成功！購買資格已解除鎖定</span>';
    } else if (input === "") {
        feedback.innerHTML = '<span class="error">⚠️ 編輯器內容為空</span>';
    } else {
        feedback.innerHTML = '<span class="error">❌ 代碼邏輯錯誤，請重新檢查</span>';
    }
}

function closeWindow() {
    document.querySelector('.task-overlay').style.display = 'none';
}