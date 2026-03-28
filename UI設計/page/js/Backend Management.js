// 側邊選單頁面切換功能
document.addEventListener('DOMContentLoaded', function() {
    const navItems = document.querySelectorAll('.nav-item');
    
    // 初始化：顯示預設頁面（玩家帳號管理）
    showPage('User-Management');
    
    // 為每個導航項目添加點擊事件
    navItems.forEach((item) => {
        item.addEventListener('click', function() {
            const pageClass = this.getAttribute('data-page');
            
            // 移除所有 active 類別
            navItems.forEach(i => i.classList.remove('active'));
            
            // 添加 active 類別到當前項目
            this.classList.add('active');
            
            // 顯示對應頁面
            showPage(pageClass);
        });
    });
});

// 頁面切換函數
function showPage(pageClass) {
    const allPages = document.querySelectorAll('.User-Management, .Game-Analytics, .Question-CMS, .Vision-Debugger');
    
    allPages.forEach(page => {
        if (page.classList.contains(pageClass)) {
            // 根據頁面類型設置不同的display屬性
            if (pageClass === 'Vision-Debugger') {
                page.style.display = 'grid';
            } else {
                page.style.display = 'flex';
            }
            page.classList.add('active-page');
        } else {
            page.style.display = 'none';
            page.classList.remove('active-page');
        }
    });
}