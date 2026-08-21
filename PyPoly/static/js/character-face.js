// =========================================================
// PyPoly 角色臉部合成（character.html 與 game.html 共用）
//
// 為什麼要抽出來：資料庫只存角色的「配方」（顏色 + 五官 ID），
// 不存合成後的圖片。原因是配方約 200 bytes、成品圖要數百 KB，
// 而且角色形式日後改版時成品圖會直接報廢、配方仍可重新渲染。
// 既然只存配方，game.html 就必須有能力自行把臉畫出來——
// 它原本只會套用現成的圖，所以把繪製邏輯集中在這裡給兩邊共用，
// 避免同一套畫法在兩個檔案裡各留一份而逐漸分歧。
// =========================================================

// 臉部貼圖的尺寸（3D 模型的 UV 依此對應，改動需同步調整模型）
const FACE_TEXTURE_SIZE = 512;

function drawFaceFeatures(ctx, W, H, feats) {
    const s   = H / 128;
    const LEX = W * 0.32, REX = W * 0.68;
    const EYY = H * 0.46;
    const BRY = H * 0.30;
    const NCX = W * 0.50, NCY = H * 0.63;
    const MCX = W * 0.50, MCY = H * 0.80;

    ctx.save();

    // ── Eyebrows ──
    const brow = feats.eyebrow;
    if (brow !== 'none') {
        ctx.strokeStyle = '#3d1f0a'; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
        const bw = 22 * s, bh = 7 * s;
        if (brow === 'standard') {
            ctx.lineWidth = 3.5 * s;
            [[LEX,BRY],[REX,BRY]].forEach(([cx,cy]) => {
                ctx.beginPath(); ctx.moveTo(cx-bw, cy); ctx.lineTo(cx+bw, cy); ctx.stroke();
            });
        } else if (brow === 'arch') {
            ctx.lineWidth = 3 * s;
            [[LEX,BRY],[REX,BRY]].forEach(([cx,cy]) => {
                ctx.beginPath(); ctx.moveTo(cx-bw, cy+bh*0.6); ctx.quadraticCurveTo(cx, cy-bh, cx+bw, cy+bh*0.6); ctx.stroke();
            });
        } else if (brow === 'angry') {
            ctx.lineWidth = 3.5 * s;
            ctx.beginPath(); ctx.moveTo(LEX-bw, BRY-bh); ctx.lineTo(LEX+bw, BRY+bh); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(REX-bw, BRY+bh); ctx.lineTo(REX+bw, BRY-bh); ctx.stroke();
        } else if (brow === 'thick') {
            ctx.lineWidth = 7.5 * s;
            [[LEX,BRY],[REX,BRY]].forEach(([cx,cy]) => {
                ctx.beginPath(); ctx.moveTo(cx-bw, cy+bh*0.5); ctx.quadraticCurveTo(cx, cy-bh, cx+bw, cy+bh*0.5); ctx.stroke();
            });
        } else if (brow === 'sad') {
            ctx.lineWidth = 3 * s;
            ctx.beginPath(); ctx.moveTo(LEX-bw, BRY+bh); ctx.lineTo(LEX+bw, BRY-bh); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(REX-bw, BRY-bh); ctx.lineTo(REX+bw, BRY+bh); ctx.stroke();
        }
    }

    // ── Eyes ──
    const eye = feats.eye;
    const er  = 12 * s, pr = 5.5 * s;
    if (eye === 'round' || eye === 'big') {
        const r = eye === 'big' ? er * 1.35 : er;
        [[LEX,EYY],[REX,EYY]].forEach(([cx,cy]) => {
            ctx.fillStyle = 'white';
            ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2); ctx.fill();
            ctx.fillStyle = '#18182a';
            ctx.beginPath(); ctx.arc(cx, cy, pr, 0, Math.PI*2); ctx.fill();
            ctx.fillStyle = 'rgba(255,255,255,0.85)';
            ctx.beginPath(); ctx.arc(cx - pr*0.55, cy - pr*0.6, pr*0.52, 0, Math.PI*2); ctx.fill();
        });
    } else if (eye === 'half') {
        [[LEX,EYY],[REX,EYY]].forEach(([cx,cy]) => {
            ctx.fillStyle = 'white';
            ctx.beginPath(); ctx.arc(cx, cy, er, Math.PI, 0, false); ctx.closePath(); ctx.fill();
            ctx.fillStyle = '#18182a';
            ctx.beginPath(); ctx.arc(cx, cy, pr, Math.PI, 0, false); ctx.closePath(); ctx.fill();
        });
    } else if (eye === 'squint') {
        [[LEX,EYY],[REX,EYY]].forEach(([cx,cy]) => {
            ctx.save(); ctx.translate(cx, cy); ctx.scale(1, 0.32);
            ctx.fillStyle = 'white';  ctx.beginPath(); ctx.arc(0, 0, er, 0, Math.PI*2); ctx.fill();
            ctx.fillStyle = '#18182a'; ctx.beginPath(); ctx.arc(0, 0, pr, 0, Math.PI*2); ctx.fill();
            ctx.restore();
        });
    } else if (eye === 'wink') {
        // Left eye: open
        ctx.fillStyle = 'white';  ctx.beginPath(); ctx.arc(LEX, EYY, er, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = '#18182a'; ctx.beginPath(); ctx.arc(LEX, EYY, pr, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        ctx.beginPath(); ctx.arc(LEX - pr*0.55, EYY - pr*0.6, pr*0.52, 0, Math.PI*2); ctx.fill();
        // Right eye: closed arc
        ctx.strokeStyle = '#18182a'; ctx.lineWidth = 3.5 * s; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(REX-er, EYY); ctx.quadraticCurveTo(REX, EYY+er*0.55, REX+er, EYY); ctx.stroke();
    }

    // ── Nose ──
    const nose = feats.nose;
    if (nose === 'button') {
        ctx.fillStyle = 'rgba(0,0,0,0.18)';
        ctx.beginPath(); ctx.ellipse(NCX-9*s, NCY, 4.5*s, 3.5*s, 0, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.ellipse(NCX+9*s, NCY, 4.5*s, 3.5*s, 0, 0, Math.PI*2); ctx.fill();
    } else if (nose === 'dot') {
        ctx.fillStyle = 'rgba(0,0,0,0.22)';
        ctx.beginPath(); ctx.arc(NCX-7*s, NCY, 3*s, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.arc(NCX+7*s, NCY, 3*s, 0, Math.PI*2); ctx.fill();
    } else if (nose === 'cat') {
        ctx.fillStyle = '#d6609a';
        ctx.beginPath(); ctx.moveTo(NCX, NCY-7*s); ctx.lineTo(NCX-11*s, NCY+6*s); ctx.lineTo(NCX+11*s, NCY+6*s); ctx.closePath(); ctx.fill();
        ctx.fillStyle = 'rgba(0,0,0,0.12)';
        ctx.beginPath(); ctx.arc(NCX, NCY+3*s, 3*s, 0, Math.PI*2); ctx.fill();
    }

    // ── Mouth ──
    const mouth = feats.mouth;
    const mw = 30 * s, ma = 10 * s;
    ctx.strokeStyle = '#3d1f0a'; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    if (mouth === 'neutral') {
        ctx.lineWidth = 3 * s;
        ctx.beginPath(); ctx.moveTo(MCX-mw, MCY); ctx.lineTo(MCX+mw, MCY); ctx.stroke();
    } else if (mouth === 'smile') {
        ctx.lineWidth = 3 * s;
        ctx.beginPath(); ctx.moveTo(MCX-mw, MCY-ma*0.35); ctx.quadraticCurveTo(MCX, MCY+ma, MCX+mw, MCY-ma*0.35); ctx.stroke();
    } else if (mouth === 'grin') {
        ctx.fillStyle = '#1a0a02';
        ctx.beginPath(); ctx.moveTo(MCX-mw, MCY); ctx.quadraticCurveTo(MCX, MCY+ma*1.6, MCX+mw, MCY); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#f0f0f0';
        ctx.beginPath(); ctx.moveTo(MCX-mw, MCY); ctx.quadraticCurveTo(MCX, MCY+ma*0.7, MCX+mw, MCY); ctx.closePath(); ctx.fill();
        ctx.lineWidth = 2 * s;
        ctx.beginPath(); ctx.moveTo(MCX-mw, MCY); ctx.quadraticCurveTo(MCX, MCY+ma*1.6, MCX+mw, MCY); ctx.stroke();
    } else if (mouth === 'surprise') {
        ctx.fillStyle = '#1a0a02';
        ctx.beginPath(); ctx.ellipse(MCX, MCY, 11*s, 14*s, 0, 0, Math.PI*2); ctx.fill();
    } else if (mouth === 'frown') {
        ctx.lineWidth = 3 * s;
        ctx.beginPath(); ctx.moveTo(MCX-mw, MCY+ma*0.35); ctx.quadraticCurveTo(MCX, MCY-ma, MCX+mw, MCY+ma*0.35); ctx.stroke();
    } else if (mouth === 'smirk') {
        ctx.lineWidth = 3 * s;
        ctx.beginPath(); ctx.moveTo(MCX-mw, MCY); ctx.quadraticCurveTo(MCX+mw*0.4, MCY+ma*0.9, MCX+mw, MCY-ma*0.5); ctx.stroke();
    }

    ctx.restore();
}

// 依「配方」建立一張臉部貼圖畫布。純函式，不碰任何 DOM 或全域狀態。
//   colors   : { head, arm, body, legs, feet }  只有 head 會用到（膚色）
//   features : { eyebrow, eye, nose, mouth }
function buildFaceCanvas(colors, features) {
    const W = FACE_TEXTURE_SIZE, H = FACE_TEXTURE_SIZE;
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');

    // 膚色打底
    ctx.fillStyle = (colors && colors.head) || '#f5c18a';
    ctx.fillRect(0, 0, W, H);

    drawFaceFeatures(ctx, W, H, features || {});
    return canvas;
}

// 直接取得 data URL，供需要字串形式的呼叫端使用
function buildFaceDataUrl(colors, features) {
    return buildFaceCanvas(colors, features).toDataURL('image/png');
}
