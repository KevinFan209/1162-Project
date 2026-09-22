# -*- coding: utf-8 -*-
"""棋盤格子座標的生成邏輯。

背景：/game/map_config 每局隨機抽 20 個地點塞進棋盤的冒險格。這裡要做的事：
    1. 每局隨機挑一種預設幾何形狀（圓形/方形/六邊形/無限符號），26 格
       （20 冒險格 + 6 特殊格）全部沿著形狀外框均勻分佈（choose_shape,
       circle_positions, regular_polygon_positions, infinity_positions）
    2. 20 個冒險格依真實海拔的「排名」（不是數值本身）分配高度，
       保證每格高度都不同、级距肉眼可辨（rank_based_heights）
    3. 讓沿形狀走一圈時高度平滑爬升到最高點再下降，連接橋才不會忽高
       忽低亂跳（compute_shape_board 內部的走訪順序）
    4. 特殊格沒有海拔資料，y 用前後相鄰格的平均值插值；x/z 直接由形狀
       公式給出，不需要額外插值

⚠️ 這裡不再依真實經緯度換算座標——舊版用等距圓柱投影把經緯度換算成
   x/z，好處是「同一地點不管哪一局抽到，換算出來的棋盤座標都一樣」，
   但實測發現南投市這類地點密集的鄉鎮常常一次抽到好幾筆，格子會擠在
   一起看不出路線，即使加上鬆弛演算法（declutter）處理也只能緩解不能
   根治。改用形狀生成後，26 個點天生均勻分布在外框上、不會重疊，位置
   不再對應真實地理，純粹是「每格分到哪一階海拔排名」決定走到哪個
   位置——這是已經確認過的設計取捨，不是退化。

這幾個函式都是純數學運算（不碰資料庫、不碰 FastAPI），獨立出來才能在
沒有伺服器的情況下直接用真實資料跑驗證。
"""
import math
import random

# 形狀的視覺尺度。
#
# ⚠️ 這個數字必須跟 static/js/board-build.js 的 BOARD_MAX_EXTENT／
#    GROUND_SIZE 算法裡引用的半徑保持一致（那邊的註解也有提醒）——
#    Python 跟 JS 是兩個獨立的執行環境沒辦法共用同一個常數，只能各自
#    定義、手動保持同步。以後要調棋盤大小，這裡跟 board-build.js 要
#    一起改。
BOARD_SHAPE_RADIUS = 24.0

# 高度範圍：比舊版 elevation_to_y 的 0~4 更寬，19 個名次間隔下每階約
# 0.3 個單位，肉眼看得出高度差（見 rank_based_heights）。
DEFAULT_Y_RANGE = (0.0, 6.0)

# 跟 main.py／board-layout.js 的特殊格索引一致：
#     0 = START 起點      3, 16 = SHOP 道具店
#     6 = PUNISH 開合跳    13    = JAIL 監獄
#     19 = REWARD 獎勵     其餘 20 格 = ADVENTURE 冒險格
SPECIAL_IDX = (0, 3, 6, 13, 16, 19)


def circle_positions(n, radius=BOARD_SHAPE_RADIUS):
    """n 個點均勻分佈在一個圓上。"""
    pts = []
    for i in range(n):
        angle = (2 * math.pi * i) / n
        pts.append((radius * math.cos(angle), radius * math.sin(angle)))
    return pts


def regular_polygon_positions(n, sides, radius=BOARD_SHAPE_RADIUS):
    """正多邊形（方形＝4邊、六邊形＝6邊，邊數可調）。

    n 個點依「周長」等距分佈，不是每邊固定配額——n 不一定能被邊數
    整除，用周長等距才能讓每個間隔實際距離一致，不會有些邊擠有些邊鬆。
    """
    verts = []
    # 頂點角度的起始偏移：-90 度 + 半個邊的角寬（π/sides），讓多邊形
    # 是「平邊朝前」（像相框那樣，邊對齊軸線），不是「頂角朝前」的
    # 菱形方向——單純頂角朝上下左右的話，sides=4 時看起來會是菱形，
    # 一般人不會直覺辨認成「正方形」。這個偏移對任意邊數都適用。
    start_angle = -math.pi / 2 + math.pi / sides
    for k in range(sides):
        angle = (2 * math.pi * k) / sides + start_angle
        verts.append((radius * math.cos(angle), radius * math.sin(angle)))

    edge_lens = []
    total = 0.0
    for k in range(sides):
        ax, az = verts[k]
        bx, bz = verts[(k + 1) % sides]
        length = math.hypot(bx - ax, bz - az)
        edge_lens.append(length)
        total += length

    pts = []
    for i in range(n):
        target = (total * i) / n
        edge_idx = 0
        while edge_idx < sides - 1 and target > edge_lens[edge_idx]:
            target -= edge_lens[edge_idx]
            edge_idx += 1
        ax, az = verts[edge_idx]
        bx, bz = verts[(edge_idx + 1) % sides]
        t = target / edge_lens[edge_idx] if edge_lens[edge_idx] > 0 else 0.0
        pts.append((ax + (bx - ax) * t, az + (bz - az) * t))
    return pts


def infinity_positions(n, a=BOARD_SHAPE_RADIUS * 1.4, samples=2000):
    """無限符號（∞）：Gerono 雙紐線 x = a·cos(t)，z = (a/2)·sin(2t)，
    t ∈ [0, 2π)。這條曲線會通過原點兩次，畫出左右對稱的兩個環，正是
    「∞」的形狀（跟橢圓／多邊形不同，中間會交叉）。

    曲線本身不是等速參數化——t 均勻增加時，經過中間交叉點附近的弧長
    反而比環的最外側密。所以做法跟正多邊形一樣：先用很密的取樣點
    描出整條曲線的折線近似，量出每一小段的弧長，再依「總弧長」等距
    切出 n 個點。
    """
    curve = []
    for s in range(samples):
        t = (2 * math.pi * s) / samples
        curve.append((a * math.cos(t), (a / 2) * math.sin(2 * t)))

    seg_lens = []
    total = 0.0
    for s in range(samples):
        px, pz = curve[s]
        qx, qz = curve[(s + 1) % samples]
        length = math.hypot(qx - px, qz - pz)
        seg_lens.append(length)
        total += length

    pts = []
    for i in range(n):
        target = (total * i) / n
        idx = 0
        while idx < samples - 1 and target > seg_lens[idx]:
            target -= seg_lens[idx]
            idx += 1
        px, pz = curve[idx]
        qx, qz = curve[(idx + 1) % samples]
        t = target / seg_lens[idx] if seg_lens[idx] > 0 else 0.0
        pts.append((px + (qx - px) * t, pz + (qz - pz) * t))
    return pts


SHAPES = {
    "circle": lambda n: circle_positions(n),
    "square": lambda n: regular_polygon_positions(n, 4),
    "hexagon": lambda n: regular_polygon_positions(n, 6),
    "infinity": lambda n: infinity_positions(n),
}


def choose_shape():
    """每局隨機挑一種形狀，四種等機率。"""
    return random.choice(list(SHAPES.keys()))


def rank_based_heights(elevations, y_range=DEFAULT_Y_RANGE):
    """依海拔「排名」（不是數值本身）分配高度，保證兩兩不同。

    真實海拔資料很不均勻（多數擠在 100~800m，只有少數突出到 1000m
    以上），如果照數值直接線性對應高度，大部分格子會擠在同一個低矮
    區間、看不出差異；依排名分配則保證每一格的高度都不同、级距均等。

    elevations: 長度 n 的 list，元素是海拔數值或 None（沒有資料時
                視為 0，用原始索引當排序鍵仍能拆出穩定的排名）。
    回傳: 對齊 elevations 原始順序的 [(rank, y), ...]，rank 是 0~n-1
          的排名（0 = 海拔最低），y 是等距映射到 y_range 的高度。
    """
    n = len(elevations)
    y_min, y_max = y_range
    filled = [e if e is not None else 0 for e in elevations]

    # 用 (海拔, 原始索引) 排序，就算兩筆海拔剛好相同，也能靠索引拆出
    # 穩定、不會並列的排名。
    order = sorted(range(n), key=lambda i: (filled[i], i))
    rank_of = {orig_idx: rank for rank, orig_idx in enumerate(order)}

    result = []
    for i in range(n):
        rank = rank_of[i]
        t = rank / (n - 1) if n > 1 else 0.5
        result.append((rank, y_min + t * (y_max - y_min)))
    return result


def compute_shape_board(elevations, special_idx=SPECIAL_IDX, shape_key=None,
                        y_range=DEFAULT_Y_RANGE):
    """主要進入點：把 20 個冒險格的海拔換算成走訪順序，加上完整 26 格
    的座標。

    elevations: 長度 20 的 list，跟呼叫端 adventure_tiles 的原始順序
                對齊（元素可為 None，見 rank_based_heights）
    special_idx: 26 格裡哪些索引是特殊格（沒有海拔資料）
    shape_key:  不傳的話用 choose_shape() 隨機挑一種

    走訪順序：名次 0（海拔最低）排進第一個非特殊 slot，名次最高排進
    最後一個非特殊 slot——這樣沿形狀走一圈，高度會平滑爬升到最高點
    再下降，連接橋不會忽高忽低亂跳（跟 game_board_shapes.html 的
    buildShapeGameMap() 是同一套規則）。

    特殊格沒有海拔資料，y 用前後相鄰格（此時鄰居必定是冒險格或已算好
    高度的特殊格）的平均值插值；x/z 直接是形狀公式給的座標，不插值
    （這跟舊版經緯度那套不一樣——形狀本身在每個 slot 都有明確座標，
    不需要事後補位）。

    回傳 (shape_key, order, positions_26)：
        shape_key    實際採用的形狀名稱
        order        20 個冒險格「依排名重排後」要塞進 slot 的原始
                     索引順序，長度 20，是 range(20) 的排列
        positions_26 長度 26 的 [(x, y, z), ...]，已經是 slot 順序
                     （不是走訪順序）
    """
    n = len(elevations)
    shape_key = shape_key or choose_shape()
    positions = SHAPES[shape_key](26)

    special_set = set(special_idx)
    adv_slots = [i for i in range(26) if i not in special_set]

    ranked = rank_based_heights(elevations, y_range)

    # 依名次（不是原順序）排序冒險格，決定要放進哪個 slot
    order = sorted(range(n), key=lambda i: ranked[i][0])

    positions_26 = [None] * 26
    for k, adv_idx in enumerate(order):
        slot = adv_slots[k]
        x, z = positions[slot]
        _, y = ranked[adv_idx]
        positions_26[slot] = (x, y, z)

    for slot in special_idx:
        x, z = positions[slot]
        positions_26[slot] = (x, None, z)

    # 插值特殊格的 y：往前/往後找最近的非 None（特殊格彼此不相鄰，
    # 理論上第一次找就會命中，但寫成通用寫法比較穩固）
    for slot in special_idx:
        j = slot
        while positions_26[j % 26][1] is None:
            j -= 1
        prev_y = positions_26[j % 26][1]
        k = slot
        while positions_26[k % 26][1] is None:
            k += 1
        next_y = positions_26[k % 26][1]

        x, _, z = positions_26[slot]
        positions_26[slot] = (x, (prev_y + next_y) / 2.0, z)

    return shape_key, order, positions_26
