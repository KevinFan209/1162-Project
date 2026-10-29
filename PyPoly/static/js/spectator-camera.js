// =============================================================
// 觀戰者「忙碌中要不要排隊」與「鏡頭目標計算」
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_spectator_busy.html 要用同一份程式碼驗證 #9（原本忙碌中會被
// 強制搶畫面、鏡頭瞬間硬切沒有過渡）的修法。
//
// ⚠️ 範圍縮小：enterSpectatorMode_Internal() 本身還包含敘述打字機
// 效果、處罰可見性強制、背景球載入等跟 #9 這次修的 bug（忙碌中不該
// 搶畫面、鏡頭要補間不要瞬間跳）無關的邏輯，這次只抽出真正被 #9
// 改動到的兩段純計算，不搬整個函式——那些副作用邏輯繼續留在
// game.html，沒有被這個模組取代。
//
// computeSpectatorCameraTarget() 只回傳目標位置/注視點/是否跳過鏡頭
// 移動，實際的 gsap.to(camera.position, {...}) 補間呼叫（有副作用）
// 留在 game.html 原處，不適合搬進純函式模組。
// =============================================================

function isUiStateBusy(uiState, busyStates) {
    busyStates = busyStates || ["PURCHASE_DECISION", "SHOP_BROWSING", "SHOP_CONFIRMING"];
    return busyStates.includes(uiState);
}

function computeSpectatorCameraTarget(phase, data, playerModels) {
    let targetLook = new THREE.Vector3(0, 1.5, -10);
    let targetCamPos = new THREE.Vector3(0, 1.5, 0);

    if (phase === 'PUNISH' || phase === 'PUNISH_SKIP') {
        const targetModel = playerModels[data.user];
        if (targetModel) {
            const forward = new THREE.Vector3(0, 0, 1).applyQuaternion(targetModel.quaternion);

            targetCamPos = targetModel.position.clone()
                .add(new THREE.Vector3(0, 2.5, 0))
                .addScaledVector(forward, 4.9);

            targetLook = targetModel.position.clone()
                .add(new THREE.Vector3(0, 2.1, 0));
        }
    }

    const skipCameraMove = ['JAIL_ANIM', 'ITEM_STEAL_ANIM', 'TOLL_ANIM'].includes(phase);

    return { targetCamPos, targetLook, skipCameraMove };
}
