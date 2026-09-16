// =============================================================
// 角色的 3D 方塊模型
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/ 底下的
// 預覽頁要用同一份程式碼——複製一份的話，日後改角色外觀就得記得改兩處，
// 遲早變成「預覽好看但遊戲裡不是那樣」。
//
// 這個函式本來就不讀任何全域變數（scene / camera / gameMap 都沒用到），
// 所以是原樣搬移，沒有任何行為改變。
//
// 臉部貼圖由 character-face.js 的 buildFaceDataUrl(colors, features) 產生，
// 傳進來的 faceDataUrl 就是它的輸出。
// =============================================================

function createCustomBoxCharacter(colors, faceDataUrl) {
    const group = new THREE.Group();

    const headMat  = new THREE.MeshStandardMaterial({ color: colors.head, roughness: 0.6 });
    const bodyMat  = new THREE.MeshStandardMaterial({ color: colors.body, roughness: 0.6 });
    const armMat   = new THREE.MeshStandardMaterial({ color: colors.arm,  roughness: 0.6 });
    const legsMat  = new THREE.MeshStandardMaterial({ color: colors.legs, roughness: 0.6 });
    const feetMat  = new THREE.MeshStandardMaterial({ color: colors.feet, roughness: 0.6 });

    // 1. 🏆 頭部多重材質處理：Index 4 是正前方 (+Z)
    const headGeo = new THREE.BoxGeometry(0.8, 0.8, 0.8);
    let headMaterialSetting = headMat;

    if (faceDataUrl) {
        const img = new Image();
        img.src = faceDataUrl;
        const faceTex = new THREE.Texture(img);
        img.onload = () => { faceTex.needsUpdate = true; };
        
        const faceMat = new THREE.MeshStandardMaterial({ 
            map: faceTex,
            roughness: 0.5
        });
        // 🚀 關鍵：[右, 左, 上, 下, 前(人臉貼圖), 後]
        headMaterialSetting = [headMat, headMat, headMat, headMat, faceMat, headMat];
    }

    const headMesh = new THREE.Mesh(headGeo, headMaterialSetting);
    headMesh.position.set(0, 2.4, 0);
    headMesh.name = "head"; 
    group.add(headMesh);

    // 2. 身體
    const bodyGeo = new THREE.BoxGeometry(0.8, 1.0, 0.4);
    const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
    bodyMesh.position.set(0, 1.5, 0);
    bodyMesh.name = "body";
    group.add(bodyMesh);

    // 3. 手臂
    const armGeo = new THREE.BoxGeometry(0.24, 1.0, 0.4);
    const leftArm = new THREE.Mesh(armGeo, armMat); leftArm.position.set(-0.52, 1.5, 0); leftArm.name = "leftArm"; group.add(leftArm);
    const rightArm = new THREE.Mesh(armGeo, armMat); rightArm.position.set(0.52, 1.5, 0); rightArm.name = "rightArm"; group.add(rightArm);

    // 4. 腿部
    const legGeo = new THREE.BoxGeometry(0.36, 0.8, 0.4);
    const leftLeg = new THREE.Mesh(legGeo, legsMat); leftLeg.position.set(-0.2, 0.6, 0); leftLeg.name = "leftLeg"; group.add(leftLeg);
    const rightLeg = new THREE.Mesh(legGeo, legsMat); rightLeg.position.set(0.2, 0.6, 0); rightLeg.name = "rightLeg"; group.add(rightLeg);

    // 5. 鞋子
    const footGeo = new THREE.BoxGeometry(0.38, 0.2, 0.48);
    const leftFoot = new THREE.Mesh(footGeo, feetMat); leftFoot.position.set(-0.2, 0.1, 0.04); leftFoot.name = "leftFoot"; group.add(leftFoot);
    const rightFoot = new THREE.Mesh(footGeo, feetMat); rightFoot.position.set(0.2, 0.1, 0.04); rightFoot.name = "rightFoot"; group.add(rightFoot);

    group.traverse((child) => {
        if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            child.layers.set(0); 
        }
    });

    return group;
}
