// =============================================================
// 過路費／監獄／道具偷竊動畫
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_events.html 要用同一份程式碼——複製一份的話，日後改動畫效果
// 就得記得改兩處，遲早變成「預覽好看但遊戲裡不是那樣」。
//
// 這三支在 game.html 裡本來就已經是「對自己跟觀戰者都呼叫同一份、
// 內部沒有 socket 呼叫」的乾淨函式，只是讀了一堆全域變數
// （scene / camera / playerModels / allTileMeshes / mapBlocks /
// playerCurrentIndex / window.landOwnership / panoSphere /
// window.isSpectating...）。現在全部包進第一個參數 ctx 傳入，行為
// 完全相同。ctx 的形狀：
//   {
//     scene, camera, playerModels, allTileMeshes, mapBlocks,
//     playerCurrentIndex, landOwnership,       // 查地主/格子位置用
//     panoSphere,                               // 可以是 null
//     myName, isSpectating,                     // 決定要不要動鏡頭
//     getPlayerLandColor(ownerName),             // 回傳該玩家的代表色
//     setBoardVisibility(isVisible, specificIdx),
//     showNotice(msg, position, duration),       // 選填，預設 no-op
//     playSfx(key),                              // 選填，預設 no-op
//   }
// =============================================================

function createJailCage() {
    const group = new THREE.Group();
    const ironMat = new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.9, roughness: 0.4 });

    const baseGeo = new THREE.BoxGeometry(4.8, 0.4, 4.8);
    const base = new THREE.Mesh(baseGeo, ironMat);
    base.position.y = 0.2;
    group.add(base);

    const top = new THREE.Mesh(baseGeo, ironMat);
    top.position.y = 4.5;
    group.add(top);

    const barGeo = new THREE.CylinderGeometry(0.18, 0.18, 4.3, 8);
    const positions = [
        [-2.2, -2.2], [-2.2, 0], [-2.2, 2.2],
        [ 2.2, -2.2], [ 2.2, 0], [ 2.2, 2.2],
        [ 0,   -2.2]
    ];
    positions.forEach(pos => {
        const bar = new THREE.Mesh(barGeo, ironMat);
        bar.position.set(pos[0], 2.35, pos[1]);
        group.add(bar);
    });

    return group;
}

function createShovel() {
    const group = new THREE.Group();
    const handleGeo = new THREE.CylinderGeometry(0.05, 0.05, 1.2, 8);
    const handleMat = new THREE.MeshStandardMaterial({ color: 0x8b4513 });
    const handle = new THREE.Mesh(handleGeo, handleMat);
    group.add(handle);
    const headGeo = new THREE.BoxGeometry(0.3, 0.4, 0.05);
    const headMat = new THREE.MeshStandardMaterial({ color: 0xaaaaaa, metalness: 0.8 });
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.y = -0.6;
    group.add(head);
    return group;
}

// 專為偷竊戰鬥設計的跳字特效（乾淨、清晰、不破圖）
function spawnCombatText(side, text, color) {
    const el = document.createElement('div');
    el.innerHTML = text;

    const offsetX = (Math.random() - 0.5) * 40;
    const offsetY = (Math.random() - 0.5) * 40;

    el.style.cssText = `
        position: fixed;
        top: calc(50% + ${offsetY}px);
        left: calc(${side === 'left' ? '30%' : '70%'} + ${offsetX}px);
        transform: translate(-50%, -50%) scale(0.5);
        background: ${color};
        color: white;
        padding: 10px 25px;
        border-radius: 50px;
        border: 4px solid white;
        font-size: 2.2rem;
        font-weight: 900;
        z-index: 100000;
        opacity: 0;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        pointer-events: none;
    `;
    document.body.appendChild(el);

    gsap.to(el, { opacity: 1, scale: 1.2, duration: 0.2, ease: "back.out(2)" });
    gsap.to(el, { top: "35%", opacity: 0, duration: 0.8, delay: 0.6, ease: "power1.in", onComplete: () => el.remove() });
}

function _noop() {}

async function playTollAnimationCore(ctx, payerName, ownerName, tollAmount, usedItem, tileIdx) {
    const showNotice = ctx.showNotice || _noop;
    const playSfx = ctx.playSfx || _noop;
    const { scene, camera, playerModels, allTileMeshes, mapBlocks, landOwnership, panoSphere, myName, isSpectating, getPlayerLandColor, setBoardVisibility } = ctx;

    const payerModel = playerModels[payerName];
    const ownerModel = playerModels[ownerName];
    if (!payerModel || !ownerModel) return;

    // 🏆 在動畫開始前，強制刷新這格土地與房子的顏色，保證 100% 同步
    const landData = landOwnership[tileIdx];
    if (landData) {
        const ownerColor = getPlayerLandColor(landData.owner);
        if (allTileMeshes[tileIdx]) allTileMeshes[tileIdx].material.color.set(ownerColor);
        const house = scene.getObjectByName("house_" + tileIdx);
        if (house) {
            house.children.forEach(c => {
                if (c.geometry && c.geometry.type === 'ConeGeometry') {
                    c.material.color.set(ownerColor);
                    c.material.needsUpdate = true;
                }
            });
        }
    }

    payerModel.visible = true;
    ownerModel.visible = true;

    const payerHead = payerModel.getObjectByName("head");
    const ownerHead = ownerModel.getObjectByName("head");
    if (payerHead) payerHead.visible = true;
    if (ownerHead) ownerHead.visible = true;

    const existingHouse = scene.getObjectByName("house_" + tileIdx);
    if (existingHouse) existingHouse.visible = true;

    scene.background = null;
    if (panoSphere) { panoSphere.visible = true; panoSphere.material.opacity = 1; }

    setBoardVisibility(false, tileIdx);

    showNotice("💸 支付/收取過路費中...", "bottom", 2500);

    const origPayerPos = payerModel.position.clone();
    const origPayerRot = payerModel.rotation.clone();
    const origOwnerPos = ownerModel.position.clone();
    const origOwnerRot = ownerModel.rotation.clone();

    const centerPos = mapBlocks[tileIdx].clone();
    payerModel.position.set(centerPos.x - 1.2, centerPos.y, centerPos.z);
    ownerModel.position.set(centerPos.x + 1.2, centerPos.y, centerPos.z);

    payerModel.lookAt(ownerModel.position.x, ownerModel.position.y, ownerModel.position.z + 5);
    ownerModel.lookAt(payerModel.position.x, payerModel.position.y, payerModel.position.z + 5);

    payerModel.visible = true;
    ownerModel.visible = true;

    if (payerName === myName || isSpectating) {
        camera.layers.enable(0); camera.layers.enable(1);
        camera.position.set(centerPos.x, centerPos.y + 5.0, centerPos.z + 9);
        camera.lookAt(centerPos.x, centerPos.y + 1, centerPos.z);
    }

    await new Promise(res => {
        const tl = gsap.timeline({ onComplete: res });
        tl.to(payerModel.rotation, { x: 0.3, duration: 0.3, yoyo: true, repeat: 1 })
          .add(() => {
              if (usedItem) {
                  spawnCombatText('left', "🛡️ 免疫", "#4facfe");
                  spawnCombatText('right', "💢 沒收到錢", "#94a3b8");
                  gsap.to(ownerModel.rotation, { z: 0.3, duration: 0.2, yoyo: true, repeat: 3 });
              } else {
                  spawnCombatText('left', `💸 -$${tollAmount}`, "#ff4757");
                  spawnCombatText('right', `🤑 +$${tollAmount}`, "#00cdac");
                  gsap.to(ownerModel.position, { y: ownerModel.position.y + 0.8, duration: 0.3, yoyo: true, repeat: 1 });
              }
          })
          .to({}, { duration: 2.0 });
    });

    payerModel.visible = false;
    ownerModel.visible = false;
    setBoardVisibility(false);
    if (allTileMeshes[tileIdx]) allTileMeshes[tileIdx].visible = false;
    if (existingHouse) existingHouse.visible = false;

    if (payerName === myName && !isSpectating) {
        if (payerHead) payerHead.visible = false;
    }

    payerModel.position.copy(origPayerPos); payerModel.rotation.copy(origPayerRot);
    ownerModel.position.copy(origOwnerPos); ownerModel.rotation.copy(origOwnerRot);
}

async function playJailAnimationCore(ctx, playerName, tileIdx) {
    const showNotice = ctx.showNotice || _noop;
    const playSfx = ctx.playSfx || _noop;
    const { scene, camera, playerModels, allTileMeshes, mapBlocks, panoSphere, myName, isSpectating, setBoardVisibility } = ctx;

    const model = playerModels[playerName];
    if (!model) return;
    playSfx('jail');

    scene.background = new THREE.Color(0xf1f5f9);
    if (panoSphere) { panoSphere.visible = false; panoSphere.material.opacity = 0; }
    setBoardVisibility(false, tileIdx);

    model.visible = true;
    const head = model.getObjectByName("head");
    if (head) head.visible = true;

    const existingHouse = scene.getObjectByName("house_" + tileIdx);
    if (existingHouse) existingHouse.visible = true;

    const origPos = model.position.clone();
    const origRot = model.rotation.clone();
    const centerPos = mapBlocks[tileIdx].clone();

    const targetTile = allTileMeshes[tileIdx];
    if (targetTile) {
        gsap.to(targetTile.scale, { x: 1.3, z: 1.3, duration: 0.5, ease: "back.out(1.5)" });
    }

    model.position.set(centerPos.x, centerPos.y, centerPos.z);
    model.lookAt(centerPos.x, centerPos.y, centerPos.z + 10);

    let origCamPos = camera.position.clone();
    let origCamQuat = camera.quaternion.clone();

    if (playerName === myName || isSpectating) {
        camera.layers.enable(0); camera.layers.enable(1);
        camera.position.set(centerPos.x, centerPos.y + 2.5, centerPos.z + 8.5);
        camera.lookAt(centerPos.x, centerPos.y + 2.0, centerPos.z);
        origCamPos = camera.position.clone();
    }

    const cage = createJailCage();
    cage.position.set(centerPos.x, centerPos.y + 15, centerPos.z);
    scene.add(cage);

    const tearsGroup = new THREE.Group();
    const tearGeo = new THREE.SphereGeometry(0.06, 6, 6);
    const tearMat = new THREE.MeshBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.8 });
    for (let i = 0; i < 12; i++) {
        const t = new THREE.Mesh(tearGeo, tearMat);
        t.position.set((Math.random() - 0.5) * 0.6, 0, 0.45);
        tearsGroup.add(t);
    }
    tearsGroup.visible = false;
    if (head) head.add(tearsGroup);

    showNotice("⛓️ 慘遭逮捕！下回合禁賽", "bottom", 4500);

    await new Promise(res => {
        const tl = gsap.timeline({ onComplete: res });

        tl.to(cage.position, { y: centerPos.y, duration: 0.7, ease: "power4.in" })
          .add(() => {
              if (playerName === myName || isSpectating) {
                  const shakeObj = { val: 0 };
                  gsap.to(shakeObj, {
                      val: 1, duration: 0.4,
                      onUpdate: () => {
                          camera.position.y = origCamPos.y + (Math.random() - 0.5) * 1.5;
                          camera.position.x = origCamPos.x + (Math.random() - 0.5) * 1.5;
                      },
                      onComplete: () => { camera.position.copy(origCamPos); }
                  });
              }

              gsap.to(model.scale, { y: 0.4, x: 2.4, z: 2.4, duration: 0.15, yoyo: true, repeat: 1 });
              gsap.to(model.rotation, { y: Math.PI * 6, duration: 1.5, ease: "power2.out", delay: 0.15 });

              tearsGroup.visible = true;
              tearsGroup.children.forEach(t => {
                  gsap.to(t.position, {
                      y: -1.0 - Math.random(),
                      duration: 0.4 + Math.random() * 0.3,
                      repeat: -1,
                      ease: "power1.in"
                  });
                  gsap.to(t.material, {
                      opacity: 0,
                      duration: 0.4 + Math.random() * 0.3,
                      repeat: -1,
                      ease: "power1.in"
                  });
              });
          })
          .to(cage.position, { y: centerPos.y + 0.5, duration: 0.2, ease: "power1.out" })
          .to(cage.position, { y: centerPos.y, duration: 0.15, ease: "power1.in" })
          .to({}, { duration: 4.5 });
    });

    if (head) head.remove(tearsGroup);
    scene.remove(cage);
    model.position.copy(origPos);
    model.rotation.copy(origRot);
    model.scale.set(1.5, 1.5, 1.5);

    model.visible = false;
    setBoardVisibility(false);
    if (existingHouse) existingHouse.visible = false;

    if (targetTile) {
        gsap.to(targetTile.scale, { x: 1, z: 1, duration: 0.5 });
    }

    if (playerName === myName || isSpectating) {
        camera.quaternion.copy(origCamQuat);
    }

    if (playerName === myName && !isSpectating) {
        if (head) head.visible = false;
    }
}

async function playStealAnimationCore(ctx, attackerName, victimName) {
    const playSfx = ctx.playSfx || _noop;
    const { scene, camera, playerModels, allTileMeshes, mapBlocks, playerCurrentIndex, panoSphere, myName, isSpectating } = ctx;

    const attackerModel = playerModels[attackerName];
    const victimModel = playerModels[victimName];
    if (!attackerModel || !victimModel) return;

    scene.background = new THREE.Color(0xf1f5f9);
    if (panoSphere) { panoSphere.visible = false; panoSphere.material.opacity = 0; }
    allTileMeshes.forEach(m => m.visible = true);

    const origAttackerPos = attackerModel.position.clone();
    const origAttackerRot = attackerModel.rotation.clone();
    const origVictimPos = victimModel.position.clone();
    const origVictimRot = victimModel.rotation.clone();

    const centerIdx = playerCurrentIndex[attackerName] || 0;
    const centerPos = mapBlocks[centerIdx].clone();

    attackerModel.position.set(centerPos.x - 1.5, centerPos.y, centerPos.z);
    victimModel.position.set(centerPos.x + 1.5, centerPos.y, centerPos.z);

    attackerModel.lookAt(attackerModel.position.x, attackerModel.position.y, attackerModel.position.z + 10);
    victimModel.lookAt(victimModel.position.x, victimModel.position.y, victimModel.position.z + 10);

    attackerModel.visible = true;
    victimModel.visible = true;

    const attackerHead = attackerModel.getObjectByName("head");
    const victimHead = victimModel.getObjectByName("head");
    if (attackerHead) attackerHead.visible = true;
    if (victimHead) victimHead.visible = true;

    if (attackerName === myName || isSpectating) {
        camera.layers.enable(0);
        camera.layers.enable(1);
        camera.position.set(centerPos.x, centerPos.y + 5.0, centerPos.z + 9);
        camera.lookAt(centerPos.x, centerPos.y + 1.2, centerPos.z);
    }

    const shovel = createShovel();
    attackerModel.add(shovel);
    shovel.position.set(0.6, 1.2, 0.6);
    shovel.rotation.x = Math.PI / 2;

    await new Promise(res => {
        const tl = gsap.timeline({ onComplete: res });

        tl.to(attackerModel.rotation, { y: Math.PI / 3, duration: 0.5, ease: "back.out(1.5)" })
          .to(victimModel.rotation, { y: -Math.PI / 3, duration: 0.3 }, "-=0.2")
          .to({}, { duration: 0.2 });

        for (let i = 0; i < 6; i++) {
            tl.to(attackerModel.rotation, { x: -0.6, duration: 0.25, ease: "power2.inOut" })
              .to(attackerModel.rotation, { x: 0.7, duration: 0.12, ease: "none" })
              .add(() => {
                  playSfx('steal');
                  gsap.to(victimModel.position, { x: victimModel.position.x + (i % 2 === 0 ? 0.15 : -0.15), duration: 0.05, yoyo: true, repeat: 3 });
                  spawnCombatText('right', "🪙 -$50", "#ff4757");
              })
              .to(attackerModel.rotation, { x: 0, duration: 0.2 });
        }

        tl.add(() => {
            spawnCombatText('left', "💰 總共 +$300", "#00cdac");
        });
        tl.to({}, { duration: 1.5 });
    });

    attackerModel.remove(shovel);

    attackerModel.position.copy(origAttackerPos);
    attackerModel.rotation.copy(origAttackerRot);
    victimModel.position.copy(origVictimPos);
    victimModel.rotation.copy(origVictimRot);
}
