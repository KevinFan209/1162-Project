function toggle(mode) {
    const loginForm = document.getElementById('loginForm');
    const regForm = document.getElementById('regForm');
    const loginTab = document.getElementById('loginTab');
    const regTab = document.getElementById('regTab');

    if (mode === 'register') {
        loginForm.classList.remove('active');
        regForm.classList.add('active');
        loginTab.classList.remove('active');
        regTab.classList.add('active');
    } else {
        loginForm.classList.add('active');
        regForm.classList.remove('active');
        loginTab.classList.add('active');
        regTab.classList.remove('active');
    }
}