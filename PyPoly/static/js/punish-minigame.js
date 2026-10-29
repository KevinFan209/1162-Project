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

function play3DJumpAnimation(model) {
    const origY = model.position.y;
    // 身體往上跳
    gsap.to(model.position, {
        y: origY + 1.2,
        duration: 0.25,
        yoyo: true,
        repeat: 1,
        ease: "power1.out"
    });

    // 雙手揮動 (簡單的開合跳手臂動作)
    // 🏆 修正方向：原本的正負號會讓垂下的手臂往身體內側甩（跟開合跳
    // 張開的動作相反），改成讓兩隻手臂同時往身體外側甩開。
    const leftArm = model.getObjectByName("leftArm");
    const rightArm = model.getObjectByName("rightArm");
    if (leftArm && rightArm) {
        gsap.to(leftArm.rotation, { z: -Math.PI / 1.5, duration: 0.25, yoyo: true, repeat: 1 });
        gsap.to(rightArm.rotation, { z: Math.PI / 1.5, duration: 0.25, yoyo: true, repeat: 1 });
    }
}
