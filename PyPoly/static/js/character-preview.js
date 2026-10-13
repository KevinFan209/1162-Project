// =============================================================
// 角色縮圖產生器（lobby.html／profile.html 共用）
//
// 用跟遊戲裡一樣的方塊角色（player-model.js 的 createCustomBoxCharacter）
// 離屏渲染一張縮圖，不再依賴 character.html 寫入的 pypoly_char_preview
// 快取——這樣換裝置、清過 localStorage，只要資料庫有 colors/features，
// 大廳/個人主頁都能直接補出縮圖，不需要先跑一次 character.html。
//
// 使用前要先載入 three.min.js、player-model.js；features 存在時還會用到
// character-face.js 的 buildFaceDataUrl()（沒載入的話就跳過臉部貼圖）。
//
// onFrame(dataUrl) 可能被呼叫兩次：第一次立刻給一張（沒有臉貼圖的版本
// 已經夠用了），如果這個角色有五官配方，臉部貼圖是非同步載入的 Image，
// 稍後會再補叫一次確保貼上了才是最終版本。呼叫端直接把兩次收到的值都
// 設成 <img>.src 即可，第二次只是把第一次蓋過去，不需要特別分辨。
//
// localFaceOverride（選填）：相機拍的人臉貼圖從設計上就不會存進資料庫
// （只存 colors/features 配方，8KB 上限刻意擋圖片），所以 DB 的
// features 永遠只會是五官套裝 ID、無法反映「這個人其實是用相機拍的」。
// 呼叫端如果在本機找到這個使用者的臉部貼圖快取（pypoly_char_face_*，
// 由 character.html 存檔時寫入），應該傳進來優先使用，不要讓這裡重新
// 用 DB 的 features 合成出一張不是真實外觀的臉。
// =============================================================
function renderCharacterPreview(colors, features, onFrame, localFaceOverride) {
    try {
        const faceUrl = localFaceOverride
            || ((features && typeof buildFaceDataUrl === 'function') ? buildFaceDataUrl(colors, features) : null);

        const width = 220, height = 280;
        const canvas = document.createElement('canvas');
        const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
        renderer.setSize(width, height);

        const scene = new THREE.Scene();
        scene.add(new THREE.AmbientLight(0xffffff, 0.9));
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
        dirLight.position.set(2, 4, 3);
        scene.add(dirLight);

        const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
        camera.position.set(0, 1.4, 4.2);
        camera.lookAt(0, 1.4, 0);

        const model = createCustomBoxCharacter(colors, faceUrl);
        scene.add(model);

        const capture = () => {
            renderer.render(scene, camera);
            onFrame(canvas.toDataURL('image/png'));
        };

        capture();
        if (faceUrl) setTimeout(capture, 150);
    } catch (err) {
        console.warn('⚠️ 產生角色縮圖失敗', err);
    }
}
