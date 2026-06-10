// ── Tile type definitions ─────────────────────────────────────────────────────
const TILE_TYPES = {
    start: { label: '起點', color: '#00cdac' },
    grass: { label: '草地', color: '#66bb6a' },
    stone: { label: '石頭', color: '#90a4ae' },
    sand:  { label: '沙地', color: '#ffca28' },
    ice:   { label: '冰地', color: '#80deea' },
    lava:  { label: '熔岩', color: '#ff7043' },
    event: { label: '事件', color: '#ce93d8' }
};

// ── Default tile data (must mirror game.html's getDefaultTileData) ────────────
function getDefaultTiles() {
    const topH  = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4];
    const topT  = ['start','grass','stone','grass','event','stone','sand','grass','stone'];
    const rightH = [4, 4, 4, 3.5, 3];
    const rightT = ['ice','event','lava','stone','ice'];
    const botH  = [3, 2.5, 2, 2, 1.5, 1, 0.5, 0];
    const botT  = ['lava','event','stone','sand','grass','event','stone','grass'];
    const leftH = [0, 0.5, 0.5, 0];
    const leftT = ['ice','stone','event','grass'];

    const tiles = [];
    for (let i = 0; i < 9; i++) tiles.push({ x: -16 + i*4, z: 10,       y: topH[i],    type: topT[i],    label: topT[i] === 'start' ? 'GO' : '', size: 1 });
    for (let i = 1; i < 6; i++) tiles.push({ x: 16,         z: 10 - i*4, y: rightH[i-1],type: rightT[i-1],label: '', size: 1 });
    for (let i = 1; i < 9; i++) tiles.push({ x: 16 - i*4,  z: -10,      y: botH[i-1],  type: botT[i-1],  label: '', size: 1 });
    for (let i = 1; i < 5; i++) tiles.push({ x: -16,        z: -10 + i*4,y: leftH[i-1], type: leftT[i-1], label: '', size: 1 });
    return tiles;
}

// ── State ─────────────────────────────────────────────────────────────────────
let boardConfig = { version: 1, boardName: 'Custom Board', tiles: getDefaultTiles() };
let selectedIndex = null;

// ── Undo / Redo history ─────────────────────────────────────────────────────────
const HISTORY_MAX = 100;
let history    = [];   // stack of pre-change snapshots
let redoStack  = [];
let pendingSnapshot = null;   // snapshot captured at focus, committed on first edit

function snapshot() { return JSON.parse(JSON.stringify(boardConfig)); }

// Record a pre-change snapshot. Call BEFORE mutating boardConfig.
function recordHistory(state) {
    history.push(state || snapshot());
    if (history.length > HISTORY_MAX) history.shift();
    redoStack = [];
    updateUndoButtons();
}
function pushHistory() { recordHistory(snapshot()); }

function updateUndoButtons() {
    const u = document.getElementById('btnUndo');
    const r = document.getElementById('btnRedo');
    if (u) u.disabled = history.length === 0;
    if (r) r.disabled = redoStack.length === 0;
}

function undo() {
    if (!history.length) return;
    redoStack.push(snapshot());
    boardConfig = history.pop();
    afterHistoryChange();
}
function redo() {
    if (!redoStack.length) return;
    history.push(snapshot());
    boardConfig = redoStack.pop();
    afterHistoryChange();
}

// Refresh all UI from boardConfig after an undo/redo restore.
function afterHistoryChange() {
    document.getElementById('boardName').value = boardConfig.boardName || 'Custom Board';
    if (selectedIndex !== null && selectedIndex >= boardConfig.tiles.length) selectedIndex = null;
    if (selectedIndex !== null) {
        selectTile(selectedIndex);   // also redraws + re-renders list
    } else {
        document.getElementById('no-selection').style.display = 'block';
        document.getElementById('tile-props').style.display   = 'none';
        drawBoard();
        renderTileList();
    }
    updateUndoButtons();
}

// ── Canvas setup ──────────────────────────────────────────────────────────────
const canvas  = document.getElementById('boardCanvas');
const ctx     = canvas.getContext('2d');

// World viewport (with margin around the default board) — auto-fit to content
let WX_MIN = -22, WX_MAX = 22;
let WZ_MIN = -14, WZ_MAX = 14;
const TILE_HALF = 1.75;   // half of tile 3D width 3.5

// Recompute the 2D viewport so it frames every tile. Call on wholesale board
// changes (generate / import / reset / load) — not during drag, to avoid jitter.
function fitViewport() {
    const tiles = boardConfig.tiles;
    if (!tiles.length) return;
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    tiles.forEach(o => {
        const h = TILE_HALF * (o.size ?? 1);
        minX = Math.min(minX, o.x - h); maxX = Math.max(maxX, o.x + h);
        minZ = Math.min(minZ, o.z - h); maxZ = Math.max(maxZ, o.z + h);
    });
    const pad = 4;
    WX_MIN = minX - pad; WX_MAX = maxX + pad;
    WZ_MIN = minZ - pad; WZ_MAX = maxZ + pad;
}

function resizeCanvas() {
    const area  = document.getElementById('canvas-area');
    const maxW  = area.clientWidth  - 24;
    const maxH  = area.clientHeight - 60;  // leave room for legend
    const worldAspect = (WX_MAX - WX_MIN) / (WZ_MAX - WZ_MIN);
    let W = maxW, H = maxW / worldAspect;
    if (H > maxH) { H = maxH; W = maxH * worldAspect; }
    canvas.width  = Math.floor(W);
    canvas.height = Math.floor(H);
    drawBoard();
}

function wx2cx(x) { return (x - WX_MIN) / (WX_MAX - WX_MIN) * canvas.width; }
// Z 方向不翻轉：z 越小 → cy 越小 → 畫面越靠上，與 game.html 相機（z=+45）的視角一致
function wz2cy(z) { return (z - WZ_MIN) / (WZ_MAX - WZ_MIN) * canvas.height; }
function tileR()  { return TILE_HALF / (WX_MAX - WX_MIN) * canvas.width; }

function cx2wx(cx) { return cx / canvas.width  * (WX_MAX - WX_MIN) + WX_MIN; }
function cy2wz(cy) { return cy / canvas.height * (WZ_MAX - WZ_MIN) + WZ_MIN; }

// ── Draw board ────────────────────────────────────────────────────────────────
function drawBoard() {
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, W, H);

    // Faint grid
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let x = Math.ceil(WX_MIN / 4) * 4; x <= WX_MAX; x += 4) {
        const cx = wx2cx(x);
        ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, H); ctx.stroke();
    }
    for (let z = Math.ceil(WZ_MIN / 4) * 4; z <= WZ_MAX; z += 4) {
        const cy = wz2cy(z);
        ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(W, cy); ctx.stroke();
    }

    const tiles = boardConfig.tiles;
    if (!tiles.length) return;

    // Path lines
    ctx.strokeStyle = 'rgba(88,166,255,0.2)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    tiles.forEach((t, i) => {
        i === 0
            ? ctx.moveTo(wx2cx(t.x), wz2cy(t.z))
            : ctx.lineTo(wx2cx(t.x), wz2cy(t.z));
    });
    ctx.lineTo(wx2cx(tiles[0].x), wz2cy(tiles[0].z));
    ctx.stroke();
    ctx.setLineDash([]);

    // Tiles
    tiles.forEach((tile, idx) => {
        const cx = wx2cx(tile.x);
        const cy = wz2cy(tile.z);
        const r  = tileR() * (tile.size ?? 1);
        const color = TILE_TYPES[tile.type]?.color || '#e0e0e0';
        const heightAlpha = tile.y / 8;

        ctx.save();
        ctx.translate(cx, cy);

        // Drop shadow
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.fillRect(-r + 2, -r + 2, r * 2, r * 2);

        // Tile body
        ctx.fillStyle = color;
        ctx.fillRect(-r, -r, r * 2, r * 2);

        // Height brightness overlay (lighter = taller)
        ctx.fillStyle = `rgba(255,255,255,${heightAlpha * 0.4})`;
        ctx.fillRect(-r, -r, r * 2, r * 2);

        // Border
        if (drag.active && idx === drag.index && drag.blocked) {
            ctx.strokeStyle = '#ff4444';
            ctx.lineWidth = 3;
        } else if (idx === selectedIndex) {
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 3;
        } else {
            ctx.strokeStyle = 'rgba(0,0,0,0.6)';
            ctx.lineWidth = 1;
        }
        ctx.strokeRect(-r, -r, r * 2, r * 2);

        // Sequence number
        const numSize = Math.max(9, r * 0.65);
        ctx.fillStyle = 'rgba(0,0,0,0.75)';
        ctx.font = `bold ${numSize}px monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(idx, 0, 0);

        // Label
        const text = tile.label || (tile.type === 'start' ? 'GO' : tile.type === 'event' ? '?' : null);
        if (text) {
            const fs = Math.max(7, r * 0.5);
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            ctx.font = `bold ${fs}px Arial`;
            ctx.fillText(text, 0, r * 0.52);
        }

        // Height badge (top-right corner)
        if (tile.y > 0) {
            const bw = r * 0.9, bh = r * 0.55;
            ctx.fillStyle = 'rgba(0,0,0,0.65)';
            ctx.fillRect(r - bw, -r, bw, bh);
            ctx.fillStyle = '#fbbf24';
            ctx.font = `bold ${Math.max(7, r * 0.42)}px Arial`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`↑${tile.y}`, r - bw / 2, -r + bh / 2);
        }

        ctx.restore();
    });

    // Closing arrow (last → first)
    drawArrow(
        tiles[tiles.length - 1].x, tiles[tiles.length - 1].z,
        tiles[0].x, tiles[0].z,
        'rgba(251,191,36,0.5)'
    );
}

function drawArrow(x1, z1, x2, z2, color) {
    const ax = wx2cx(x1), ay = wz2cy(z1);
    const bx = wx2cx(x2), by = wz2cy(z2);
    const r  = tileR();
    const angle = Math.atan2(by - ay, bx - ax);
    const sx = ax + Math.cos(angle) * r;
    const sy = ay + Math.sin(angle) * r;
    const ex = bx - Math.cos(angle) * r;
    const ey = by - Math.sin(angle) * r;

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.stroke();
    ctx.setLineDash([]);

    const hs = 10;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(ex, ey);
    ctx.lineTo(ex - hs * Math.cos(angle - 0.4), ey - hs * Math.sin(angle - 0.4));
    ctx.lineTo(ex - hs * Math.cos(angle + 0.4), ey - hs * Math.sin(angle + 0.4));
    ctx.closePath(); ctx.fill();
}

// ── Drag system ───────────────────────────────────────────────────────────────
const DRAG_THRESHOLD = 5;  // px movement before treating as drag (not click)
let drag = {
    active:   false,
    index:    null,
    hasMoved: false,
    blocked:  false,  // true when movement is blocked by another tile
    offWX:    0,
    offWZ:    0,
    startCX:  0,
    startCY:  0,
    preState: null    // snapshot taken at drag start, committed to history if moved
};

// Commit (or discard) the snapshot taken when a drag began.
function commitDragHistory(moved) {
    if (drag.preState && moved) recordHistory(drag.preState);
    drag.preState = null;
}

function getCanvasPt(e) {
    const rect   = canvas.getBoundingClientRect();
    const scaleX = canvas.width  / rect.width;
    const scaleY = canvas.height / rect.height;
    const src    = e.touches ? e.touches[0] : e;
    return {
        cx: (src.clientX - rect.left) * scaleX,
        cy: (src.clientY - rect.top)  * scaleY
    };
}

function hitTest(cx, cy) {
    const wx = cx2wx(cx), wz = cy2wz(cy);
    // Iterate in reverse so tiles drawn on top get hit-tested first
    for (let i = boardConfig.tiles.length - 1; i >= 0; i--) {
        const t = boardConfig.tiles[i];
        const half = TILE_HALF * (t.size ?? 1);
        if (Math.abs(t.x - wx) <= half && Math.abs(t.z - wz) <= half) return i;
    }
    return null;
}

// Returns true if placing dragIdx at (nx, nz) would overlap any other tile
function wouldOverlap(dragIdx, nx, nz) {
    const tiles = boardConfig.tiles;
    const hd = TILE_HALF * (tiles[dragIdx].size ?? 1);
    for (let i = 0; i < tiles.length; i++) {
        if (i === dragIdx) continue;
        const t  = tiles[i];
        const hj = TILE_HALF * (t.size ?? 1);
        const minDist = hd + hj;
        if (Math.abs(nx - t.x) < minDist && Math.abs(nz - t.z) < minDist) return true;
    }
    return false;
}

function snapVal(v) {
    if (!document.getElementById('snapGrid').checked) return v;
    return Math.round(v / 0.5) * 0.5;
}

function onPointerDown(e) {
    const { cx, cy } = getCanvasPt(e);
    const hit = hitTest(cx, cy);

    drag.active   = hit !== null;
    drag.index    = hit;
    drag.startCX  = cx;
    drag.startCY  = cy;
    drag.hasMoved = false;

    if (hit !== null) {
        const t = boardConfig.tiles[hit];
        drag.offWX = cx2wx(cx) - t.x;
        drag.offWZ = cy2wz(cy) - t.z;
        drag.preState = snapshot();   // captured now; committed on pointer-up only if moved
        canvas.style.cursor = 'grabbing';
    }
}

function onPointerMove(e) {
    const { cx, cy } = getCanvasPt(e);

    if (!drag.active) {
        canvas.style.cursor = hitTest(cx, cy) !== null ? 'grab' : 'crosshair';
        return;
    }

    // Check drag threshold
    if (!drag.hasMoved) {
        if (Math.hypot(cx - drag.startCX, cy - drag.startCY) < DRAG_THRESHOLD) return;
        drag.hasMoved = true;
    }

    const tile = boardConfig.tiles[drag.index];
    const newX = snapVal(cx2wx(cx) - drag.offWX);
    const newZ = snapVal(cy2wz(cy) - drag.offWZ);

    // Collision: try full move, then slide along each axis independently
    if (!wouldOverlap(drag.index, newX, newZ)) {
        tile.x = newX;
        tile.z = newZ;
        drag.blocked = false;
    } else {
        const movedX = !wouldOverlap(drag.index, newX, tile.z);
        const movedZ = !wouldOverlap(drag.index, tile.x, newZ);
        if (movedX) tile.x = newX;
        if (movedZ) tile.z = newZ;
        drag.blocked = !movedX && !movedZ;
    }

    // Live-sync properties panel
    if (drag.index === selectedIndex) {
        document.getElementById('propX').value = tile.x;
        document.getElementById('propZ').value = tile.z;
    }

    drawBoard();
    renderTileList();
}

function onPointerUp(e) {
    if (!drag.active) return;

    const wasDrag = drag.hasMoved;
    const idx     = drag.index;

    commitDragHistory(wasDrag);

    drag.active   = false;
    drag.hasMoved = false;

    const { cx, cy } = drag.index !== null
        ? { cx: drag.startCX, cy: drag.startCY }
        : getCanvasPt(e);
    canvas.style.cursor = hitTest(cx, cy) !== null ? 'grab' : 'crosshair';

    if (idx !== null) {
        // Whether click or drag, always select the tile
        selectTile(idx);
    } else if (!wasDrag) {
        // Clicked empty space → deselect
        selectedIndex = null;
        document.getElementById('no-selection').style.display = 'block';
        document.getElementById('tile-props').style.display   = 'none';
        drawBoard();
        renderTileList();
    }
}

function onPointerLeave() {
    if (drag.active && drag.hasMoved) {
        // Finalize drag when mouse leaves canvas mid-drag
        commitDragHistory(true);
        drag.active = false;
        drag.hasMoved = false;
        if (drag.index !== null) selectTile(drag.index);
    }
    if (!drag.active) canvas.style.cursor = 'crosshair';
}

canvas.addEventListener('mousedown',  onPointerDown);
canvas.addEventListener('mousemove',  onPointerMove);
canvas.addEventListener('mouseup',    onPointerUp);
canvas.addEventListener('mouseleave', onPointerLeave);
canvas.addEventListener('touchstart', e => { e.preventDefault(); onPointerDown(e); }, { passive: false });
canvas.addEventListener('touchmove',  e => { e.preventDefault(); onPointerMove(e); }, { passive: false });
canvas.addEventListener('touchend',   e => { e.preventDefault(); onPointerUp(e);   }, { passive: false });

// ── Tile list (bottom bar) ────────────────────────────────────────────────────
function renderTileList() {
    const list = document.getElementById('tile-list-inner');
    list.innerHTML = '';
    boardConfig.tiles.forEach((tile, idx) => {
        const color = TILE_TYPES[tile.type]?.color || '#e0e0e0';
        const chip  = document.createElement('div');
        chip.className = 'tile-chip' + (idx === selectedIndex ? ' selected' : '');
        chip.style.background = color;
        chip.style.color = isLight(color) ? '#111' : '#fff';
        chip.innerHTML = `<span class="tile-chip-num">${idx}</span><span class="tile-chip-type">${TILE_TYPES[tile.type]?.label || tile.type}</span>`;
        chip.onclick = () => selectTile(idx);

        // Drag-to-reorder
        chip.draggable = true;
        chip.title = '拖曳可調整順序';
        chip.addEventListener('dragstart', e => {
            chipDrag.from = idx;
            chip.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', String(idx));   // Firefox needs payload
        });
        chip.addEventListener('dragend', () => {
            chip.classList.remove('dragging');
            chipDrag.from = null;
            clearChipDropMarkers();
        });
        chip.addEventListener('dragover', e => {
            if (chipDrag.from === null) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            const rect  = chip.getBoundingClientRect();
            const after = (e.clientX - rect.left) > rect.width / 2;
            clearChipDropMarkers();
            chip.classList.add(after ? 'drop-after' : 'drop-before');
        });
        chip.addEventListener('dragleave', () => {
            chip.classList.remove('drop-before', 'drop-after');
        });
        chip.addEventListener('drop', e => {
            if (chipDrag.from === null) return;
            e.preventDefault();
            const rect  = chip.getBoundingClientRect();
            const after = (e.clientX - rect.left) > rect.width / 2;
            clearChipDropMarkers();
            moveTile(chipDrag.from, after ? idx + 1 : idx);
        });

        list.appendChild(chip);
    });
    // scroll selected chip into view
    if (selectedIndex !== null) {
        const chips = list.querySelectorAll('.tile-chip');
        chips[selectedIndex]?.scrollIntoView({ block: 'nearest', inline: 'center' });
    }
}

function isLight(hex) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return (r*299 + g*587 + b*114) / 1000 > 155;
}

// ── Reorder tiles (drag chips in the bottom bar) ──────────────────────────────
let chipDrag = { from: null };

function clearChipDropMarkers() {
    document.querySelectorAll('.tile-chip.drop-before, .tile-chip.drop-after')
        .forEach(c => c.classList.remove('drop-before', 'drop-after'));
}

// Move the tile at index `from` to insertion position `target` (0..length).
function moveTile(from, target) {
    const tiles = boardConfig.tiles;
    let dest = target > from ? target - 1 : target;   // removal shifts later indices
    dest = Math.max(0, Math.min(tiles.length - 1, dest));
    if (dest === from) return;                         // no-op, skip history
    pushHistory();
    const [moved] = tiles.splice(from, 1);
    tiles.splice(dest, 0, moved);
    selectTile(dest);
}

// ── Legend ────────────────────────────────────────────────────────────────────
function renderLegend() {
    document.getElementById('canvas-legend').innerHTML =
        Object.entries(TILE_TYPES).map(([k,v]) =>
            `<div class="legend-item">
                <div class="legend-swatch" style="background:${v.color}"></div>
                <span>${v.label}</span>
             </div>`
        ).join('');
}

// ── Select tile ───────────────────────────────────────────────────────────────
function selectTile(idx) {
    selectedIndex = idx;
    const tile = boardConfig.tiles[idx];

    document.getElementById('no-selection').style.display  = 'none';
    document.getElementById('tile-props').style.display    = 'block';
    document.getElementById('tileIdxLabel').textContent    = idx;
    document.getElementById('propX').value    = tile.x;
    document.getElementById('propZ').value    = tile.z;
    document.getElementById('propY').value    = tile.y;
    document.getElementById('propYNum').value = tile.y;
    document.getElementById('propSize').value    = tile.size ?? 1;
    document.getElementById('propSizeNum').value = tile.size ?? 1;
    document.getElementById('propLabel').value = tile.label || '';

    renderTypeGrid(tile.type);
    drawBoard();
    renderTileList();
}

function renderTypeGrid(current) {
    const grid = document.getElementById('typeGrid');
    grid.innerHTML = '';
    Object.entries(TILE_TYPES).forEach(([key, val]) => {
        const btn = document.createElement('div');
        btn.className = 'type-btn' + (key === current ? ' selected' : '');
        btn.style.background = val.color;
        btn.style.color = isLight(val.color) ? '#111' : '#fff';
        btn.textContent = val.label;
        btn.onclick = () => {
            if (boardConfig.tiles[selectedIndex]?.type === key) return;
            pushHistory();
            updateProp('type', key);
            renderTypeGrid(key);
        };
        grid.appendChild(btn);
    });
}

// ── Property updates ──────────────────────────────────────────────────────────
function updateProp(key, value) {
    if (selectedIndex === null) return;
    boardConfig.tiles[selectedIndex][key] = value;
    drawBoard();
    renderTileList();
}

function syncHeight(val) {
    const v = parseFloat(val);
    if (isNaN(v)) return;
    document.getElementById('propY').value    = v;
    document.getElementById('propYNum').value = v;
    updateProp('y', v);
}

function syncSize(val) {
    const v = Math.round(parseFloat(val) * 10) / 10;
    if (isNaN(v)) return;
    document.getElementById('propSize').value    = v;
    document.getElementById('propSizeNum').value = v;
    updateProp('size', v);
}

// ── Overlap helpers ───────────────────────────────────────────────────────────
// True if a tile of the given size placed at (nx,nz) would overlap any existing
// tile (ignoreIdx is skipped; pass -1 to test against all tiles).
function overlapsAny(nx, nz, size, ignoreIdx) {
    const hd    = TILE_HALF * (size ?? 1);
    const tiles = boardConfig.tiles;
    for (let i = 0; i < tiles.length; i++) {
        if (i === ignoreIdx) continue;
        const t  = tiles[i];
        const hj = TILE_HALF * (t.size ?? 1);
        const minDist = hd + hj;
        if (Math.abs(nx - t.x) < minDist && Math.abs(nz - t.z) < minDist) return true;
    }
    return false;
}

// Find the nearest free spot to (nx,nz) for a tile of the given size, spiralling out.
function findFreeSpot(nx, nz, size) {
    if (!overlapsAny(nx, nz, size, -1)) return { x: nx, z: nz };
    for (let r = 0.5; r <= 12; r += 0.5) {
        for (let a = 0; a < 360; a += 45) {
            const rad = a * Math.PI / 180;
            const tx = Math.round((nx + Math.cos(rad) * r) / 0.5) * 0.5;
            const tz = Math.round((nz + Math.sin(rad) * r) / 0.5) * 0.5;
            if (!overlapsAny(tx, tz, size, -1)) return { x: tx, z: tz };
        }
    }
    return { x: nx, z: nz };
}

// ── Add / Insert / Delete tiles ───────────────────────────────────────────────────────────────
function addTile() {
    pushHistory();
    const tiles = boardConfig.tiles;
    const last  = tiles[tiles.length - 1] || { x: 0, z: 0 };
    const spot  = findFreeSpot(last.x + 4, last.z, 1);
    tiles.push({ x: spot.x, z: spot.z, y: 0, type: 'grass', label: '', size: 1 });
    drawBoard();
    renderTileList();
    selectTile(tiles.length - 1);
}

// Insert a new tile into the path right after the selected one (between it and the
// next tile). With no selection, falls back to appending at the end.
function insertTileAfter() {
    const tiles = boardConfig.tiles;
    if (selectedIndex === null) { addTile(); return; }
    pushHistory();
    const cur  = tiles[selectedIndex];
    const next = tiles[(selectedIndex + 1) % tiles.length];
    const midX = (cur.x + next.x) / 2;
    const midZ = (cur.z + next.z) / 2;
    const midY = Math.round(((cur.y + next.y) / 2) / 0.5) * 0.5;
    const spot = findFreeSpot(midX, midZ, 1);
    tiles.splice(selectedIndex + 1, 0, {
        x: spot.x, z: spot.z, y: midY, type: 'grass', label: '', size: 1
    });
    selectTile(selectedIndex + 1);   // selects the newly inserted tile
}

function deleteSelectedTile() {
    if (selectedIndex === null) return;
    if (boardConfig.tiles.length <= 2) { alert('至少需要 2 個格子'); return; }
    if (!confirm(`確定刪除格子 #${selectedIndex}？`)) return;
    pushHistory();
    boardConfig.tiles.splice(selectedIndex, 1);
    selectedIndex = null;
    document.getElementById('no-selection').style.display = 'block';
    document.getElementById('tile-props').style.display   = 'none';
    drawBoard();
    renderTileList();
}

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetToDefault() {
    if (!confirm('確定重設為預設棋盤？目前修改將遺失。')) return;
    pushHistory();
    boardConfig.tiles     = getDefaultTiles();
    boardConfig.boardName = 'Custom Board';
    document.getElementById('boardName').value = 'Custom Board';
    selectedIndex = null;
    document.getElementById('no-selection').style.display = 'block';
    document.getElementById('tile-props').style.display   = 'none';
    fitViewport();
    resizeCanvas();   // re-fit canvas to new viewport + redraw
    renderTileList();
    saveToGame();
}

// ── Auto-layout generator ─────────────────────────────────────────────────────
let genShape = 'rect';

const snap05 = v => Math.round(v / 0.5) * 0.5;

function openGenModal()  { document.getElementById('gen-modal').style.display = 'flex'; }
function closeGenModal() { document.getElementById('gen-modal').style.display = 'none'; }

function selectGenShape(s) {
    genShape = s;
    document.querySelectorAll('#gen-shape-grid .gen-shape-btn')
        .forEach(b => b.classList.toggle('selected', b.dataset.shape === s));
}

// Rectangle loop (Monopoly style). Perimeter is always even, so N rounds up to even.
function genRect(N, d) {
    if (N % 2) N++;
    const half = N / 2;                       // = a + b (tiles per width + height)
    let a = Math.max(1, Math.round(half * 1.6 / 2.6));
    let b = half - a;
    if (b < 1) { b = 1; a = half - 1; }
    const ox = a * d / 2, oz = b * d / 2;
    const pts = [];
    for (let i = 0; i < a; i++) pts.push([i, 0]);   // top
    for (let j = 0; j < b; j++) pts.push([a, j]);   // right
    for (let i = a; i > 0; i--) pts.push([i, b]);   // bottom
    for (let j = b; j > 0; j--) pts.push([0, j]);   // left
    return pts.map(([gx, gy]) => ({
        x: snap05(gx * d - ox), z: snap05(gy * d - oz),
        y: 0, type: 'grass', label: '', size: 1
    }));
}

// Evenly spaced ring of N tiles.
function genCircle(N, d) {
    const r = d / (2 * Math.sin(Math.PI / N));
    const out = [];
    for (let i = 0; i < N; i++) {
        const th = (2 * Math.PI * i) / N - Math.PI / 2;   // start at top
        out.push({ x: snap05(r * Math.cos(th)), z: snap05(r * Math.sin(th)),
                   y: 0, type: 'grass', label: '', size: 1 });
    }
    return out;
}

// Archimedean spiral with ~constant tile spacing, centred on its centroid.
function genSpiral(N, d) {
    const turnGap = Math.max(d, 4);            // radial gap between successive loops
    const b  = turnGap / (2 * Math.PI);
    const r0 = turnGap;
    const out = [];
    let th = 0;
    for (let i = 0; i < N; i++) {
        const r = r0 + b * th;
        out.push({ x: r * Math.cos(th), z: r * Math.sin(th),
                   y: 0, type: 'grass', label: '', size: 1 });
        th += d / Math.max(r, d);
    }
    const cx = out.reduce((s, o) => s + o.x, 0) / out.length;
    const cz = out.reduce((s, o) => s + o.z, 0) / out.length;
    out.forEach(o => { o.x = snap05(o.x - cx); o.z = snap05(o.z - cz); });
    return out;
}

function applyHeights(tiles, mode) {
    if (mode === 'random') tiles.forEach(t => t.y = snap05(Math.random() * 3));
    else                   tiles.forEach(t => t.y = 0);
}

function generateLayout() {
    let count = parseInt(document.getElementById('genCount').value, 10);
    let d     = parseFloat(document.getElementById('genSpacing').value);
    if (isNaN(count) || count < 4) count = 4;
    if (count > 60) count = 60;
    if (isNaN(d) || d < 2) d = 2;
    const heightMode = document.getElementById('genHeight').value;

    let tiles = genShape === 'circle' ? genCircle(count, d)
              : genShape === 'spiral' ? genSpiral(count, d)
              :                         genRect(count, d);

    applyHeights(tiles, heightMode);
    tiles[0].type = 'start'; tiles[0].label = 'GO'; tiles[0].y = 0;   // tag the GO tile

    pushHistory();
    boardConfig.tiles = tiles;
    selectedIndex = null;
    document.getElementById('no-selection').style.display = 'block';
    document.getElementById('tile-props').style.display   = 'none';
    fitViewport();
    resizeCanvas();   // re-fit canvas + redraw
    renderTileList();
    closeGenModal();
}

// ── BoardStyle directory handle (session-level) ──────────────────────────────
let boardStyleDirHandle = null;

async function ensureDirHandle() {
    if (boardStyleDirHandle) return boardStyleDirHandle;
    try {
        boardStyleDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
    } catch(e) {
        if (e.name !== 'AbortError') alert('無法開啟資料夾：' + e.message);
    }
    return boardStyleDirHandle;
}

async function changeBoardStyleDir() {
    boardStyleDirHandle = null;
    await ensureDirHandle();
    await updateImportList();
}

async function showImportDialog() {
    if (!window.showDirectoryPicker) { document.getElementById('fileInput').click(); return; }
    document.getElementById('import-modal').style.display = 'flex';
    await ensureDirHandle();
    await updateImportList();
}

async function updateImportList() {
    const listEl   = document.getElementById('import-file-list');
    const dirLabel = document.getElementById('import-dir-name');
    if (!boardStyleDirHandle) {
        listEl.innerHTML = '<div style="color:#484f58;text-align:center;padding:24px;font-size:0.85rem;">請選擇 BoardStyle 資料夾</div>';
        dirLabel.textContent = '未選擇資料夾';
        return;
    }
    dirLabel.textContent = boardStyleDirHandle.name;
    listEl.innerHTML = '<div style="color:#8b949e;text-align:center;padding:16px;font-size:0.82rem;">載入中…</div>';

    const validFiles = [];
    for await (const [name, handle] of boardStyleDirHandle.entries()) {
        if (handle.kind !== 'file' || !name.endsWith('.json')) continue;
        try {
            const data = JSON.parse(await (await handle.getFile()).text());
            if (Array.isArray(data.tiles)) validFiles.push({ name, data });
        } catch(e) {}
    }

    if (validFiles.length === 0) {
        listEl.innerHTML = '<div style="color:#484f58;text-align:center;padding:24px;font-size:0.85rem;">此資料夾中沒有有效的棋盤 JSON 檔案</div>';
        return;
    }

    listEl.innerHTML = '';
    validFiles.sort((a, b) => a.name.localeCompare(b.name)).forEach(({ name, data }) => {
        const btn = document.createElement('button');
        btn.style.cssText = 'text-align:left;padding:12px 14px;background:#0d1117;border:1px solid #21262d;border-radius:8px;color:#c9d1d9;cursor:pointer;width:100%;';
        btn.innerHTML = `<div style="font-weight:600;font-size:0.88rem;">${data.boardName || '未命名'}</div>
                         <div style="font-size:0.73rem;color:#8b949e;margin-top:3px;">${name} ・ ${data.tiles.length} 格</div>`;
        btn.onmouseenter = () => { btn.style.background = '#1c2128'; btn.style.borderColor = '#58a6ff'; };
        btn.onmouseleave = () => { btn.style.background = '#0d1117'; btn.style.borderColor = '#21262d'; };
        btn.onclick = () => { applyImportData(data); closeImportModal(); };
        listEl.appendChild(btn);
    });
}

function closeImportModal() {
    document.getElementById('import-modal').style.display = 'none';
}

function applyImportData(data) {
    pushHistory();
    boardConfig = data;
    document.getElementById('boardName').value = data.boardName || 'Custom Board';
    selectedIndex = null;
    document.getElementById('no-selection').style.display = 'block';
    document.getElementById('tile-props').style.display   = 'none';
    fitViewport();
    resizeCanvas();
    renderTileList();
    saveToGame();
    alert(`✅ 已匯入「${data.boardName || '未命名'}」（${data.tiles.length} 個格子）`);
}

// ── Export JSON ───────────────────────────────────────────────────────────────
async function exportJSON() {
    boardConfig.boardName = document.getElementById('boardName').value.trim() || 'Custom Board';
    const json     = JSON.stringify(boardConfig, null, 2);
    const filename = `${boardConfig.boardName.replace(/\s+/g, '_')}_board.json`;

    if (!window.showDirectoryPicker) {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
        a.download = filename;
        a.click();
        return;
    }

    const dir = await ensureDirHandle();
    if (!dir) return;
    try {
        const fh       = await dir.getFileHandle(filename, { create: true });
        const writable = await fh.createWritable();
        await writable.write(json);
        await writable.close();
        alert(`✅ 已儲存「${filename}」至 ${dir.name}/`);
    } catch(e) {
        alert('匯出失敗：' + e.message);
    }
}

// ── Import JSON (fallback for browsers without File System Access API) ────────
function handleFileImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
        try {
            const data = JSON.parse(ev.target.result);
            if (!Array.isArray(data.tiles)) throw new Error('缺少 tiles 陣列');
            applyImportData(data);
        } catch (err) {
            alert('❌ 匯入失敗：' + err.message);
        }
    };
    reader.readAsText(file);
    e.target.value = '';
}

// ── Save to game (silent) ──────────────────────────────────────────────────────────
function saveToGame() {
    boardConfig.boardName = document.getElementById('boardName').value.trim() || 'Custom Board';
    localStorage.setItem('pypoly_board_config', JSON.stringify(boardConfig));
}

// ── Apply to game (manual button — same as saveToGame but with confirmation) ──
function applyToGame() {
    saveToGame();
    alert(`✅ 已套用「${boardConfig.boardName}」（${boardConfig.tiles.length} 格）\n\n開啟 game.html?preview=1 即可預覽效果。`);
}

// ── Tile image cache ──────────────────────────────────────────────────────────
const tileImgCache = {};
let   tileImgCacheReady = false;

function preloadTileTextures(onReady) {
    if (tileImgCacheReady) { onReady(); return; }
    const types = ['start','grass','stone','sand','ice','lava','event'];
    let pending = types.length;
    function done() { if (--pending === 0) { tileImgCacheReady = true; onReady(); } }
    types.forEach(t => {
        const img = new Image();
        img.onload = () => {
            try {
                const test = document.createElement('canvas');
                test.width = test.height = 1;
                test.getContext('2d').drawImage(img, 0, 0, 1, 1);
                test.toDataURL();
                const tex = new THREE.Texture(img);
                tex.needsUpdate = true;
                tileImgCache[t] = tex;
            } catch(e) { /* cross-origin (file://) — procedural fallback will be used */ }
            done();
        };
        img.onerror = () => done();
        img.src = `img/tiles/${t}.png`;
    });
}

// ── Tile canvas helper (shared by 2D legend + 3D texture) ────────────────────
function makeTileCanvas(type, label) {
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const ctx = c.getContext('2d');
    const palette = {
        start: ['#00cdac','#008f78'], grass: ['#66bb6a','#388e3c'],
        stone: ['#90a4ae','#546e7a'], sand:  ['#ffca28','#f9a825'],
        ice:   ['#80deea','#00acc1'], lava:  ['#ff7043','#bf360c'],
        event: ['#ce93d8','#7b1fa2']
    };
    const [light, dark] = palette[type] || ['#e0e0e0','#9e9e9e'];

    ctx.fillStyle = light; ctx.fillRect(0, 0, 128, 128);
    if (type === 'grass') {
        ctx.fillStyle = dark;
        for (let r = 0; r < 12; r++)
            ctx.fillRect(8 + (r%4)*30, 10 + Math.floor(r/4)*30, 5, 12);
    } else if (type === 'stone') {
        ctx.strokeStyle = dark; ctx.lineWidth = 3;
        for (let row = 0; row < 4; row++) {
            const xoff = (row%2)*32;
            for (let col = 0; col < 3; col++)
                ctx.strokeRect(xoff + col*64 - 28, row*32 + 5, 56, 24);
        }
    } else if (type === 'sand') {
        ctx.strokeStyle = dark; ctx.lineWidth = 2;
        for (let row = 0; row < 5; row++) {
            ctx.beginPath();
            for (let x = 0; x <= 128; x += 8) {
                const y = row*26 + 12 + Math.sin(x*0.15)*5;
                x === 0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
            }
            ctx.stroke();
        }
    } else if (type === 'ice') {
        ctx.strokeStyle = 'rgba(255,255,255,0.75)'; ctx.lineWidth = 2;
        for (let a = 0; a < 6; a++) {
            const ang = (a*Math.PI)/3;
            ctx.beginPath(); ctx.moveTo(64,64);
            ctx.lineTo(64 + Math.cos(ang)*44, 64 + Math.sin(ang)*44); ctx.stroke();
        }
    } else if (type === 'lava') {
        ctx.strokeStyle = '#ffcc02'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(18,22); ctx.lineTo(58,58); ctx.lineTo(30,108); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(88,18); ctx.lineTo(106,68); ctx.lineTo(68,108); ctx.stroke();
    }

    const text = (label && label !== '') ? label
               : type === 'start' ? 'GO' : type === 'event' ? '?' : null;
    if (text) {
        const fs = text.length > 3 ? 34 : text.length > 2 ? 44 : 52;
        ctx.fillStyle = dark; ctx.font = `bold ${fs}px Arial`;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(text, 64, 65);
    }
    ctx.strokeStyle = 'rgba(0,0,0,0.3)'; ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, 124, 124);
    return c;
}

// Returns a THREE.Texture for 3D use: cached texture when possible, procedural canvas as fallback
function getTile3DTexture(type, label) {
    const defaultLabel = type === 'start' ? 'GO' : type === 'event' ? '?' : null;
    const hasCustomLabel = label != null && label !== '' && label !== defaultLabel;
    if (tileImgCache[type] && !hasCustomLabel) {
        return tileImgCache[type];
    }
    return new THREE.CanvasTexture(makeTileCanvas(type, label));
}

// ── Plan C: 格子邊緣發光 ───────────────────────────────────────────────────────
function addTileEdgeGlow(scene, td, s) {
    const glowColors = {
        start: 0x00cdac, grass: 0x4caf50, stone: 0x78909c,
        sand:  0xffd740, ice:   0x40c4ff, lava:  0xff6e40, event: 0xce93d8
    };
    const color = glowColors[td.type] || 0xffffff;
    const edgeLine = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(3.5, 0.5, 3.5)),
        new THREE.LineBasicMaterial({ color })
    );
    edgeLine.scale.set(s, 1, s);
    edgeLine.position.set(td.x, td.y, td.z);
    scene.add(edgeLine);
}

// ── Plan A: 格子裝飾物件 ───────────────────────────────────────────────────────
function addTileProps(scene, td, s) {
    const bx = td.x, top = td.y + 0.25, bz = td.z;
    if (td.type === 'grass') {
        const tMat = new THREE.MeshStandardMaterial({ color: 0x5d4037, roughness: 1 });
        const cMat = new THREE.MeshStandardMaterial({ color: 0x2e7d32, roughness: 0.9 });
        [[-0.65 * s, -0.55 * s], [0.55 * s, 0.50 * s]].forEach(([ox, oz]) => {
            const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.10, 0.44, 6), tMat);
            trunk.position.set(bx + ox, top + 0.22, bz + oz);
            scene.add(trunk);
            const crown = new THREE.Mesh(new THREE.SphereGeometry(0.29, 7, 5), cMat);
            crown.position.set(bx + ox, top + 0.60, bz + oz);
            scene.add(crown);
        });
    } else if (td.type === 'stone') {
        const rMat = new THREE.MeshStandardMaterial({ color: 0x78909c, roughness: 1, flatShading: true });
        const rots = [[0.6, 0.8, 0.4], [0.3, 2.1, 0.7], [1.1, 1.4, 0.2]];
        [[0.55 * s, -0.40 * s, 0.19], [-0.50 * s, 0.40 * s, 0.16], [0.10 * s, 0.60 * s, 0.13]].forEach(([ox, oz, rs], ri) => {
            const rock = new THREE.Mesh(new THREE.OctahedronGeometry(rs, 0), rMat);
            rock.rotation.set(rots[ri][0], rots[ri][1], rots[ri][2]);
            rock.position.set(bx + ox, top + rs * 0.6, bz + oz);
            scene.add(rock);
        });
    } else if (td.type === 'sand') {
        const cMat = new THREE.MeshStandardMaterial({ color: 0x558b2f, roughness: 0.9 });
        const body = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 0.65, 8), cMat);
        body.position.set(bx, top + 0.325, bz);
        scene.add(body);
        const armL = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.28, 7), cMat);
        armL.rotation.z = Math.PI / 2.2;
        armL.position.set(bx - 0.22, top + 0.46, bz);
        scene.add(armL);
        const armR = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.24, 7), cMat);
        armR.rotation.z = -Math.PI / 2.4;
        armR.position.set(bx + 0.20, top + 0.40, bz);
        scene.add(armR);
    } else if (td.type === 'ice') {
        const iMat = new THREE.MeshStandardMaterial({
            color: 0xb3e5fc, transparent: true, opacity: 0.82, roughness: 0.1, metalness: 0.3
        });
        [[-0.45 * s, -0.35 * s, 0.60], [0.35 * s, 0.40 * s, 0.45], [0.05 * s, -0.55 * s, 0.72]].forEach(([ox, oz, ch]) => {
            const crystal = new THREE.Mesh(new THREE.ConeGeometry(0.10, ch, 4), iMat);
            crystal.position.set(bx + ox, top + ch / 2, bz + oz);
            scene.add(crystal);
        });
    } else if (td.type === 'lava') {
        const outerFlame = new THREE.Mesh(
            new THREE.ConeGeometry(0.28, 0.80, 6),
            new THREE.MeshStandardMaterial({ color: 0xff6d00, emissive: 0xff3d00, emissiveIntensity: 0.9, roughness: 0.6 })
        );
        outerFlame.position.set(bx, top + 0.40, bz);
        scene.add(outerFlame);
        const innerFlame = new THREE.Mesh(
            new THREE.ConeGeometry(0.14, 0.60, 6),
            new THREE.MeshStandardMaterial({ color: 0xffff00, emissive: 0xffcc00, emissiveIntensity: 1.2, roughness: 0.5 })
        );
        innerFlame.position.set(bx, top + 0.44, bz);
        scene.add(innerFlame);
    }
}

// ── Plan E: 環境（水面 + 遠山） ───────────────────────────────────────────────────────
function createEnvironment(scene) {
    const water = new THREE.Mesh(
        new THREE.PlaneGeometry(220, 220),
        new THREE.MeshStandardMaterial({ color: 0x1976d2, transparent: true, opacity: 0.72, roughness: 0.05, metalness: 0.15 })
    );
    water.rotation.x = -Math.PI / 2;
    water.position.y = -0.55;
    scene.add(water);

    const mtnData = [
        [-62, -52, 14, 12, 6], [-35, -58, 11, 10, 5], [  5, -60,  9, 14, 7],
        [ 45, -54, 12, 10, 5], [ 68, -46, 15, 13, 6], [-68,  24, 10, 15, 5],
        [ 62,  22, 13, 11, 6], [-52,  50,  8, 10, 4], [ 50,  48, 10, 12, 5],
        [-18, -57,  7,  9, 4], [ 26, -55,  9,  8, 5], [  0, -62, 11, 11, 6],
    ];
    const mColors = [0x4a6741, 0x556b2f, 0x3d5c34, 0x4e6b45, 0x607d5a];
    mtnData.forEach(([mx, mz, r, h, segs], i) => {
        const mtn = new THREE.Mesh(
            new THREE.ConeGeometry(r, h, segs),
            new THREE.MeshStandardMaterial({ color: mColors[i % 5], roughness: 1, flatShading: true })
        );
        mtn.position.set(mx, h / 2 - 0.5, mz);
        scene.add(mtn);
    });
}

// ── Plan D: 路徑橋接 ───────────────────────────────────────────────────────────────
function buildTileConnectors(scene, tiles) {
    const mat = new THREE.MeshStandardMaterial({ color: 0x8d9eab, roughness: 0.85, metalness: 0.05 });
    const SLAB_H  = 0.22;
    const OVERLAP = 0.15;

    for (let i = 0; i < tiles.length; i++) {
        const a  = tiles[i];
        const b  = tiles[(i + 1) % tiles.length];
        const sa = a.size ?? 1;
        const sb = b.size ?? 1;

        const dx = b.x - a.x, dz = b.z - a.z;
        const hd = Math.sqrt(dx * dx + dz * dz);
        if (hd < 0.01) continue;
        const nx = dx / hd, nz = dz / hd;

        const sx = a.x + nx * (1.75 * sa - OVERLAP), sy = a.y + 0.25, sz = a.z + nz * (1.75 * sa - OVERLAP);
        const ex = b.x - nx * (1.75 * sb - OVERLAP), ey = b.y + 0.25, ez = b.z - nz * (1.75 * sb - OVERLAP);

        const len = Math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2 + (ez - sz) ** 2);
        if (len < 0.05) continue;

        const connW = Math.min(sa, sb) * 1.8;
        const conn = new THREE.Mesh(new THREE.BoxGeometry(len, SLAB_H, connW), mat);
        conn.position.set((sx + ex) / 2, (sy + ey) / 2, (sz + ez) / 2);
        conn.setRotationFromQuaternion(
            new THREE.Quaternion().setFromUnitVectors(
                new THREE.Vector3(1, 0, 0),
                new THREE.Vector3(ex - sx, ey - sy, ez - sz).normalize()
            )
        );
        scene.add(conn);
    }
}

// ── 3D Preview ───────────────────────────────────────────────────────────────
let viewMode   = '2d';
let threeState = null;

function switchView(mode) {
    if (mode === viewMode) return;
    viewMode = mode;
    document.getElementById('btn2d').classList.toggle('active', mode === '2d');
    document.getElementById('btn3d').classList.toggle('active', mode === '3d');
    document.getElementById('edit-tools').style.display = mode === '2d' ? 'flex' : 'none';

    if (mode === '3d') {
        if (typeof THREE === 'undefined') {
            alert('Three.js 尚未載入，請確認網路連線後重試。');
            switchView('2d'); return;
        }
        document.getElementById('canvas-area').style.display  = 'none';
        document.getElementById('view3d-area').style.display  = 'flex';
        init3D();
    } else {
        document.getElementById('view3d-area').style.display  = 'none';
        document.getElementById('canvas-area').style.display  = 'flex';
        dispose3D();
        resizeCanvas();
    }
}

function init3D() {
    dispose3D();
    const mount = document.getElementById('threejs-mount');
    const W = mount.clientWidth, H = mount.clientHeight;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87ceeb);
    scene.fog = new THREE.Fog(0x87ceeb, 70, 160);

    const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 500);
    camera.position.set(0, 28, 45);
    camera.lookAt(0, 0, 0);

    scene.add(new THREE.HemisphereLight(0x87ceeb, 0x5d8a3c, 0.9));
    const sun = new THREE.DirectionalLight(0xfffde7, 0.9);
    sun.position.set(20, 40, 20);
    scene.add(sun);

    preloadTileTextures(function() { build3DBoard(scene); });

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping  = true;
    controls.dampingFactor  = 0.06;
    controls.minDistance    = 8;
    controls.maxDistance    = 120;
    controls.target.set(0, 1, 0);
    controls.update();

    let animId;
    function animate() {
        animId = requestAnimationFrame(animate);
        controls.autoRotate = document.getElementById('autoRotate')?.checked ?? false;
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    threeState = { renderer, scene, camera, controls, animId };
    window.addEventListener('resize', on3DResize);
}

function build3DBoard(scene) {
    const tileGeo = new THREE.BoxGeometry(3.5, 0.5, 3.5);

    boardConfig.tiles.forEach((td, idx) => {
        const mat = new THREE.MeshStandardMaterial({
            map: getTile3DTexture(td.type, td.label),
            roughness: 0.8, metalness: 0.05
        });
        const tile = new THREE.Mesh(tileGeo, mat);
        const s = td.size ?? 1;
        tile.scale.set(s, 1, s);
        tile.position.set(td.x, td.y, td.z);
        scene.add(tile);
        addTileEdgeGlow(scene, td, s);
        addTileProps(scene, td, s);

        if (td.y > 0.4) {
            const p = new THREE.Mesh(
                new THREE.BoxGeometry(3.0, td.y, 3.0),
                new THREE.MeshStandardMaterial({ color: 0x78909c, roughness: 0.9 })
            );
            p.scale.set(s, 1, s);
            p.position.set(td.x, td.y / 2 - 0.25, td.z);
            scene.add(p);
        }

        if (td.type === 'event') {
            const mc = document.createElement('canvas');
            mc.width = mc.height = 64;
            const mctx = mc.getContext('2d');
            mctx.fillStyle = '#9c27b0';
            mctx.beginPath(); mctx.arc(32, 32, 28, 0, Math.PI * 2); mctx.fill();
            mctx.fillStyle = '#fff'; mctx.font = 'bold 38px Arial';
            mctx.textAlign = 'center'; mctx.textBaseline = 'middle';
            mctx.fillText('?', 32, 34);
            const sp = new THREE.Sprite(new THREE.SpriteMaterial({
                map: new THREE.CanvasTexture(mc), transparent: true
            }));
            sp.scale.set(1.4, 1.4, 1);
            sp.position.set(td.x, td.y + 2.2, td.z);
            scene.add(sp);
        }

        const nc = document.createElement('canvas');
        nc.width = nc.height = 64;
        const nctx = nc.getContext('2d');
        nctx.fillStyle = 'rgba(0,0,0,0.65)';
        nctx.beginPath(); nctx.arc(32, 32, 26, 0, Math.PI * 2); nctx.fill();
        nctx.fillStyle = '#fff'; nctx.font = 'bold 28px monospace';
        nctx.textAlign = 'center'; nctx.textBaseline = 'middle';
        nctx.fillText(idx, 32, 33);
        const ns = new THREE.Sprite(new THREE.SpriteMaterial({
            map: new THREE.CanvasTexture(nc), transparent: true
        }));
        ns.scale.set(1.2, 1.2, 1);
        ns.position.set(td.x, td.y + 1.0, td.z);
        scene.add(ns);
    });
    buildTileConnectors(scene, boardConfig.tiles);

    const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(60, 34),
        new THREE.MeshStandardMaterial({ color: 0x7cb342, roughness: 1.0 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.3;
    scene.add(ground);
    createEnvironment(scene);
}

function dispose3D() {
    if (!threeState) return;
    cancelAnimationFrame(threeState.animId);
    threeState.controls.dispose();
    threeState.renderer.dispose();
    const mount = document.getElementById('threejs-mount');
    while (mount.firstChild) mount.removeChild(mount.firstChild);
    window.removeEventListener('resize', on3DResize);
    threeState = null;
}

function on3DResize() {
    if (!threeState) return;
    const mount = document.getElementById('threejs-mount');
    const W = mount.clientWidth, H = mount.clientHeight;
    threeState.camera.aspect = W / H;
    threeState.camera.updateProjectionMatrix();
    threeState.renderer.setSize(W, H);
}

// ── Init ──────────────────────────────────────────────────────────────────────
try {
    const saved = localStorage.getItem('pypoly_board_config');
    if (saved) {
        const data = JSON.parse(saved);
        if (Array.isArray(data.tiles)) {
            boardConfig = data;
            document.getElementById('boardName').value = data.boardName || 'Custom Board';
        }
    }
} catch(e) {}

['propX','propZ','propY','propYNum','propSize','propSizeNum','propLabel'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('focus', () => { pendingSnapshot = snapshot(); });
    el.addEventListener('input', () => {
        if (pendingSnapshot) { recordHistory(pendingSnapshot); pendingSnapshot = null; }
    });
    el.addEventListener('blur',  () => { pendingSnapshot = null; });
});

window.addEventListener('keydown', e => {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.target.matches && e.target.matches('input, textarea')) return;
    const k = e.key.toLowerCase();
    if (k === 'z' && !e.shiftKey)            { e.preventDefault(); undo(); }
    else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); redo(); }
});

window.addEventListener('resize', resizeCanvas);
renderLegend();
fitViewport();
resizeCanvas();
renderTileList();
updateUndoButtons();
