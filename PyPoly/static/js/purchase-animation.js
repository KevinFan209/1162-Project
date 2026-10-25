// =============================================================
// 收購/加蓋土地動畫——玩家挖地蓋房子、格子變成自己顏色
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_purchase.html 要用同一份程式碼。
//
// createHouse(color) 是純函式，原樣搬移，沒有任何行為改變。
//
// runPurchaseAnimationCore(ctx, playerName, tileIndex, color, isUpgrade)
// 跟 spectator-animations.js 的 playTollAnimationCore 等函式用同一套
// ctx 參數慣例（跟 game.html 的 buildSpectatorAnimCtx() 回傳的物件
// 形狀一致：scene/camera/playerModels/allTileMeshes/mapBlocks/myName/
// isSpectating，其餘欄位這個函式用不到）。createShovel() 不在 ctx
// 裡——它是 spectator-animations.js 匯出的全域函式，這個模組假設
// 呼叫端已經先引入那份檔案（game.html／game_purchase.html 都是）。
//
// ⚠️ 加蓋升級分支裡有一段原樣保留的既有副作用：如果呼叫端提供的
// window.landOwnership 物件裡剛好有這個 tileIndex 的資料，這裡會
// 直接更新 floorCount 並寫回 localStorage 的 pypoly_land_ownership
// ——這是真正遊戲裡「加蓋後要持久化樓層數」用的，preview 頁如果想
// 示範加蓋動畫、又不想污染真實的 pypoly_land_ownership，記得讓
// window.landOwnership 是一個「不包含這個 tileIndex」的物件（例如
// 空物件 {}），這個 if 判斷就會自然跳過，不會寫入 localStorage。
// =============================================================

function createHouse(color) {
    const house = new THREE.Group();
    // 屋身
    const bodyGeo = new THREE.BoxGeometry(2, 2, 2);
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0xffffff });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 1;
    house.add(body);
    // 屋頂
    const roofGeo = new THREE.ConeGeometry(1.8, 1.5, 4);
    const roofMat = new THREE.MeshStandardMaterial({ color: color });
    const roof = new THREE.Mesh(roofGeo, roofMat);
    roof.position.y = 2.75;
    roof.rotation.y = Math.PI / 4;
    house.add(roof);
    return house;
}

async function runPurchaseAnimationCore(ctx, playerName, tileIndex, color, isUpgrade = false) {
    const { scene, camera, playerModels, allTileMeshes, mapBlocks, myName, isSpectating } = ctx;
    const isMe = (playerName === myName);

    const model = playerModels[playerName];
    const targetTile = allTileMeshes[tileIndex];
    if (!model || !targetTile) return;

    // 🏆 修正 1：確保人物與頭部絕對可見 (解決動畫時沒有頭的問題)
    model.visible = true;
    const head = model.getObjectByName("head");
    if (head) head.visible = true;

    const tilePos = targetTile.position.clone();

    model.rotation.set(0, 0, 0);
    model.quaternion.set(0, 0, 0, 1);
    model.up.set(0, 1, 0);
    model.scale.set(1.5, 1.5, 1.5);

    const nextIndex = (tileIndex + 1) % mapBlocks.length;
    const nextTilePos = mapBlocks[nextIndex].clone();
    const dirForward = new THREE.Vector3().subVectors(nextTilePos, tilePos).normalize();
    const dirRight = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), dirForward).normalize();

    const charFinalPos = tilePos.clone().addScaledVector(dirRight, -1.8);
    charFinalPos.y = tilePos.y + 0.6;
    const houseBuildPos = tilePos.clone().addScaledVector(dirRight, 1.4);

    model.position.copy(charFinalPos);

    // 🏆 修正 2：一開始就面對鏡頭 (直接看向前方的 dirForward)
    model.lookAt(charFinalPos.x + dirForward.x * 10, charFinalPos.y, charFinalPos.z + dirForward.z * 10);

    model.rotation.x = 0;
    model.rotation.z = 0;

    if (isMe || isSpectating) {
        camera.layers.enable(1);
        const startCamPos = camera.position.clone();
        const startLookDir = new THREE.Vector3();
        camera.getWorldDirection(startLookDir);
        const startLookTarget = startCamPos.clone().addScaledVector(startLookDir, 10);

        const finalCamPos = charFinalPos.clone().addScaledVector(dirForward, 7.7);
        finalCamPos.y = tilePos.y + 3.2;
        finalCamPos.addScaledVector(dirRight, 1.8);

        const finalLookTarget = tilePos.clone();
        finalLookTarget.y += 2.4;

        const midPoint = startCamPos.clone().lerp(finalCamPos, 0.5).addScaledVector(dirRight, 8.0);
        midPoint.y += 3.5;

        const camProgress = { t: 0 };
        gsap.to(camProgress, {
            t: 1, duration: 3.2, ease: "sine.inOut",
            onUpdate: () => {
                const t = camProgress.t;
                camera.position.set(
                    Math.pow(1 - t, 2) * startCamPos.x + 2 * (1 - t) * t * midPoint.x + Math.pow(t, 2) * finalCamPos.x,
                    Math.pow(1 - t, 2) * startCamPos.y + 2 * (1 - t) * t * midPoint.y + Math.pow(t, 2) * finalCamPos.y,
                    Math.pow(1 - t, 2) * startCamPos.z + 2 * (1 - t) * t * midPoint.z + Math.pow(t, 2) * finalCamPos.z
                );
                camera.lookAt(new THREE.Vector3().lerpVectors(startLookTarget, finalLookTarget, t));
            }
        });
    }

    const shovel = createShovel();
    model.add(shovel);
    shovel.position.set(0.6, 1.2, 0.6);
    shovel.rotation.x = Math.PI / 2;

    return new Promise(resolve => {
        const buildTl = gsap.timeline();
        for (let i = 0; i < 3; i++) {
            buildTl.to(model.rotation, { x: 0.35, duration: 0.8, ease: "power1.inOut" })
                   .to(model.rotation, { x: 0, duration: 0.3, ease: "back.out(2)" })
                   .to({}, { duration: 0.4 });
        }

        const hasHouse = targetTile.userData.hasHouse;

        buildTl.to({}, { duration: 0.6 }).add(() => {
            model.remove(shovel);

            if (!hasHouse || isUpgrade) {
                // 🏆 修正二：若為加蓋 (isUpgrade) 且原先已有房，執行加蓋；若無房則蓋新房
                if (!hasHouse) {
                    const house = createHouse(color);
                    house.name = "house_" + tileIndex;
                    house.position.copy(houseBuildPos);
                    house.scale.set(0, 0, 0);
                    scene.add(house);
                    targetTile.userData.hasHouse = true;
                    targetTile.userData.floorCount = 1;
                    gsap.fromTo(house.scale, { x: 0, y: 0, z: 0 }, { x: 0.85, y: 0.85, z: 0.85, duration: 1.8, ease: "elastic.out(1, 0.3)" });
                } else {
                    const existingHouse = scene.getObjectByName("house_" + tileIndex);
                    if (existingHouse) {
                        if (isUpgrade) {
                            const floorCount = existingHouse.children.filter(c => c.geometry && c.geometry.type === 'BoxGeometry').length;
                            const floorGeo = new THREE.BoxGeometry(2, 2, 2);
                            const floorMat = new THREE.MeshStandardMaterial({ color: 0xffffff });
                            const floor = new THREE.Mesh(floorGeo, floorMat);
                            floor.position.y = 1 + (2 * floorCount);
                            floor.scale.set(1, 0, 1);
                            existingHouse.add(floor);
                            gsap.to(floor.scale, {
                                y: 1,
                                duration: 0.8,
                                ease: "back.out(1.7)"
                            });

                            existingHouse.children.forEach(c => {
                                if (c.geometry && c.geometry.type === 'ConeGeometry') {
                                    gsap.to(c.position, {
                                        y: c.position.y + 2,
                                        duration: 0.8,
                                        ease: "back.out(1.7)"
                                    });
                                }
                            });

                            targetTile.userData.floorCount = floorCount + 1;

                            if (window.landOwnership && window.landOwnership[tileIndex]) {
                                window.landOwnership[tileIndex].floorCount = floorCount + 1;
                                localStorage.setItem('pypoly_land_ownership', JSON.stringify(window.landOwnership));
                            }
                        } else {
                            existingHouse.children.forEach(c => {
                                if (c.geometry && c.geometry.type === 'ConeGeometry') {
                                    c.material.color.set(color);
                                    c.material.needsUpdate = true;
                                }
                            });
                        }
                        gsap.fromTo(existingHouse.scale, { x: 0.85, y: 0.85, z: 0.85 }, { x: 1.0, y: 1.1, z: 1.0, duration: 0.3, yoyo: true, repeat: 1 });
                    }
                }
            }

            targetTile.material.color.set(color);

            // 🏆 修正：原本這裡寫死 y: 0.5，但棋盤 26 格裡只有 4 格原始
            // 高度天生是 0.5（見 board-layout.js 的 BOARD_HEIGHTS，範圍
            // 0~4）——蓋房子時格子會被拉去這個固定值，原始高度不是 0.5
            // 的格子看起來就像蓋完房子後下沉或上浮。改成用函式一開頭
            // 已經存好的 tilePos.y（格子原始高度），蓋完房子後維持原高。
            gsap.to(targetTile.position, {
                y: tilePos.y, duration: 1, onComplete: () => {
                    resolve();
                }
            });
        });
    });
}
