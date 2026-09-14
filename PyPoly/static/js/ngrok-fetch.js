// =============================================================
// 繞過 ngrok 免費方案的瀏覽器警告頁
//
// 問題：ngrok 免費方案會對「看起來像瀏覽器」的請求回一頁 HTML 警告頁
//       （Ngrok-Error-Code: ERR_NGROK_6024），而不是後端真正的回應。
//       實測結果：
//           GET  /rooms/public  → text/html  ← 被攔
//           POST /rooms/public  → application/json  ← 不攔
//       靜態頁面與 socket.io 的 polling 握手（都是 GET）同樣被攔。
//
// 症狀：平板用 ngrok 網址進大廳時，房間列表永遠只顯示靜態的「房間列表」。
//       因為 lobby.html 的 renderRooms() 先 fetch 再 res.json()，
//       拿到 HTML 解析失敗就被 catch 吞掉，連標題都沒換成「公開房間列表」。
//       電腦之所以正常，是因為先前點過警告頁的 Visit Site 拿到 cookie；
//       平板沒點過、或 Safari 的跨站追蹤防護讓 fetch 帶不上那個 cookie。
//
// 解法：所有請求都帶上 ngrok-skip-browser-warning 標頭，ngrok 就會直接放行，
//       不依賴 cookie。實測帶了標頭之後 Content-Type 正確回 application/json。
//
// 為什麼用包裝 window.fetch 而不是逐一修改：全專案有 81 處 fetch 散在 17 個
// 檔案裡，逐一加標頭一定會漏，日後新增的也會忘記。包一層就一勞永逸。
//
// ⚠️ 這支必須在其他會發出請求的 script 之前載入。
// =============================================================

(function () {
    // 只在 ngrok 網域下生效。本機與區網不受影響，行為完全不變。
    var host = location.hostname || "";
    if (!/(^|\.)ngrok(-free)?\.(dev|app|io)$/.test(host)) return;

    var HEADER = "ngrok-skip-browser-warning";
    var VALUE = "true";
    var origFetch = window.fetch;
    if (typeof origFetch !== "function") return;

    window.fetch = function (input, init) {
        try {
            // input 可能是網址字串，也可能是 Request 物件，兩種都要處理
            var headers = new Headers(
                (init && init.headers) ||
                (input instanceof Request ? input.headers : undefined)
            );
            if (!headers.has(HEADER)) headers.set(HEADER, VALUE);

            var opts = {};
            if (init) for (var k in init) opts[k] = init[k];
            opts.headers = headers;

            return origFetch.call(this, input, opts);
        } catch (e) {
            // 包裝失敗時不能讓整個請求跟著死，退回原本的 fetch
            console.warn("ngrok-fetch 包裝失敗，改用原生 fetch", e);
            return origFetch.call(this, input, init);
        }
    };

    // socket.io 的 polling 握手也是 GET，同樣會被攔。
    // 它不走 window.fetch，必須用 extraHeaders 另外處理——
    // 見 game.html 的 io(API_URL, { transportOptions: ... })。
    // 這裡把設定集中在一處，讓呼叫端直接用。
    window.NGROK_SOCKET_OPTS = {
        transportOptions: {
            polling: { extraHeaders: { "ngrok-skip-browser-warning": VALUE } }
        }
    };

    console.log("🔓 已啟用 ngrok 警告頁繞過（偵測到 ngrok 網域）");
})();
