// =============================================================
// 調整面板——給預覽頁用的通用「畫面位置」調整工具（2D DOM 版）
//
// 跟 static/js/transform-gizmo.js 是同一套思路（數字輸入框 + 存成
// JSON，給人之後手動讀、手動套回程式碼），但那個版本只能調 Three.js
// 3D 物件的 position/rotation；這個版本調的是用 CSS 排版的 2D 畫面
// 元素（答題選項區、商店版面這類 fixed/absolute/flex 排出來的畫面），
// 不是 3D 物件。
//
// 🏆 這裡用的是「視窗寬高百分比」（CSS 的 vw/vh 單位），不是固定像素。
// 原本第一版用固定 px 疊加偏移，使用者實測後發現：預覽頁螢幕跟實際
// 遊玩的螢幕比例不一樣時，同一組 px 數字在兩邊看起來的「比例位移」
// 完全不同（例如小螢幕上 87px 位移很明顯，大螢幕上幾乎看不出來）。
// 改成 vw/vh 之後，位移/尺寸都是「視窗寬或高的百分之幾」，不管螢幕
// 大小、長寬比怎麼變，看起來的相對位置都會一致。
//
// 做法：不去改動元素原本的 top/left/flex 排版邏輯，只在它原本已有的
// CSS transform（例如 .task-options 的 translateY(-50%)）後面疊加一個
// translate(dxPct vw, dyPct vh) 的百分比偏移。畫面上每個 target 旁邊
// 會出現一個可以直接拖曳的「⠿」把手，也可以用面板上的數字輸入框
// 微調。調好後按「儲存」存成 JSON——這個模組本身不會改動遊戲任何
// 真正的程式碼，JSON 只是記錄調整結果。
//
// 用法：
//   const gizmo = createDomPositionGizmoPanel({
//       pageName: 'game_quiz',
//       targets: [
//           { key: 'quizOptions', label: '答題選項區', el: document.getElementById('adv-options') },
//           // resizable: true 的 target 面板上會多出寬/高的數字輸入框，
//           // 畫面上也會多一個右下角可拖曳的縮放把手；寬高一樣是視窗
//           // 寬/高的百分之幾（寬用 vw，高用 vh），不是絕對像素值。
//           { key: 'shopInstructionBox', label: '手勢說明框', el: ..., resizable: true },
//           // initial：之前存過的 JSON 可以直接當起始值餵進來。
//           { key: 'x', label: '...', el: ..., initial: { dxPct: 4.5, dyPct: -0.9 } },
//       ],
//   });
// =============================================================

function createDomPositionGizmoPanel(opts) {
    const { pageName, targets } = opts;
    const STEP = 0.5; // 百分之幾（% of viewport width/height）

    const state = new Map();
    const inputs = new Map();

    const panel = document.createElement('div');
    panel.style.cssText = `
        position: fixed; left: 16px; bottom: 16px; z-index: 99999;
        background: rgba(15,23,42,0.92); color: #e2e8f0; border-radius: 14px;
        padding: 14px 16px; font-family: 'Segoe UI', '微軟正黑體', sans-serif;
        font-size: 0.78rem; max-width: 300px; max-height: 70vh; overflow-y: auto;
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    `;

    const title = document.createElement('div');
    title.textContent = '🛠️ 畫面位置調整面板（百分比）';
    title.style.cssText = 'font-size:0.95rem; font-weight:800; margin-bottom:6px; color:#ffde59;';
    panel.appendChild(title);

    const hint = document.createElement('div');
    hint.textContent = '直接拖曳畫面上的「⠿」把手，或用下面的數字調整；單位是視窗寬/高的百分之幾（vw/vh），不是固定像素，不同螢幕比例看起來的相對位置會一致。部分 target 右下角還有黃色「↘」把手可以拖曳縮放寬高。調好後按「儲存」。';
    hint.style.cssText = 'color:#94a3b8; margin-bottom:10px; line-height:1.5;';
    panel.appendChild(hint);

    function positionHandle(t) {
        const rect = t.el.getBoundingClientRect();
        t._gizmoHandle.style.left = (rect.left + rect.width / 2) + 'px';
        t._gizmoHandle.style.top = (rect.top - 6) + 'px';
        if (t.resizable && t._gizmoResizeHandle) {
            t._gizmoResizeHandle.style.left = rect.right + 'px';
            t._gizmoResizeHandle.style.top = rect.bottom + 'px';
        }
    }

    function fmt(v) {
        return Math.round(v * 100) / 100; // 四捨五入到小數點後 2 位，避免存出一長串浮點數誤差
    }

    function applyOffset(t) {
        const s = state.get(t.key);
        const base = t.el.dataset.gizmoBase || '';
        t.el.style.transform = (base ? base + ' ' : '') + `translate(${fmt(s.dxPct)}vw, ${fmt(s.dyPct)}vh)`;
        if (t.resizable) {
            t.el.style.width = fmt(s.widthPct) + 'vw';
            t.el.style.height = fmt(s.heightPct) + 'vh';
        }
        positionHandle(t);
        const io = inputs.get(t.key);
        if (io) {
            io.x.value = fmt(s.dxPct); io.y.value = fmt(s.dyPct);
            if (t.resizable) { io.w.value = fmt(s.widthPct); io.h.value = fmt(s.heightPct); }
        }
    }

    function makeRow(labelText, axis, t, opts) {
        opts = opts || {};
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; align-items:center; gap:4px; margin-bottom:4px;';

        const axisLabel = document.createElement('span');
        axisLabel.textContent = labelText;
        axisLabel.style.cssText = 'width:20px; color:#64748b; font-weight:700;';
        row.appendChild(axisLabel);

        const minusBtn = document.createElement('button');
        minusBtn.textContent = '−';
        minusBtn.style.cssText = 'width:22px; height:22px; border:none; border-radius:6px; background:#334155; color:#fff; cursor:pointer; font-weight:800;';
        row.appendChild(minusBtn);

        const input = document.createElement('input');
        input.type = 'number';
        input.step = STEP;
        if (opts.min !== undefined) input.min = opts.min;
        input.style.cssText = 'width:62px; background:#1e293b; color:#fff; border:1px solid #334155; border-radius:6px; padding:3px 4px; text-align:center;';
        row.appendChild(input);

        const plusBtn = document.createElement('button');
        plusBtn.textContent = '+';
        plusBtn.style.cssText = minusBtn.style.cssText;
        row.appendChild(plusBtn);

        const suffixEl = document.createElement('span');
        suffixEl.textContent = '%';
        suffixEl.style.cssText = 'color:#64748b;';
        row.appendChild(suffixEl);

        function set(v) {
            if (opts.min !== undefined) v = Math.max(opts.min, v);
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
        // 🏆 initial：之前存過的 JSON 可以直接當起始值餵進來（例如
        // { dxPct: 4.5, dyPct: -0.9 }），讓這頁重新整理後就直接顯示
        // 調整過的結果，不用每次都手動重新拖一次——面板上的數字輸入框
        // 也會正確顯示這組起始值，不是看起來調好了、面板卻還停在 0。
        const initial = t.initial || {};
        state.set(t.key, { dxPct: initial.dxPct || 0, dyPct: initial.dyPct || 0 });

        // 🏆 一定要用 computed style 抓「目前實際生效」的 transform（可能
        // 來自 CSS class，例如 .task-options 的 translateY(-50%)），不能
        // 只看 el.style.transform（inline），否則之後整段覆寫會把 CSS
        // class 原本的置中效果蓋掉。computed 回來的會是 matrix(...)，跟
        // 我們自己疊加的 translate(...) 相乘完全等價於原本的位移。
        const computed = getComputedStyle(t.el).transform;
        t.el.dataset.gizmoBase = (computed && computed !== 'none') ? computed : '';

        if (t.resizable) {
            // 🏆 把目前「沒有寫死寬高、靠內容撐開」的實際渲染尺寸，先
            // 原封不動凍結成明確的 width/height（換算成視窗寬高的百分
            // 之幾），之後才能用這組數字當基準微調——順便改成
            // border-box，這樣 width/height 才會跟
            // getBoundingClientRect() 量出來的、包含 padding 的總尺寸
            // 一致，不會每次調整都因為 padding 被重複加算而跳一下。
            // 如果有給 initial.widthPct/heightPct（之前存過的 JSON），
            // 直接拿來當起始值，不用再從目前渲染尺寸重新量一次。
            const rect = t.el.getBoundingClientRect();
            t.el.style.boxSizing = 'border-box';
            state.get(t.key).widthPct = initial.widthPct || fmt(rect.width / window.innerWidth * 100);
            state.get(t.key).heightPct = initial.heightPct || fmt(rect.height / window.innerHeight * 100);
        }

        const section = document.createElement('div');
        section.style.cssText = 'border-top:1px solid #334155; padding-top:8px; margin-top:8px;';

        const secTitle = document.createElement('div');
        secTitle.textContent = t.label + '（' + t.key + '）';
        secTitle.style.cssText = 'font-weight:700; margin-bottom:6px; color:#4facfe;';
        section.appendChild(secTitle);

        const xRow = makeRow('X', 'dxPct', t);
        const yRow = makeRow('Y', 'dyPct', t);
        section.appendChild(xRow.row);
        section.appendChild(yRow.row);
        const io = { x: xRow.input, y: yRow.input };

        if (t.resizable) {
            const wRow = makeRow('寬', 'widthPct', t, { min: 1 });
            const hRow = makeRow('高', 'heightPct', t, { min: 1 });
            section.appendChild(wRow.row);
            section.appendChild(hRow.row);
            io.w = wRow.input;
            io.h = hRow.input;
        }
        inputs.set(t.key, io);

        const resetBtn = document.createElement('button');
        resetBtn.textContent = '↺ 重設這個';
        resetBtn.style.cssText = 'margin-top:4px; width:100%; padding:4px; border:none; border-radius:6px; background:#475569; color:#fff; cursor:pointer; font-size:0.72rem;';
        resetBtn.onclick = () => {
            const s = state.get(t.key);
            s.dxPct = 0; s.dyPct = 0;
            if (t.resizable) {
                t.el.style.width = ''; t.el.style.height = '';
                const rect = t.el.getBoundingClientRect();
                s.widthPct = fmt(rect.width / window.innerWidth * 100);
                s.heightPct = fmt(rect.height / window.innerHeight * 100);
            }
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

        if (t.resizable) {
            const resizeHandle = document.createElement('div');
            resizeHandle.textContent = '↘';
            resizeHandle.title = '拖曳縮放「' + t.label + '」';
            resizeHandle.style.cssText = `
                position: fixed; z-index: 99998; cursor: nwse-resize; user-select: none;
                background: #ffde59; color: #1e293b; font-size: 0.7rem; font-weight: 900;
                width: 18px; height: 18px; border-radius: 4px; display: flex;
                align-items: center; justify-content: center;
                transform: translate(-50%, -50%);
            `;
            document.body.appendChild(resizeHandle);
            t._gizmoResizeHandle = resizeHandle;

            // 拖曳時把滑鼠移動的像素量換算成視窗寬/高的百分之幾，這樣
            // 存出來的數字才是真正的百分比，不是換了個名字的像素值。
            let resizing = false, rStartX = 0, rStartY = 0, origW = 0, origH = 0;
            resizeHandle.addEventListener('mousedown', e => {
                resizing = true;
                rStartX = e.clientX; rStartY = e.clientY;
                const s = state.get(t.key);
                origW = s.widthPct; origH = s.heightPct;
                e.preventDefault();
                e.stopPropagation();
            });
            window.addEventListener('mousemove', e => {
                if (!resizing) return;
                const s = state.get(t.key);
                s.widthPct = Math.max(1, origW + (e.clientX - rStartX) / window.innerWidth * 100);
                s.heightPct = Math.max(1, origH + (e.clientY - rStartY) / window.innerHeight * 100);
                applyOffset(t);
            });
            window.addEventListener('mouseup', () => { resizing = false; });
        }

        let dragging = false, startX = 0, startY = 0, origDx = 0, origDy = 0;
        handle.addEventListener('mousedown', e => {
            dragging = true;
            startX = e.clientX; startY = e.clientY;
            const s = state.get(t.key);
            origDx = s.dxPct; origDy = s.dyPct;
            e.preventDefault();
        });
        window.addEventListener('mousemove', e => {
            if (!dragging) return;
            const s = state.get(t.key);
            s.dxPct = origDx + (e.clientX - startX) / window.innerWidth * 100;
            s.dyPct = origDy + (e.clientY - startY) / window.innerHeight * 100;
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
            // 存一下當時的視窗尺寸純粹當參考記錄（例如之後想知道這組
            // 百分比是在什麼比例的螢幕下調的），套回程式碼時不需要
            // 這個欄位，百分比本身就是跨螢幕一致的。
            viewportAtSave: { width: window.innerWidth, height: window.innerHeight },
            targets: {},
        };
        targets.forEach(t => {
            const s = state.get(t.key);
            data.targets[t.key] = t.resizable
                ? { dxPct: fmt(s.dxPct), dyPct: fmt(s.dyPct), widthPct: fmt(s.widthPct), heightPct: fmt(s.heightPct) }
                : { dxPct: fmt(s.dxPct), dyPct: fmt(s.dyPct) };
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
