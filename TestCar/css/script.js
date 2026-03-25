// 顏色互動 ==================================================

const colors = [
    '#667eea', '#764ba2', '#f093fb', '#4fd1c5',
    '#f6ad55', '#fc8181', '#48bb78', '#4299e1',
    '#9ae6b4', '#fbd38d', '#f687b3', '#63b3ed'
];

let currentColorIndex = 0;

function initColorApp() {
    const colorBox = document.getElementById('colorBox');
    const colorCodeSpan = document.getElementById('colorCode');
    const randomColorBtn = document.getElementById('randomColorBtn');
    const cycleColorBtn = document.getElementById('cycleColorBtn');
    const resetBtn = document.getElementById('resetBtn');
    const greeting = document.getElementById('greeting');

    const messages = [
        "歡迎使用這個互動網頁！🚀",
        "點擊按鈕來探索不同颜色。",
        "顏色讓世界更豐富！🌈",
        "今天又是美好的一天！☀️",
        "繼續點擊，發現更多驚喜！"
    ];

    applyColor(colors[0]);

    randomColorBtn.addEventListener('click', setRandomColor);
    cycleColorBtn.addEventListener('click', cycleColor);
    resetBtn.addEventListener('click', resetColor);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight') cycleColor();
        if (e.key === 'ArrowDown') setRandomColor();
        if (e.key === 'r' || e.key === 'R') resetColor();
    });

    function applyColor(color) {
        colorBox.style.background = color;
        colorCodeSpan.textContent = color;
        const luminance = getLuminance(color);
        const textColor = luminance > 0.5 ? '#000' : '#fff';
        colorCodeSpan.style.color = textColor;
    }

    function setRandomColor() {
        const randomIndex = Math.floor(Math.random() * colors.length);
        currentColorIndex = randomIndex;
        applyColor(colors[randomIndex]);
        animateBox();
    }

    function cycleColor() {
        currentColorIndex = (currentColorIndex + 1) % colors.length;
        applyColor(colors[currentColorIndex]);
        animateBox();
    }

    function resetColor() {
        currentColorIndex = 0;
        applyColor(colors[0]);
        showMessage('已重置為默認颜色！🔙');
    }

    function animateBox() {
        colorBox.style.transform = 'scale(0.95)';
        setTimeout(() => {
            colorBox.style.transform = 'scale(1)';
        }, 150);
    }

    function getLuminance(hex) {
        const rgb = parseInt(hex.slice(1), 16);
        const r = (rgb >> 16) & 0xff;
        const g = (rgb >> 8) & 0xff;
        const b = (rgb >> 0) & 0xff;
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    }

    function showRandomMessage() {
        const randomMsg = messages[Math.floor(Math.random() * messages.length)];
        showMessage(randomMsg);
    }

    function showMessage(msg) {
        greeting.style.opacity = 0;
        setTimeout(() => {
            greeting.textContent = msg;
            greeting.style.opacity = 1;
        }, 300);
    }
}

// ========== MonoPy 大富翁遊戲 ==========

class MonopolyGame {
    constructor(options) {
        this.playerCount = options.playerCount;  // 真人數量
        this.aiCount = options.aiCount;          // AI 數量
        this.totalPlayers = options.totalPlayers;
        this.winningGoal = options.winningGoal;
        this.players = [];
        this.boardCells = [];
        this.currentTurn = 0;
        this.gameOver = false;
        this.cellSize = 80;

        // DOM references
        this.boardWrapper = document.getElementById('boardWrapper');
        this.boardEl = document.getElementById('board');
        this.tokensContainer = document.getElementById('tokensContainer');
        this.playerCardsEl = document.getElementById('playerCards');
        this.diceDisplay = document.getElementById('diceDisplay');
        this.turnIndicator = document.getElementById('turnIndicator');
        this.logContent = document.getElementById('logContent');
        this.rollBtn = document.getElementById('rollDiceBtn');

        // 顏色池
        this.colorPool = [
            { name: '紅色', hex: '#e53e3e' },
            { name: '藍色', hex: '#3182ce' },
            { name: '綠色', hex: '#38a169' },
            { name: '橙色', hex: '#dd6b20' },
            { name: '紫色', hex: '#805ad5' },
            { name: '粉色', hex: '#d53f8c' }
        ];
        this.shuffleArray(this.colorPool);

        // 問題庫
        this.questions = this.createQuestionBank();

        // 3D car dimensions
        this.CAR_WIDTH = 140;
        this.CAR_HEIGHT = 80;
        this.carScale = 1;
        this.halfCarWidth = this.CAR_WIDTH / 2;
        this.halfCarHeight = this.CAR_HEIGHT / 2;
    }

    start() {
        this.createBoardCells();
        this.createPlayers();
        this.renderBoard();
        this.renderPlayerCards();
        this.updateTurnIndicator();
        this.log('遊戲開始！目標：最先達到 $' + this.winningGoal.toLocaleString() + '！');
        this.checkTurn();
    }

    // ========== 棋盤生成 ==========
    createBoardCells() {
        const cellNames = [
            { name: '台灣', type: 'start', label: '起點' },
            { name: '變數與型別', type: 'python-basic' },
            { name: '串接', type: 'python-basic' },
            { name: 'Luck', type: 'bonus' },
            { name: '清單', type: 'python-basic' },
            { name: '字典', type: 'python-basic' },
            { name: '條件語法', type: 'python-basic' },
            { name: '循環', type: 'python-basic' },
            { name: '函數', type: 'python-basic' },
            { name: '模組', type: 'python-basic' },

            { name: '百慕達', type: 'penalty', label: '-200' },
            { name: '例外處理', type: 'python-advanced' },
            { name: '裝飾器', type: 'python-advanced' },
            { name: '產生器', type: 'python-advanced' },
            { name: 'OOP', type: 'python-advanced' },
            { name: '瑞士金庫', type: 'bonus', label: '+3 Immunity' },
            { name: '多繼承', type: 'python-advanced' },
            { name: 'Metaclass', type: 'python-advanced' },
            { name: 'Async', type: 'python-advanced' },
            { name: 'Testing', type: 'python-advanced' },

            { name: '南極', type: 'penalty', label: '-150 / Skip' },
            { name: 'Quiz', type: 'challenge' },
            { name: 'Debug', type: 'challenge' },
            { name: 'Core', type: 'python-advanced' },
            { name: 'Standard Lib', type: 'python-advanced' },
            { name: '第三方套件', type: 'python-advanced' },
            { name: 'Web框架', type: 'python-advanced' },
            { name: 'DataScience', type: 'python-advanced' },
            { name: 'AI/ML', type: 'python-advanced' },
            { name: 'DevOps', type: 'python-advanced' },

            { name: 'End', type: 'end', label: '終點' },
            { name: 'Final', type: 'challenge' },
            { name: 'Architecture', type: 'python-advanced' },
            { name: 'Performance', type: 'python-advanced' },
            { name: 'Security', type: 'python-advanced' },
            { name: '西安', type: 'bonus', label: '+$500' },
            { name: '極光', type: 'bonus', label: 'Bonus' },
            { name: '未來', type: 'bonus', label: 'Future' },
            { name: 'Home', type: 'bonus', label: 'Home' },
            { name: 'AI Racer', type: 'bonus', label: 'AI' }
        ];

        this.boardCells = cellNames.map((cell, idx) => ({
            index: idx,
            name: cell.name,
            type: cell.type,
            label: cell.label || ''
        }));
    }

    createPlayers() {
        for (let i = 0; i < this.playerCount; i++) {
            this.players.push({
                id: i + 1,
                name: `玩家 ${i + 1}`,
                money: 1000,
                position: 0,
                color: this.colorPool[i],
                isAI: false,
                extraTurn: 0,
                skipNext: false,
                immunity: 0
            });
        }
        for (let i = 0; i < this.aiCount; i++) {
            this.players.push({
                id: this.players.length + 1,
                name: `電腦 ${i + 1}`,
                money: 1000,
                position: 0,
                color: this.colorPool[this.players.length],
                isAI: true,
                extraTurn: 0,
                skipNext: false,
                immunity: 0
            });
        }
    }

    // ========== 渲染棋盤 ==========
    renderBoard() {
        this.boardEl.innerHTML = '';
        const wrapperRect = this.boardWrapper.getBoundingClientRect();
        const boardWidth = wrapperRect.width;
        const boardHeight = wrapperRect.height;
        const minDim = Math.min(boardWidth, boardHeight);
        const padding = Math.max(20, Math.floor(minDim * 0.05));
        const sideLen = minDim - 2 * padding;
        const cellSize = Math.max(40, Math.floor(sideLen / 10));
        this.cellSize = cellSize;

        const offset = padding;

        // 40格：四邊各10格
        // 上邊: 左->右 (0-9)
        for (let i = 0; i < 10; i++) {
            const x = offset + i * cellSize;
            const y = offset;
            this.createCell(i, x, y, cellSize);
        }
        // 右邊: 上->下 (10-19)
        for (let i = 0; i < 10; i++) {
            const x = offset + sideLen - cellSize;
            const y = offset + i * cellSize;
            this.createCell(10 + i, x, y, cellSize);
        }
        // 下邊: 右->左 (20-29)
        for (let i = 0; i < 10; i++) {
            const x = offset + sideLen - (i + 1) * cellSize;
            const y = offset + sideLen - cellSize;
            this.createCell(20 + i, x, y, cellSize);
        }
        // 左邊: 下->上 (30-39)
        for (let i = 0; i < 10; i++) {
            const x = offset;
            const y = offset + sideLen - (i + 1) * cellSize;
            this.createCell(30 + i, x, y, cellSize);
        }

        // 將 tokensContainer 移入 boardEl
        if (this.tokensContainer.parentElement !== this.boardEl) {
            this.boardEl.appendChild(this.tokensContainer);
        }
        this.tokensContainer.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none;';

        this.createTokens();
    }

    createCell(index, x, y, size) {
        const cell = this.boardCells[index];
        const cellEl = document.createElement('div');
        cellEl.className = `cell ${cell.type}`;
        cellEl.dataset.index = index;
        cellEl.style.width = `${size}px`;
        cellEl.style.height = `${size}px`;
        cellEl.style.left = `${x}px`;
        cellEl.style.top = `${y}px`;
        cellEl.innerHTML = `<span>${cell.label || index}</span><span>${cell.name}</span>`;
        this.boardEl.appendChild(cellEl);
    }

    createTokens() {
        this.tokensContainer.innerHTML = '';
        this.players.forEach(player => {
            const token = document.createElement('div');
            token.className = 'car-token';
            token.id = `token-${player.id}`;
            token.style.setProperty('--car-color', player.color.hex);
            token.style.setProperty('--heading', `${this.getHeadingFromPosition(player.position)}deg`);
            token.innerHTML = `
                <div class="car">
                    <div class="car-body">
                        <div class="front"></div>
                        <div class="back"></div>
                        <div class="left"></div>
                        <div class="right"></div>
                        <div class="top"></div>
                        <div class="bottom"></div>
                    </div>
                    <div class="car-cabin">
                        <div class="window-left"></div>
                        <div class="window-right"></div>
                        <div class="window-front"></div>
                        <div class="window-back"></div>
                    </div>
                    <div class="light front-light-left"></div>
                    <div class="light front-light-right"></div>
                    <div class="light back-light-left"></div>
                    <div class="light back-light-right"></div>
                    <div class="wheel w1"></div>
                    <div class="wheel w2"></div>
                    <div class="wheel w3"></div>
                    <div class="wheel w4"></div>
                    <div class="car-number">${player.id}</div>
                </div>
            `;
            this.tokensContainer.appendChild(token);
        });
        this.updateTokenPositions();
    }

    updateTokenPositions() {
        this.players.forEach(player => {
            const token = document.getElementById(`token-${player.id}`);
            if (!token) return;
            const cells = this.boardEl.querySelectorAll('.cell');
            const cellEl = cells[player.position];
            if (cellEl) {
                const x = parseFloat(cellEl.style.left) + this.cellSize / 2;
                const y = parseFloat(cellEl.style.top) + this.cellSize / 2;
                token.style.left = `${x}px`;
                token.style.top = `${y}px`;
                token.style.setProperty('--heading', `${this.getHeadingFromPosition(player.position)}deg`);
            }
        });
    }

    getHeadingFromPosition(cellIndex) {
        const edge = Math.floor(cellIndex / 10); // 0:上, 1:右, 2:下, 3:左
        const headings = [0, 90, 180, 270];
        return headings[edge];
    }

    // ========== 玩家卡片 ==========
    renderPlayerCards() {
        this.playerCardsEl.innerHTML = '';
        this.players.forEach(player => {
            const card = document.createElement('div');
            card.className = 'player-card';
            card.id = `player-card-${player.id}`;
            card.style.borderLeft = `5px solid ${player.color.hex}`;
            if (player.id === this.players[this.currentTurn].id) {
                card.classList.add('active');
            }
            card.innerHTML = `
                <div class="color-dot" style="background:${player.color.hex}"></div>
                <div class="player-info">
                    <div class="player-name">${player.name} ${player.isAI ? '🤖' : ''}</div>
                    <div class="player-stats">金錢: $${player.money.toLocaleString()}</div>
                    <div class="player-stats">位置: ${this.boardCells[player.position].name}</div>
                </div>
            `;
            this.playerCardsEl.appendChild(card);
        });
    }

    updateTurnIndicator() {
        const currentPlayer = this.players[this.currentTurn];
        this.turnIndicator.textContent = `🎮 ${currentPlayer.name} 的回合`;
        this.rollBtn.disabled = currentPlayer.isAI;
    }

    checkTurn() {
        this.renderPlayerCards();
        this.updateTurnIndicator();
        if (this.players[this.currentTurn].isAI) {
            this.log(`${this.players[this.currentTurn].name} 正在思考...`);
            setTimeout(() => this.aiTurn(), 1500);
        } else {
            this.log(`輪到 ${this.players[this.currentTurn].name} 擲骰子`);
        }
    }

    rollDice() {
        if (this.gameOver) return;
        const player = this.players[this.currentTurn];
        if (player.isAI) return;
        this.rollBtn.disabled = true;
        const dice = Math.floor(Math.random() * 6) + 1;
        this.animateDice(dice, () => {
            this.movePlayer(player, dice);
        });
    }

    animateDice(value, callback) {
        this.diceDisplay.classList.add('rolling');
        this.diceDisplay.querySelector('span').textContent = '?';
        setTimeout(() => {
            this.diceDisplay.classList.remove('rolling');
            this.diceDisplay.querySelector('span').textContent = value;
            callback();
        }, 500);
    }

    movePlayer(player, steps) {
        const oldPos = player.position;
        player.position = (player.position + steps) % this.boardCells.length;
        if (player.position < oldPos) {
            player.money += 200;
            this.log(`${player.name} 經過起點！獲得 $200`);
        }
        this.log(`${player.name} 擲出 ${steps} 點，移動到 ${this.boardCells[player.position].name}`);
        this.updateTokenPositions();
        this.renderPlayerCards();
        setTimeout(() => this.handleCellEvent(player), 600);
    }

    handleCellEvent(player) {
        const cell = this.boardCells[player.position];
        this.log(`${player.name} 到達了 ${cell.name}`);
        if (cell.type === 'start' || cell.type === 'end') {
            this.finishTurn();
            return;
        }
        if (cell.type === 'bonus') {
            const bonus = 200;
            player.money += bonus;
            this.log(`${player.name} 獲得獎金 $${bonus}`);
            this.renderPlayerCards();
            setTimeout(() => this.finishTurn(), 1000);
            return;
        }
        if (cell.type === 'penalty') {
            const penalty = cell.name.includes('南極') ? 150 : 200;
            player.money = Math.max(0, player.money - penalty);
            this.log(`${player.name} 被罰款 $${penalty}`);
            this.renderPlayerCards();
            setTimeout(() => this.finishTurn(), 1000);
            return;
        }
        if (['python-basic', 'python-advanced', 'challenge'].includes(cell.type)) {
            const question = this.getRandomQuestion(cell.type);
            this.showQuestion(player, question);
            return;
        }
        this.finishTurn();
    }

    getRandomQuestion(type) {
        const pool = this.questions[type] || this.questions['python-basic'];
        return pool[Math.floor(Math.random() * pool.length)];
    }

    showQuestion(player, question) {
        this.rollBtn.disabled = true;
        const modal = document.getElementById('question-modal');
        const questionEl = document.getElementById('questionText');
        const categoryEl = document.getElementById('questionCategory');
        const answerArea = document.getElementById('answerOptions');
        const feedback = document.getElementById('feedback');

        feedback.style.display = 'none';
        answerArea.innerHTML = '';
        categoryEl.textContent = question.category;
        questionEl.textContent = question.text;

        question.options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.className = 'answer-btn';
            btn.textContent = `${String.fromCharCode(65+idx)}. ${opt}`;
            btn.dataset.index = idx;
            btn.addEventListener('click', () => this.handleAnswer(player, question, idx));
            answerArea.appendChild(btn);
        });

        modal.classList.add('show');
    }

    handleAnswer(player, question, selectedIdx) {
        const allBtns = document.querySelectorAll('.answer-btn');
        allBtns.forEach(b => b.disabled = true);
        const isCorrect = selectedIdx === question.correct;
        const reward = isCorrect ? 150 + Math.floor(Math.random() * 100) : 0;
        allBtns[selectedIdx].classList.add(isCorrect ? 'correct' : 'wrong');

        if (isCorrect) {
            player.money += reward;
            this.log(`${player.name} 答對！獲得 $${reward}`);
        } else {
            this.log(`${player.name} 答錯！`);
        }
        this.renderPlayerCards();

        if (player.money >= this.winningGoal) {
            setTimeout(() => this.endGame(player), 1500);
            return;
        }

        setTimeout(() => {
            document.getElementById('question-modal').classList.remove('show');
            this.finishTurn();
        }, 2000);
    }

    finishTurn() {
        if (this.players[this.currentTurn].skipNext) {
            this.players[this.currentTurn].skipNext = false;
            this.log(`${this.players[this.currentTurn].name} 跳過這一回合`);
        } else {
            this.currentTurn = (this.currentTurn + 1) % this.totalPlayers;
        }
        if (this.gameOver) return;
        this.checkTurn();
    }

    aiTurn() {
        if (this.gameOver) return;
        const ai = this.players[this.currentTurn];
        this.log(`${ai.name} 正在擲骰...`);
        setTimeout(() => {
            const dice = Math.floor(Math.random() * 6) + 1;
            this.animateDice(dice, () => {
                this.movePlayer(ai, dice);
            });
        }, 1200);
    }

    endGame(winner) {
        this.gameOver = true;
        this.rollBtn.disabled = true;
        setTimeout(() => {
            const modal = document.getElementById('game-over');
            modal.classList.remove('hidden');
            modal.querySelector('.winner-announcement').textContent = `${winner.name} 獲勝！`;
            modal.querySelector('.game-stats').innerHTML = `
                <p>最終資產：$${winner.money.toLocaleString()}</p>
                <p>遊戲目標：$${this.winningGoal.toLocaleString()}</p>
            `;
        }, 1000);
    }

    log(msg) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        this.logContent.prepend(entry);
    }

    // ========== 問題庫 ==========
    createQuestionBank() {
        return {
            'python-basic': [
                { category: '變數', text: 'Python 中宣告變數時需要寫上類型嗎？', options: ['需要', '不需要'], correct: 1 },
                { category: '型別', text: '>>> type(3.14) 的結果是？', options: ['int', 'float', 'str', 'bool'], correct: 1 },
                { category: '字串', text: '>>> "Hello" + "World" 的結果？', options: ['Hello World', 'HelloWorld', '錯誤'], correct: 1 },
                { category: '串接', text: '>>> [1,2] + [3,4] 的結果是？', options: ['[1,2,3,4]', '[1,2],[3,4]', '錯誤'], correct: 0 },
                { category: '條件', text: 'if 條件成立時會執行哪個區塊？', options: ['if 下方縮排', 'else 下方', '都不執行'], correct: 0 },
                { category: '循環', text: 'for i in range(3): print(i) 輸出？', options: ['0,1,2', '1,2,3', '0,1,2,3'], correct: 0 },
                { category: '函數', text: '定義函數的關鍵字是？', options: ['def', 'function', 'func'], correct: 0 },
                { category: '模組', text: '引入 math 模組的語法是？', options: ['import math', 'include math', 'require math'], correct: 0 }
            ],
            'python-advanced': [
                { category: '裝飾器', text: '裝飾器的符號是？', options: ['@', '#', '&'], correct: 0 },
                { category: '生成器', text: '哪個函數回傳生成器？', options: ['range()', 'list()', 'dict()'], correct: 0 },
                { category: 'OOP', text: '__init__ 用於什麼？', options: ['建構子', '解構子', 'toString'], correct: 0 },
                { category: '異常', text: '捕捉所有異常的關鍵字是？', options: ['except', 'catch', 'error'], correct: 0 },
                { category: '作用域', text: '區域變數在何處有效？', options: ['函數內', '全域', '模組內'], correct: 0 },
                { category: '清單推導', text: '[x**2 for x in range(3)] 的結果？', options: ['[0,1,4]', '[0,1,2]', '[0,1,4,9]'], correct: 0 }
            ],
            'challenge': [
                { category: 'Debug', text: '>>> print(1 + "1") 的錯誤類型？', options: ['TypeError', 'ValueError', 'SyntaxError'], correct: 0 },
                { category: '邏輯', text: 'and 運算優先於 or？', options: ['是', '否'], correct: 0 },
                { category: 'Python 2 vs 3', text: 'print 在 Py2 與 Py3 的差異？', options: ['函數 vs 陳述句', '一樣', '語法錯誤'], correct: 0 }
            ]
        };
    }

    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
    }

    cleanup() {
        this.gameOver = true;
    }
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    initColorApp();

    // 大富翁遊戲控制
    const startMonopolyBtn = document.getElementById('startMonopolyBtn');
    const monopolyGame = document.getElementById('monopoly-game');
    const backToMenuBtn = document.getElementById('backToMenu');
    const gameSetup = document.getElementById('gameSetup');
    const gameArea = document.getElementById('gameArea');
    const actuallyStartGame = document.getElementById('actuallyStartGame');
    const rollDiceBtn = document.getElementById('rollDiceBtn');
    const leaveGameBtn = document.getElementById('leaveGameBtn');
    const leaveRoomBtn = document.getElementById('leaveRoomBtn');
    const turnIndicator = document.getElementById('turnIndicator');
    const logContent = document.getElementById('logContent');

    startMonopolyBtn.addEventListener('click', () => {
        monopolyGame.classList.remove('hidden');
    });

    backToMenuBtn.addEventListener('click', () => {
        monopolyGame.classList.add('hidden');
    });

    actuallyStartGame.addEventListener('click', () => {
        const playerCount = parseInt(document.getElementById('playerCount').value);
        const gameMode = document.getElementById('gameMode').value;
        const aiCount = parseInt(document.getElementById('aiCount').value);
        const winningGoal = parseInt(document.getElementById('winningGoal').value);

        gameSetup.classList.add('hidden');
        gameArea.classList.remove('hidden');

        window.monopoly = new MonopolyGame({
            playerCount: gameMode === 'ai' ? 1 : playerCount,
            aiCount: gameMode === 'ai' ? Math.min(aiCount, 3) : 0,
            totalPlayers: gameMode === 'ai' ? 1 + aiCount : playerCount,
            winningGoal: winningGoal
        });
        window.monopoly.start();
    });

    rollDiceBtn.addEventListener('click', () => {
        if (window.monopoly) window.monopoly.rollDice();
    });

    leaveGameBtn.addEventListener('click', () => {
        if (window.monopoly) {
            window.monopoly.cleanup();
            window.monopoly = null;
        }
        gameArea.classList.add('hidden');
        gameSetup.classList.remove('hidden');
        monopolyGame.classList.add('hidden');
    });

    // 重新開始
    document.getElementById('restartBtn').addEventListener('click', () => {
        document.getElementById('game-over').classList.add('hidden');
        if (window.monopoly) {
            window.monopoly.cleanup();
            window.monopoly = null;
        }
        gameArea.classList.add('hidden');
        gameSetup.classList.remove('hidden');
    });
});

// 調整棋盤大小
window.addEventListener('resize', () => {
    if (window.monopoly && window.monopoly.boardWrapper) {
        window.monopoly.renderBoard();
    }
});
