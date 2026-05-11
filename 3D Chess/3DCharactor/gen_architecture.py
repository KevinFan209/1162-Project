import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib as mpl

mpl.rcParams['font.family'] = ['Microsoft JhengHei', 'DejaVu Sans']

# 座標系統：1 data unit ≈ 1 figure inch（tight layout 後）
# 字型大小公式：fontsize ≈ box_width_units * 72pt * fill_ratio / (n_chars * 0.65)
W, H = 32, 22
fig, ax = plt.subplots(figsize=(W, H))
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis('off')

mpl.rcParams['font.family'] = ['Microsoft JhengHei', 'DejaVu Sans']

# ── Helpers ───────────────────────────────────────────────────────────────────
def box(x, y, w, h, color, label, sublabel=None, fs=28, sub_fs=None, radius=0.35):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0.06,rounding_size={radius}",
                 linewidth=2.2, edgecolor='#333', facecolor=color, zorder=3))
    cy = y + h / 2 + (0.3 if sublabel else 0)
    ax.text(x + w/2, cy, label, ha='center', va='center',
            fontsize=fs, fontweight='bold', color='#1a1a2e', zorder=4)
    if sublabel:
        sfz = sub_fs if sub_fs else max(fs - 10, 12)
        ax.text(x + w/2, cy - 0.7, sublabel, ha='center', va='center',
                fontsize=sfz, color='#333', zorder=4)

def layer_bg(y, h, color, label, lfs=26):
    ax.add_patch(FancyBboxPatch((0.4, y), W - 0.8, h,
                 boxstyle="round,pad=0.06,rounding_size=0.5",
                 linewidth=1.5, edgecolor='#bbb', facecolor=color,
                 alpha=0.4, zorder=1))
    ax.text(0.9, y + h/2, label, ha='center', va='center',
            fontsize=lfs, color='#444', rotation=90, fontweight='bold')

def subbox(x, y, w, h, ec, fc, label, fs=22):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle="round,pad=0.04,rounding_size=0.15",
                 linewidth=1.5, edgecolor=ec, facecolor=fc, zorder=4))
    ax.text(x + w/2, y + h/2, label, ha='center', va='center',
            fontsize=fs, fontweight='bold', color='#1a1a2e', zorder=5)

def arrow(x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color='#555', lw=2.5), zorder=5)

def dblarrow(x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='<->', color='#555', lw=2.5), zorder=5)

# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(16, 21.5, 'PyPoly 系統架構圖',
        ha='center', va='center', fontsize=58, fontweight='bold', color='#1a1a2e')
ax.text(16, 20.85, '三層式架構（Three-Tier Architecture）',
        ha='center', va='center', fontsize=32, color='#444')

# ══════════════════════════════════════════════════════════════════════════════
# Layer 1 – 表示層   y 17.4 – 20.5
# ══════════════════════════════════════════════════════════════════════════════
# 6 boxes × w=4.35，總寬=26.1，起點 1.6，間距 0.45
layer_bg(17.4, 3.1, '#dce8ff', '表示層', 28)

BOX_W  = 4.35   # 框寬
BOX_H  = 2.3    # 框高
BOX_Y  = 17.7
BOX_SP = 0.45   # 間距

# "登入 / 大廳" 7字在 4.35單位 → fs ≈ 4.35*72*0.65/(7*0.65) ≈ 45pt
P_LABELS = ['登入 / 大廳', '遊戲棋盤', '題目作答', '遊戲結算', '後台管理', '相機辨識']
P_COLORS = ['#4a90d9', '#4a90d9', '#4a90d9', '#4a90d9', '#4a90d9', '#6ab0de']
for i, (lbl, col) in enumerate(zip(P_LABELS, P_COLORS)):
    bx = 1.6 + i * (BOX_W + BOX_SP)
    # 按最長字串動態決定字型
    fs = int(BOX_W * 72 * 0.62 / (len(lbl) * 0.65))
    fs = min(fs, 52)   # 上限，避免過大
    box(bx, BOX_Y, BOX_W, BOX_H, col, lbl, fs=fs)

# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 – 業務邏輯層   y 9.4 – 17.1
# ══════════════════════════════════════════════════════════════════════════════
layer_bg(9.4, 7.7, '#fff3cd', '業務邏輯層', 28)

ax.text(16, 16.68, '通訊層  WebSocket / Socket.IO',
        ha='center', va='center', fontsize=30, color='#7a5c00', fontweight='bold')

# Game Logic  w=8.6 h=5.5  → "遊戲邏輯模組" 6字 → fs=55
GL_X, GL_Y, GL_W, GL_H = 1.5, 10.3, 8.6, 5.5
box(GL_X, GL_Y, GL_W, GL_H, '#f5c842', '遊戲邏輯模組',
    'Game Logic  (FastAPI / Node.js)', fs=46, sub_fs=26, radius=0.3)
SB_W, SB_H = 1.85, 1.5
for i, txt in enumerate(['回合管理', '移動判斷', '金錢計算', '題目評分']):
    sx = GL_X + 0.22 + i * (SB_W + 0.25)
    subbox(sx, GL_Y + 0.28, SB_W, SB_H, '#c89c00', '#ffe680', txt, fs=30)

# Image Rec  w=8.2 h=5.5  → "影像辨識模組" 6字 → fs=52
IR_X, IR_Y, IR_W, IR_H = 11.2, 10.3, 8.2, 5.5
box(IR_X, IR_Y, IR_W, IR_H, '#ffa94d', '影像辨識模組',
    'Image Recognition  (Python + OpenCV)', fs=46, sub_fs=24, radius=0.3)
SB_W2, SB_H2 = 2.3, 1.5
for i, txt in enumerate(['手勢偵測', '骰子偵測', 'ArUco辨識']):
    sx = IR_X + 0.2 + i * (SB_W2 + 0.25)
    subbox(sx, IR_Y + 0.28, SB_W2, SB_H2, '#c06000', '#ffd0a0', txt, fs=30)

# Auth  w=4.9 h=5.5  → "使用者管理" 5字 → fs=49
box(20.5, 10.3, 4.9, 5.5, '#b2f0b2', '使用者管理',
    'JWT / bcrypt', fs=44, sub_fs=28, radius=0.3)

# Admin  w=4.9 h=5.5  → "後台模組" 4字 → fs=61 (cap at 52)
box(26.5, 10.3, 4.9, 5.5, '#d0b0f0', '後台模組',
    'Admin CMS', fs=50, sub_fs=28, radius=0.3)

ax.text(16, 9.82,
        'RESTful API：/api/auth  ·  /api/game  ·  /api/answers/submit  ·  /api/leaderboard',
        ha='center', va='center', fontsize=18, color='#7a5c00')

# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 – 資料層   y 5.9 – 9.1
# ══════════════════════════════════════════════════════════════════════════════
layer_bg(5.9, 3.2, '#e8f5e9', '資料層', 28)

# 3 MySQL 表各 w=5.0，Redis/S3 各 w=4.3
DB_H = 2.4
DB_Y = 6.15
for bx, dw, col, lbl in [
    (1.5,  5.0, '#66bb6a', 'users 表'),
    (7.0,  5.0, '#66bb6a', 'game_records 表'),
    (12.5, 5.0, '#66bb6a', 'questions 表'),
    (18.0, 4.3, '#ef9a9a', 'Redis Cache'),
    (22.8, 4.3, '#80cbc4', '檔案儲存 S3'),
]:
    fs = int(dw * 72 * 0.60 / (len(lbl) * 0.65))
    fs = max(min(fs, 46), 28)
    box(bx, DB_Y, dw, DB_H, col, lbl, fs=fs)

# ══════════════════════════════════════════════════════════════════════════════
# 部署環境   y 0.6 – 5.6
# ══════════════════════════════════════════════════════════════════════════════
layer_bg(0.6, 5.3, '#f3e5f5', '部署環境', 28)

ax.text(16, 5.65, '生產部署 Production',
        ha='center', va='center', fontsize=34, color='#6a1b9a', fontweight='bold')

DEPLOY = [
    ('CloudFlare', 'CDN / DDoS'),
    ('Nginx',      '反向代理'),
    ('Node.js\nPM2', '程序管理'),
    ('FastAPI\nUvicorn', 'ASGI'),
    ('MySQL',      '關聯式DB'),
    ('Redis',      '快取'),
    ('S3 / MinIO', '物件儲存'),
]
D_W, D_H = 3.9, 4.0
for i, (lbl, sub) in enumerate(DEPLOY):
    bx = 1.3 + i * (D_W + 0.37)
    # 計算主標字型（取最短維度對齊）
    n = max(len(l) for l in lbl.split('\n'))
    fs = int(D_W * 72 * 0.62 / (n * 0.65))
    fs = max(min(fs, 46), 28)
    box(bx, 1.0, D_W, D_H, '#ce93d8', lbl, sub, fs=fs, sub_fs=24, radius=0.3)

# ══════════════════════════════════════════════════════════════════════════════
# Arrows
# ══════════════════════════════════════════════════════════════════════════════
# 表示層 ↔ 業務邏輯層
for cx in [3.8, 8.6, 13.4, 18.2, 23.0]:
    dblarrow(cx, BOX_Y, cx, 17.1)
arrow(29.5, BOX_Y, 15.3, 17.1)   # 相機辨識 → 影像辨識

# 業務邏輯層 → 資料層
for cx in [5.8, 15.3, 22.95, 28.95]:
    arrow(cx, 10.3, cx, 9.1)

# 資料層 → 部署
arrow(16, 6.15, 16, 5.6)

# 模組間水平箭頭
arrow(10.1, 13.05, 11.2, 13.05)
arrow(19.7, 13.05, 20.5, 13.05)
arrow(25.4, 13.05, 26.5, 13.05)

# ══════════════════════════════════════════════════════════════════════════════
# Legend
# ══════════════════════════════════════════════════════════════════════════════
LEGEND = [
    ('#4a90d9', '前端 UI'),
    ('#f5c842', '遊戲邏輯'),
    ('#ffa94d', '影像辨識'),
    ('#b2f0b2', '身份驗證'),
    ('#d0b0f0', '後台管理'),
    ('#66bb6a', '資料庫'),
    ('#ce93d8', '部署元件'),
]
for i, (c, l) in enumerate(LEGEND):
    rx = 1.3 + i * 4.27
    ax.add_patch(FancyBboxPatch((rx, 0.12), 0.65, 0.42,
                 boxstyle="round,pad=0.03", linewidth=1.2,
                 edgecolor='#888', facecolor=c, zorder=6))
    ax.text(rx + 0.82, 0.33, l, va='center', fontsize=22, color='#333')

plt.tight_layout(pad=0)
plt.savefig('system_architecture.png', dpi=180, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print('Saved: system_architecture.png')
