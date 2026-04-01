function check() {
    const input = document.getElementById('answer').value.trim();
    const feedback = document.getElementById('feedback');
    if (input === "1500") {
        feedback.innerHTML = '<span class="success">✅ 驗證成功！資格已解除鎖定</span>';
    } else {
        feedback.innerHTML = '<span class="error">❌ 語法錯誤，系統拒絕執行</span>';
    }
}
function closeWindow() {
    document.querySelector('.task-overlay').style.display = 'none';
}