// =============================================================
// 調整面板——給預覽頁用的通用「畫面位置」調整工具（2D DOM 版）
//
// 跟 static/js/transform-gizmo.js 是同一套思路（數字輸入框 + 存成
// JSON，給人之後手動讀、手動套回程式碼），但那個版本只能調 Three.js
// 3D 物件的 position/rotation；這個版本調的是用 CSS 排版的 2D 畫面
// 元素（答題選項區、商店版面這類 fixed/absolute/flex 排出來的畫面），
// 不是 3D 物件。
//
// 做法：不去改動元素原本的 top/left/flex 排版邏輯，只在它原本已有的
// CSS transform（例如 .task-options 的 translateY(-50%)）後面疊加一個
// translate(dx, dy) 的像素偏移。畫面上每個 target 旁邊會出現一個可以
// 直接拖曳的「⠿」把手，也可以用面板上的數字輸入框微調。調好後按
// 「儲存」存成 JSON——跟 transform-gizmo.js 一樣，這個模組本身不會
// 改動遊戲任何真正的程式碼，JSON 只是記錄調整結果。
//
// 用法：
//   const gizmo = createDomPositionGizmoPanel({
//       pageName: 'game_quiz',
//       targets: [
//           { key: 'quizOptions', label: '答題選項區', el: document.getElementById('adv-options') },
//       ],
//   });
// =============================================================

function createDomPositionGizmoPanel(opts) {
    const { pageName, targets } = opts;
    const STEP = 2; // px

    const state = new Map();
    const inputs = new Map();

    const panel = document.createElement('div');
    panel.style.cssText = `
        position: fixed; right: 16px; top: 50%; transform: translateY(-50%); z-index: 99999;
        background: rgba(15,23,42,0.92); color: #e2e8f0; border-radius: 14px;
        padding: 14px 16px; font-family: 'Segoe UI', '微軟正黑體', sans-serif;
        font-size: 0.78rem; max-width: 300px; max-height: 80vh; overflow-y: auto;
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    `;

    const title = document.createElement('div');
    title.textContent = '🛠️ 畫面位置調整面板';
    title.style.cssText = 'font-size:0.95rem; font-weight:800; margin-bottom:6px; color:#ffde59;';
    panel.appendChild(title);

    const hint = document.createElement('div');
    hint.textContent = '直接拖曳畫面上的「⠿」把手，或用下面的數字調整；偏移量是疊加在原本排版上的像素位移，調好後按「儲存」。';
    hint.style.cssText = 'color:#94a3b8; margin-bottom:10px; line-height:1.5;';
    panel.appendChild(hint);

    function positionHandle(t) {
        const rect = t.el.getBoundingClientRect();
        t._gizmoHandle.style.left = (rect.left + rect.width / 2) + 'px';
        t._gizmoHandle.style.top = (rect.top - 6) + 'px';
    }

    function applyOffset(t) {
        const s = state.get(t.key);
        const base = t.el.dataset.gizmoBase || '';
        t.el.style.transform = (base ? base + ' ' : '') + `translate(${s.dx}px, ${s.dy}px)`;
        positionHandle(t);
        const io = inputs.get(t.key);
        if (io) { io.x.value = s.dx; io.y.value = s.dy; }
    }

    function makeAxisRow(labelText, axis, t) {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; align-items:center; gap:4px; margin-bottom:4px;';

        const axisLabel = document.createElement('span');
        axisLabel.textContent = labelText;
        axisLabel.style.cssText = 'width:16px; color:#64748b; font-weight:700;';
        row.appendChild(axisLabel);

        const minusBtn = document.createElement('button');
        minusBtn.textContent = '−';
        minusBtn.style.cssText = 'width:22px; height:22px; border:none; border-radius:6px; background:#334155; color:#fff; cursor:pointer; font-weight:800;';
        row.appendChild(minusBtn);

        const input = document.createElement('input');
        input.type = 'number';
        input.step = STEP;
        input.value = '0';
        input.style.cssText = 'width:62px; background:#1e293b; color:#fff; border:1px solid #334155; border-radius:6px; padding:3px 4px; text-align:center;';
        row.appendChild(input);

        const plusBtn = document.createElement('button');
        plusBtn.textContent = '+';
        plusBtn.style.cssText = minusBtn.style.cssText;
        row.appendChild(plusBtn);

        const suffixEl = document.createElement('span');
        suffixEl.textContent = 'px';
        suffixEl.style.cssText = 'color:#64748b;';
        row.appendChild(suffixEl);

        function set(v) {
            state.get(t.key)[axis] = v;
            applyOffset(t);
        }
        minusBtn.onclick = () => set(state.get(t.key)[axis] - STEP);
        plusBtn.onclick = () => set(state.get(t.key)[axis] + STEP);
        input.onchange = () => {
            const v = parseFloat(input.value);
            if (!isNaN(v)) set(v);
        };

        return { row, input };
    }

    targets.forEach(t => {
        state.set(t.key, { dx: 0, dy: 0 });

        // 🏆 一定要用 computed style 抓「目前實際生效」的 transform（可能
        // 來自 CSS class，例如 .task-options 的 translateY(-50%)），不能
        // 只看 el.style.transform（inline），否則之後整段覆寫會把 CSS
        // class 原本的置中效果蓋掉。computed 回來的會是 matrix(...)，跟
        // 我們自己疊加的 translate(dx,dy) 相乘完全等價於原本的位移。
        const computed = getComputedStyle(t.el).transform;
        t.el.dataset.gizmoBase = (computed && computed !== 'none') ? computed : '';

        const section = document.createElement('div');
        section.style.cssText = 'border-top:1px solid #334155; padding-top:8px; margin-top:8px;';

        const secTitle = document.createElement('div');
        secTitle.textContent = t.label + '（' + t.key + '）';
        secTitle.style.cssText = 'font-weight:700; margin-bottom:6px; color:#4facfe;';
        section.appendChild(secTitle);

        const xRow = makeAxisRow('X', 'dx', t);
        const yRow = makeAxisRow('Y', 'dy', t);
        section.appendChild(xRow.row);
        section.appendChild(yRow.row);
        inputs.set(t.key, { x: xRow.input, y: yRow.input });

        const resetBtn = document.createElement('button');
        resetBtn.textContent = '↺ 重設這個';
        resetBtn.style.cssText = 'margin-top:4px; width:100%; padding:4px; border:none; border-radius:6px; background:#475569; color:#fff; cursor:pointer; font-size:0.72rem;';
        resetBtn.onclick = () => {
            state.set(t.key, { dx: 0, dy: 0 });
            applyOffset(t);
        };
        section.appendChild(resetBtn);

        panel.appendChild(section);

        const handle = document.createElement('div');
        handle.textContent = '⠿ ' + t.label;
        handle.title = '拖曳移動「' + t.label + '」';
        handle.style.cssText = `
            position: fixed; z-index: 99998; cursor: move; user-select: none;
            background: rgba(0,0,0,0.78); color: #ffde59; font-size: 0.72rem;
            font-weight: 800; padding: 4px 8px; border-radius: 6px; white-space: nowrap;
            transform: translate(-50%, -100%);
        `;
        document.body.appendChild(handle);
        t._gizmoHandle = handle;

        let dragging = false, startX = 0, startY = 0, origDx = 0, origDy = 0;
        handle.addEventListener('mousedown', e => {
            dragging = true;
            startX = e.clientX; startY = e.clientY;
            const s = state.get(t.key);
            origDx = s.dx; origDy = s.dy;
            e.preventDefault();
        });
        window.addEventListener('mousemove', e => {
            if (!dragging) return;
            const s = state.get(t.key);
            s.dx = origDx + (e.clientX - startX);
            s.dy = origDy + (e.clientY - startY);
            applyOffset(t);
        });
        window.addEventListener('mouseup', () => { dragging = false; });

        applyOffset(t);
    });

    const saveNote = document.createElement('div');
    saveNote.style.cssText = 'color:#64748b; font-size:0.7rem; margin-top:10px; line-height:1.5;';
    saveNote.textContent = '儲存會跳瀏覽器存檔視窗（Chrome/Edge 可直接選到 static/preview/）；若瀏覽器不支援，會變成自動下載，請自己搬進 static/preview/。';
    panel.appendChild(saveNote);

    const saveBtn = document.createElement('button');
    saveBtn.textContent = '💾 儲存目前的調整';
    saveBtn.style.cssText = 'display:block; width:100%; margin-top:8px; padding:8px 10px; border:none; border-radius:8px; background:#00cdac; color:#fff; font-weight:800; cursor:pointer;';
    panel.appendChild(saveBtn);

    const statusEl = document.createElement('div');
    statusEl.style.cssText = 'margin-top:6px; color:#4ade80; font-weight:700; min-height:1em;';
    panel.appendChild(statusEl);

    async function handleSave() {
        const data = {
            page: pageName || 'unknown',
            savedAt: new Date().toISOString(),
            targets: {},
        };
        targets.forEach(t => {
            const s = state.get(t.key);
            data.targets[t.key] = { dx: s.dx, dy: s.dy };
        });
        const json = JSON.stringify(data, null, 2);
        const filename = (pageName || 'position') + '_position.json';

        if (window.showSaveFilePicker) {
            try {
                const fileHandle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: [{ description: 'JSON', accept: { 'application/json': ['.json'] } }],
                });
                const writable = await fileHandle.createWritable();
                await writable.write(json);
                await writable.close();
                statusEl.textContent = '✅ 已儲存：' + filename;
                return;
            } catch (e) {
                if (e && e.name === 'AbortError') {
                    statusEl.textContent = '已取消儲存。';
                    return;
                }
                // 不支援或出錯時往下 fallback 成自動下載
            }
        }

        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        statusEl.textContent = '✅ 已下載：' + filename + '（請手動搬進 static/preview/）';
    }
    saveBtn.onclick = handleSave;

    document.body.appendChild(panel);

    function loop() {
        targets.forEach(positionHandle);
        requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);

    return { update: () => targets.forEach(positionHandle) };
}
