function selectVer(el) {
    document.querySelectorAll('.version-card').forEach(card => card.classList.remove('active'));
    el.classList.add('active');
}

function handleAILogic() {
    const aiStatus = document.getElementById('aiToggle').value;
    const playerSelect = document.getElementById('maxPlayers');
    if (aiStatus === 'on') {
        playerSelect.value = "1";
        playerSelect.disabled = true;
        playerSelect.style.backgroundColor = "#f1f5f9";
        playerSelect.style.cursor = "not-allowed";
    } else {
        playerSelect.disabled = false;
        playerSelect.style.backgroundColor = "#fdfdfd";
        playerSelect.style.cursor = "pointer";
    }
}