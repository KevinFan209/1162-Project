// =============================================================
// 後台「編輯使用者角色」modal 填值
//
// 從 admin.html 抽出來的共用模組。抽離的原因是 static/preview/
// admin_edit_role.html 要用同一份程式碼驗證 #36（編輯按鈕原本完全
// 沒有 onclick）的修法，不想讓預覽頁跟 admin.html 各自維護一份、
// 最後演化成兩邊不一致。
//
// 原樣搬移 admin.html 原本 openEditRoleModal() 的內部邏輯，只是把
// 讀 document.getElementById 的部分改成接參數，並把原本寫死呼叫
// executeRoleChange() 的部分改成 onConfirm(newRole) callback——
// admin.html 傳真的 executeRoleChange，預覽頁傳假的模擬函式。
// =============================================================

function fillEditRoleModal(titleEl, msgEl, footerEl, targetUser, currentRole, roles, onConfirm) {
    roles = roles || [
        { value: 'player', label: '一般玩家' },
        { value: 'banned', label: '封鎖' },
    ];

    titleEl.innerText = `✏️ 編輯使用者「${targetUser}」`;
    titleEl.style.color = "var(--pixel-blue)";
    msgEl.innerHTML = `
        <label style="display:block; margin-bottom:8px; font-weight:700;">權限角色</label>
        <select id="editRoleSelect" style="width:100%; padding:8px; font-size:1rem;">
            ${roles.map(r => `<option value="${r.value}" ${r.value === currentRole ? 'selected' : ''}>${r.label}</option>`).join('')}
        </select>
    `;

    footerEl.innerHTML = `
        <button class="btn-3d" id="confirmEditBtn" style="background: var(--pixel-blue); color: white; margin-right: 10px;">儲存</button>
        <button class="btn-3d" style="background: #dfe4ea; color: var(--text-dark);" onclick="closeModal()">取消</button>
    `;

    footerEl.querySelector('#confirmEditBtn').onclick = async () => {
        const newRole = document.getElementById('editRoleSelect').value;
        if (newRole === currentRole) { closeModal(); return; }
        await onConfirm(newRole);
        closeModal();
    };
}
