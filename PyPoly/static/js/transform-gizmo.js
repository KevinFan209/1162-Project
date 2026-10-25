// =============================================================
// 調整面板——給預覽頁用的通用「位置/旋轉」調整工具
//
// 不是遊戲正式功能，只給 static/preview/ 底下的動畫預覽頁用：針對
// 幾個指定的 Object3D（例如角色的手臂、鏟子），即時顯示座標與角度，
// 並提供數字輸入框 + 微調按鈕讓使用者直接拖拉/點按調整，調整完可以
// 按「儲存」把目前所有 target 的 position/rotation 存成一份 JSON。
//
// 用法（跟 static/js 其他模組一樣，純函式、吃參數、不汙染全域）：
//   const gizmo = createTransformGizmoPanel({
//       renderer, camera,
//       pageName: 'game_purchase',
//       targets: [
//           { key: 'rightArm', label: '右手臂', object3D: rightArmMesh },
//           { key: 'shovel', label: '鏟子', object3D: debugShovel },
//       ],
//   });
//   // 在既有的 animate() 迴圈裡每個 frame 呼叫一次：
//   gizmo.update();
//
// 存出來的 JSON 只是給人之後手動讀、手動套回程式碼用的「調整結果
// 記錄」，這個模組本身不會改動遊戲任何真正的程式碼或連後端。
// =============================================================

function createTransformGizmoPanel(opts) {
    const { renderer, camera, targets, pageName } = opts;
    const POS_STEP = 0.05;
    const ROT_STEP_DEG = 5;

    const panel = document.createElement('div');
    panel.style.cssText = `
        position: fixed; left: 16px; bottom: 16px; z-index: 20;
        background: rgba(15,23,42,0.92); color: #e2e8f0; border-radius: 14px;
        padding: 14px 16px; font-family: 'Segoe UI', '微軟正黑體', sans-serif;
        font-size: 0.78rem; max-width: 300px; max-height: 70vh; overflow-y: auto;
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    `;

    const title = document.createElement('div');
    title.textContent = '🛠️ 座標調整面板';
    title.style.cssText = 'font-size:0.95rem; font-weight:800; margin-bottom:6px; color:#ffde59;';
    panel.appendChild(title);

    const hint = document.createElement('div');
    hint.textContent = '調整下面的數字或按鈕，畫面上的物件會即時跟著動。調好後按「儲存」。';
    hint.style.cssText = 'color:#94a3b8; margin-bottom:10px; line-height:1.5;';
    panel.appendChild(hint);

    const labelEls = [];

    function makeAxisRow(axisName, getVal, setVal, step, suffix) {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; align-items:center; gap:4px; margin-bottom:4px;';

        const axisLabel = document.createElement('span');
        axisLabel.textContent = axisName;
        axisLabel.style.cssText = 'width:16px; color:#64748b; font-weight:700;';
        row.appendChild(axisLabel);

        const minusBtn = document.createElement('button');
        minusBtn.textContent = '−';
        minusBtn.style.cssText = 'width:22px; height:22px; border:none; border-radius:6px; background:#334155; color:#fff; cursor:pointer; font-weight:800;';
        row.appendChild(minusBtn);

        const input = document.createElement('input');
        input.type = 'number';
        input.step = step;
        input.value = getVal().toFixed(2);
        input.style.cssText = 'width:62px; background:#1e293b; color:#fff; border:1px solid #334155; border-radius:6px; padding:3px 4px; text-align:center;';
        row.appendChild(input);

        const plusBtn = document.createElement('button');
        plusBtn.textContent = '+';
        plusBtn.style.cssText = minusBtn.style.cssText;
        row.appendChild(plusBtn);

        if (suffix) {
            const suffixEl = document.createElement('span');
            suffixEl.textContent = suffix;
            suffixEl.style.cssText = 'color:#64748b;';
            row.appendChild(suffixEl);
        }

        function apply(v) {
            setVal(v);
            input.value = v.toFixed(2);
        }
        minusBtn.onclick = () => apply(getVal() - step);
        plusBtn.onclick = () => apply(getVal() + step);
        input.onchange = () => {
            const v = parseFloat(input.value);
            if (!isNaN(v)) apply(v);
        };

        return row;
    }

    targets.forEach(t => {
        const section = document.createElement('div');
        section.style.cssText = 'border-top:1px solid #334155; padding-top:8px; margin-top:8px;';

        const secTitle = document.createElement('div');
        secTitle.textContent = t.label + '（' + t.key + '）';
        secTitle.style.cssText = 'font-weight:700; margin-bottom:6px; color:#4facfe;';
        section.appendChild(secTitle);

        const posWrap = document.createElement('div');
        posWrap.appendChild(makeAxisRow('X', () => t.object3D.position.x, v => { t.object3D.position.x = v; }, POS_STEP, ''));
        posWrap.appendChild(makeAxisRow('Y', () => t.object3D.position.y, v => { t.object3D.position.y = v; }, POS_STEP, ''));
        posWrap.appendChild(makeAxisRow('Z', () => t.object3D.position.z, v => { t.object3D.position.z = v; }, POS_STEP, ''));
        section.appendChild(posWrap);

        const rotWrap = document.createElement('div');
        rotWrap.style.marginTop = '4px';
        const toDeg = r => r * 180 / Math.PI;
        const toRad = d => d * Math.PI / 180;
        rotWrap.appendChild(makeAxisRow('RX', () => toDeg(t.object3D.rotation.x), v => { t.object3D.rotation.x = toRad(v); }, ROT_STEP_DEG, '°'));
        rotWrap.appendChild(makeAxisRow('RY', () => toDeg(t.object3D.rotation.y), v => { t.object3D.rotation.y = toRad(v); }, ROT_STEP_DEG, '°'));
        rotWrap.appendChild(makeAxisRow('RZ', () => toDeg(t.object3D.rotation.z), v => { t.object3D.rotation.z = toRad(v); }, ROT_STEP_DEG, '°'));
        section.appendChild(rotWrap);

        panel.appendChild(section);

        const floatLabel = document.createElement('div');
        floatLabel.style.cssText = `
            position: fixed; z-index: 15; pointer-events: none;
            background: rgba(0,0,0,0.75); color: #ffde59; font-size: 0.68rem;
            font-weight: 700; padding: 3px 6px; border-radius: 6px;
            white-space: pre; transform: translate(-50%, -100%);
        `;
        document.body.appendChild(floatLabel);
        labelEls.push({ target: t, el: floatLabel });
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
            data.targets[t.key] = {
                position: { x: t.object3D.position.x, y: t.object3D.position.y, z: t.object3D.position.z },
                rotation: { x: t.object3D.rotation.x, y: t.object3D.rotation.y, z: t.object3D.rotation.z },
            };
        });
        const json = JSON.stringify(data, null, 2);
        const filename = (pageName || 'transform') + '_transform.json';

        if (window.showSaveFilePicker) {
            try {
                const handle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: [{ description: 'JSON', accept: { 'application/json': ['.json'] } }],
                });
                const writable = await handle.createWritable();
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

    const vec = new THREE.Vector3();
    function update() {
        const rect = renderer.domElement.getBoundingClientRect();
        labelEls.forEach(({ target, el }) => {
            target.object3D.getWorldPosition(vec);
            const p = vec.clone().project(camera);
            const x = (p.x * 0.5 + 0.5) * rect.width + rect.left;
            const y = (-p.y * 0.5 + 0.5) * rect.height + rect.top;
            el.style.left = x + 'px';
            el.style.top = (y - 10) + 'px';
            el.style.display = (p.z > 1 || p.z < -1) ? 'none' : 'block';
            const pos = target.object3D.position;
            const rot = target.object3D.rotation;
            el.textContent = target.label + '\n' +
                'pos(' + pos.x.toFixed(2) + ', ' + pos.y.toFixed(2) + ', ' + pos.z.toFixed(2) + ')\n' +
                'rot(' + (rot.x * 180 / Math.PI).toFixed(0) + '°, ' + (rot.y * 180 / Math.PI).toFixed(0) + '°, ' + (rot.z * 180 / Math.PI).toFixed(0) + '°)';
        });
    }

    return { update };
}
