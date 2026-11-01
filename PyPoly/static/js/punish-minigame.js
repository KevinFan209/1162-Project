// =============================================================
// 開合跳處罰小遊戲——跳躍動畫
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_punish.html 要用同一份程式碼。
//
// 這個函式本來就是「給一個模型就播放一次跳躍動畫」的乾淨函式，不讀
// 任何全域變數、不靠 socket——跟 player-model.js 的
// createCustomBoxCharacter() 一樣是原樣搬移，沒有任何行為改變。
//
// ⚠️ 真正「算跳了幾次」是連 /ws/vision/jumping 即時 WebSocket 給後端
// 的姿勢辨識算的，`payToSkipJumping()`（付費略過）又牽涉金錢/回合
// 推進這些對局限定的狀態，兩者都不在這次抽取範圍，繼續留在
// game.html。預覽頁只能用按鈕模擬「跳了一次」，不會真的辨識姿勢。
// =============================================================

// 🏆 修復：原本每次呼叫都用 yoyo 讓動畫「回到呼叫當下那一刻的值」，
// 而且重複呼叫時不會先停掉前一個還在跑的 tween。如果跳的頻率比動畫
// 本身的 0.5 秒（上升 0.25s + 下降 0.25s）還快，新的 tween 會蓋掉還沒
// 跑完的舊 tween，把 body/手臂停在尚未歸位的中間值；下一次跳躍又拿
// 這個已經偏移的中間值當「原始位置」繼續疊加，越跳身體越往上飄、
// 手臂也可能卡在轉到一半的角度回不去（對局中觀戰者看對手開合跳正是
// 這個路徑：update_pose_count_broadcast 收到後端 broadcast 太快就會
// 連續觸發）。
//
// 改成：只在模型第一次做這個動作時，把「真正的靜止高度/角度」記錄在
// model.userData／手臂.userData 上，之後永遠拿這組記錄值當基準（不會
// 因為中途被打斷而跟著跑掉）；每次呼叫前先 kill 掉舊的 tween，並且
// 用「上升→回到記錄值」兩段式時間軸取代 yoyo，保證動畫結束時一定
// 精確回到原位，不管中途被打斷幾次、呼叫得多快都不會累積誤差。
function play3DJumpAnimation(model) {
    if (model.userData.punishRestY === undefined) {
        model.userData.punishRestY = model.position.y;
    }
    const restY = model.userData.punishRestY;

    gsap.killTweensOf(model.position);
    gsap.timeline()
        .to(model.position, { y: restY + 1.2, duration: 0.25, ease: "power1.out" })
        .to(model.position, { y: restY, duration: 0.25, ease: "power1.in" });

    // 雙手揮動 (簡單的開合跳手臂動作)
    // 🏆 修正方向：原本的正負號會讓垂下的手臂往身體內側甩（跟開合跳
    // 張開的動作相反），改成讓兩隻手臂同時往身體外側甩開。
    const leftArm = model.getObjectByName("leftArm");
    const rightArm = model.getObjectByName("rightArm");
    if (leftArm && rightArm) {
        if (leftArm.userData.punishRestZ === undefined) leftArm.userData.punishRestZ = leftArm.rotation.z;
        if (rightArm.userData.punishRestZ === undefined) rightArm.userData.punishRestZ = rightArm.rotation.z;
        const leftRestZ = leftArm.userData.punishRestZ;
        const rightRestZ = rightArm.userData.punishRestZ;

        gsap.killTweensOf(leftArm.rotation);
        gsap.killTweensOf(rightArm.rotation);
        gsap.timeline()
            .to(leftArm.rotation, { z: leftRestZ - Math.PI / 1.5, duration: 0.25 })
            .to(leftArm.rotation, { z: leftRestZ, duration: 0.25 });
        gsap.timeline()
            .to(rightArm.rotation, { z: rightRestZ + Math.PI / 1.5, duration: 0.25 })
            .to(rightArm.rotation, { z: rightRestZ, duration: 0.25 });
    }
}
