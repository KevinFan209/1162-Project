// =============================================================
// 小鳥飛小遊戲——畫面繪製 + 物理
//
// 從 game.html 抽出來的共用模組。抽離的原因有兩個：
// 1. static/preview/game_flappybird.html 要用同一份程式碼。
// 2. game.html 裡原本就有「兩份」畫小鳥/水管的程式碼——自己在玩的
//    gameLoop() 跟觀戰者的 FLAPPY_SYNC 接收處理各寫了一份幾乎一樣的
//    畫面繪製（觀戰者那份單純用廣播收到的座標畫，不跑物理）。這正是
//    「沒抽成共用模組，兩處各自演化」的實例，這次順手把畫面繪製那段
//    統一成 drawFlappyBirdScene()，兩邊都改call這支，不要再各留一份。
//
// game.html 的 startFlappyBirdMiniGame() 本身牽涉太多對局限定的東西
// （借用收購面板的 DOM、攝影機畫面、Socket.IO 廣播、
// finishFlappyBird() 的金錢/回合流程），這些都留在 game.html，不搬。
//
// bird/pipes 是物件/陣列，傳進來之後直接在原地修改（mutate），呼叫端
// 自己手上的參照會跟著變，不需要額外接回傳值去同步。
// =============================================================

function createInitialFlappyBirdPipe(canvas) {
    return { x: canvas.width * 0.7, top: canvas.height * 0.3, gap: 160, passed: false };
}

function flapFlappyBird(bird) {
    bird.v = -8.0;
}

// 純畫面繪製，不碰物理、不修改 bird/pipes 任何欄位——自己在玩的那端
// 跟觀戰者都能安全呼叫這支：自己玩的那端在呼叫前會先做 WAITING 的
// 浮動動畫、PLAYING 的物理推進（見 stepAndDrawFlappyBird）；觀戰者
// 直接拿廣播收到的 state/bird/pipes 原樣畫，不應該也不需要自己重算。
function drawFlappyBirdScene(ctx, canvas, state, bird, pipes) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    pipes.forEach(p => {
        ctx.fillStyle = 'rgba(0, 205, 172, 0.9)';
        ctx.lineWidth = 3;
        ctx.strokeStyle = '#005b4c';
        ctx.fillRect(p.x, 0, 45, p.top);
        ctx.strokeRect(p.x, 0, 45, p.top);
        ctx.fillRect(p.x, p.top + p.gap, 45, canvas.height - p.top - p.gap);
        ctx.strokeRect(p.x, p.top + p.gap, 45, canvas.height - p.top - p.gap);
    });

    const birdX = canvas.width * 0.25;

    ctx.save();
    ctx.translate(birdX, bird.y);

    if (state === 'PLAYING') {
        const rotation = Math.min(Math.PI / 4, Math.max(-Math.PI / 4, (bird.v * 0.08)));
        ctx.rotate(rotation);
    }

    ctx.fillStyle = '#ffde59';
    ctx.strokeStyle = '#d97706';
    ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.arc(0, 0, 15, 0, Math.PI * 2); ctx.fill(); ctx.stroke();

    ctx.fillStyle = '#ffb3b3';
    ctx.beginPath(); ctx.arc(6, 4, 3.5, 0, Math.PI * 2); ctx.fill();

    ctx.fillStyle = '#ffffff';
    ctx.beginPath(); ctx.arc(6, -4, 6, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#0f172a';
    ctx.beginPath(); ctx.arc(8, -4, 2.5, 0, Math.PI * 2); ctx.fill();

    ctx.fillStyle = '#f97316';
    ctx.strokeStyle = '#c2410c';
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(11, 2); ctx.lineTo(24, 5); ctx.lineTo(11, 9); ctx.closePath(); ctx.fill(); ctx.stroke();

    let wingY = (state === 'PLAYING' && bird.v < 0) ? 3 : -2;
    if (state === 'WAITING') wingY = Math.sin(Date.now() / 150) * 3;
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#d97706';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.ellipse(-5, wingY, 8, 5, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();

    ctx.restore();
}

// 畫一幀並（如果 state === 'PLAYING'）推進一格物理；WAITING 時先做
// 漂浮動畫再畫。只有「自己在玩」的那端呼叫這支，觀戰者直接呼叫
// drawFlappyBirdScene()。
// 回傳 { collided, pipesScoredCount }，碰撞/計分/決定輸贏都交給呼叫端
// 處理——這裡只負責「畫面長怎樣、位置怎麼變」。
//
// ⚠️ 已知的微小簡化：原版在同一幀內一旦分數跨過上限就整個 return，
// 不會再繼續推進其他水管；這裡改成讓這一幀把所有水管都推進完，用
// pipesScoredCount 回報分數增量，呼叫端自己判斷有沒有超過上限。
// 實務上一幀只會有一根水管過關，這個簡化不會有肉眼可見的差異。
function stepAndDrawFlappyBird(ctx, canvas, state, bird, pipes, dt) {
    if (state === 'WAITING') {
        bird.y = canvas.height / 2 + Math.sin(Date.now() / 200) * 10;
    }

    drawFlappyBirdScene(ctx, canvas, state, bird, pipes);

    let collided = false;
    let pipesScoredCount = 0;
    const birdX = canvas.width * 0.25;

    if (state === 'PLAYING') {
        bird.v += 0.5 * dt;
        if (bird.v > 10) bird.v = 10;
        bird.y += bird.v * dt;

        if (pipes[pipes.length - 1].x < canvas.width - 200) {
            const gap = 160;
            const topHeight = Math.random() * (canvas.height - gap - 50) + 25;
            pipes.push({ x: canvas.width, top: topHeight, gap: gap, passed: false });
        }

        for (let i = pipes.length - 1; i >= 0; i--) {
            const p = pipes[i];
            p.x -= 3.5 * dt;

            if ((birdX + 16 > p.x && birdX - 16 < p.x + 45) && (bird.y - 14 < p.top || bird.y + 14 > p.top + p.gap)) {
                collided = true;
            }

            if (!p.passed && p.x + 45 < birdX) {
                p.passed = true;
                pipesScoredCount++;
            }
            if (p.x < -50) pipes.splice(i, 1);
        }

        if (bird.y > canvas.height || bird.y < 0) collided = true;
    }

    return { collided, pipesScoredCount };
}
