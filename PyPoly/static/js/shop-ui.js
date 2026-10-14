// =============================================================
// 道具商店 UI
//
// 從 game.html 抽出來的共用模組。抽離的原因是 static/preview/
// game_shop.html 要用同一份程式碼——複製一份的話，日後改道具內容/
// 商店版位就得記得改兩處，遲早變成「預覽好看但遊戲裡不是那樣」。
//
// SHOP_ITEMS 是純資料常數，跟 game.html 裡其他地方（背包 UI、扣款邏輯）
// 共用同一份，不要各自維護一份複本。
//
// renderShopCards()：原本直接寫在 openShopUI() 裡面的卡片 HTML 組裝
// 邏輯，單獨抽出來——openShopUI() 本身牽涉太多對局中才有的東西
// （socket、virtualScreen、鏡頭、uiState），不適合整個搬，只抽「卡片
// 長什麼樣子」這一段。
//
// createShopAvatarStage()／renderPlayerModelInShopStage()：原本是
// initShopAvatarStage()／renderPlayerModelInShop() 讀寫
// shopAvatarRenderer/shopAvatarScene/shopAvatarCamera/shopAvatarModel/
// shopAnimationId 五個全域變數，現在改成一個 stage 物件（由呼叫端自己
// 保管），不讀任何全域。這個小舞台本來就是獨立的 Three.js 場景，只需要
// 一個來源模型去 clone，不靠 playerModels 以外的任何對局狀態。
// =============================================================

const SHOP_ITEMS = {
    1: { id: "item_discount", name: "買房子折扣40%", price: 200, icon: "🏠", desc: "收購土地時可打6折" },
    2: { id: "item_plus3", name: "骰到步數+3", price: 150, icon: "🎲", desc: "移動時步數額外加 3 點" },
    3: { id: "item_notoll", name: "免收取過路費", price: 100, icon: "🛡️", desc: "踩到他人土地時免付過路費" },
    4: { id: "item_steal", name: "向對方收取300金幣", price: 100, icon: "⚔️", desc: "立即發動，敲打對手奪取金幣" }
};

// 把 SHOP_ITEMS（或任何同形狀的 items）畫成商店卡片 HTML，塞進 container。
function renderShopCards(container, items) {
    container.innerHTML = Object.keys(items).map(key => {
        const item = items[key];
        return `
            <div class="shop-item-card" id="shop-card-${key}">
                <div class="shop-item-id">${key}</div>
                <div class="shop-item-icon">${item.icon}</div>
                <div class="shop-item-name">${item.name}</div>
                <div class="shop-item-desc">${item.desc}</div>
                <div class="shop-item-price">$${item.price}</div>
            </div>
        `;
    }).join("");
}

// 建立一個獨立的小型 Three.js 舞台，專門用來渲染「商店畫面裡的角色替身」。
function createShopAvatarStage(canvasEl) {
    if (!canvasEl) return null;

    const renderer = new THREE.WebGLRenderer({ canvas: canvasEl, antialias: true, alpha: true });
    renderer.setSize(280, 320);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();

    // 🏆 調整相機位置，將相機往後拉遠(z=4.5)，讓全身能入鏡
    const camera = new THREE.PerspectiveCamera(40, 280 / 320, 0.1, 100);
    camera.position.set(0, 1.3, 4.5);
    camera.lookAt(0, 1.1, 0); // 相機看著人物身體中心點

    scene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
    dirLight.position.set(2, 4, 3);
    scene.add(dirLight);

    return { renderer, scene, camera, model: null, animationId: null };
}

// 🏆 修正一：道具店 3D 渲染 (強制作為可見、拉高模型高度，解決不重進就白屏的 Bug)
// stage 由 createShopAvatarStage() 建立；sourceModel 是要 clone 進舞台的來源模型
// （遊戲裡是 playerModels[playerName]，預覽頁可以是任何 createCustomBoxCharacter() 產物）。
function renderPlayerModelInShopStage(stage, sourceModel) {
    if (!stage) return;
    stage.renderer.setSize(280, 320);

    if (stage.animationId) {
        cancelAnimationFrame(stage.animationId);
        stage.animationId = null;
    }
    if (stage.model) stage.scene.remove(stage.model);

    if (sourceModel) {
        const clone = sourceModel.clone();

        // 🏆 關鍵修正：必須強制將複製出來的模型設為可見！
        // 防止因為主地圖呼叫了 setBoardVisibility(false) 導致複製出隱形人
        clone.visible = true;
        clone.traverse((child) => {
            child.visible = true; // 強制所有骨架與網格皆可見
            if (child.isMesh) {
                const srcChild = sourceModel.getObjectByName(child.name);
                if (srcChild) child.material = srcChild.material;
            }
        });

        clone.position.set(0, -0.15, 0);
        clone.scale.set(0.75, 0.75, 0.75);
        clone.rotation.set(0, 0, 0); // 正面朝前

        stage.scene.add(clone);
        stage.model = clone;
    } else {
        console.error('[SHOP] 找不到來源模型，無法渲染商店替身');
    }

    function animate() {
        stage.animationId = requestAnimationFrame(animate);
        if (stage.renderer && stage.scene && stage.camera) {
            stage.renderer.render(stage.scene, stage.camera);
        }
    }
    animate();
}
