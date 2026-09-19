# -*- coding: utf-8 -*-
"""棋盤格子座標的地理換算。

為什麼獨立成一個檔案：這幾個函式是純數學運算（不碰資料庫、不碰 FastAPI），
獨立出來才能在沒有伺服器的情況下直接用真實資料跑驗證——這個專案一路以來
都是這樣驗證資料正確性的，改動棋盤生成邏輯這種「肉眼很難每次都開瀏覽器
確認」的東西尤其需要。

背景：/game/map_config 每局隨機抽 20 個地點塞進棋盤的冒險格，這些地點在
scenarios 表裡有真實的 latitude/longitude/elevation_m。這裡要做的事：
    1. 把經緯度換算成棋盤的 x/z 座標（project_geo_to_xz）
    2. 把海拔換算成棋盤的 y 高度（elevation_to_y）
    3. 決定 20 個點的走訪順序，讓連接橋大致照著地理位置走，
       而不是隨機跳來跳去（order_by_angle）
    4. 沒有真實座標的 6 個特殊格（起點/道具店/監獄/開合跳/獎勵），
       用前後相鄰格的中點插值出一個座標（fill_special_positions）

⚠️ 全部換算都要用「全域範圍」（scenarios 全部 107 筆的 min/max），
   不是「這一局抽到的 20 筆」的範圍——這樣同一個地點不管哪一局抽到，
   換算出來的棋盤座標都一樣，玩家才能建立起「這一帶大概在棋盤哪個
   位置」的印象；用當局範圍的話，20 個點就算全擠在同一鄉鎮，也會被
   硬拉開填滿整個棋盤，失去真實感。呼叫端（main.py）負責把全域範圍
   查出來傳進來，這裡的函式本身不知道也不需要知道「全域」是什麼。
"""
import math

# 棋盤的實體範圍。
#
# ⚠️ 這個數字比 board-layout.js 舊棋盤的物理範圍（x:±24 / z:±15）大，
#    是刻意的，不是筆誤。舊棋盤 26 格是「沿著矩形周長排列」，26 格
#    平均分佈在周長上本來就不會擠。新做法是把 20 個點依真實相對位置
#    「散佈在一塊 2D 範圍裡」，用真實資料實測過：範圍跟舊棋盤一樣大
#    的話，因為南投市這類地點集中的鄉鎮一次抽到好幾筆很常見，
#    25% 的格子對距離小於格子邊長（5），棋盤會嚴重擁擠、看不出路線。
#    放大到 2 倍後這個比例降到 8% 左右，配合下面的 declutter() 再處理
#    剩下的極端重疊，兩者一起用才夠。單獨放大範圍沒辦法解決「同鄉鎮
#    退回同一個鄉鎮中心點」造成的完全重合（那是精確的 0 距離，
#    不管範圍多大都還是 0），只有 declutter 治得了。
DEFAULT_TARGET_BOUNDS = (-40.0, 40.0, -24.0, 24.0)  # (x_min, x_max, z_min, z_max)
DEFAULT_Y_RANGE = (0.0, 4.0)  # 沿用現有 BOARD_HEIGHTS 的範圍

# 🏆 這裡刻意是舊棋盤 BOARD_SPACING(6) 的兩倍，不是筆誤。
#
# declutter 只作用在 20 個冒險格（compute_adventure_positions 內部），
# 特殊格（起點/道具店/監獄/開合跳/獎勵）是事後補上去的，位置是相鄰兩個
# 冒險格的「中點」——也就是說，特殊格離每個鄰居的距離，結構上必然是
# 那兩個冒險格彼此間距的一半。如果冒險格之間只保證 6 的間距，插在中間
# 的特殊格離鄰居就只有 3，比舊棋盤固定 6 的間距還擠（實測過：曾經
# min_separation=6 時，最擠的特殊格只有 3 的間距）。拉高到 12，
# 冒險格彼此至少 12、特殊格離鄰居至少 6，兩種格子才會有一致的最小間距。
#
# ⚠️ 曾經試過改成「26 格全部到齊後再 declutter 一次」讓特殊格也被推開，
# 結果連接線大量交叉（無交叉率從 100% 掉到 2%）——declutter 不懂棋盤的
# 路徑拓撲，會把本該貼著鄰居中點的特殊格推走，破壞環狀順序。所以改用
# 這個「提高冒險格間距的門檻，讓特殊格自然而然也夠開」的做法。
DEFAULT_MIN_SEPARATION = 12.0

KM_PER_DEG_LAT = 111.32


def project_geo_to_xz(lat, lon, geo_bounds, target_bounds=DEFAULT_TARGET_BOUNDS):
    """等距圓柱投影 + 等比縮放，把經緯度換算成棋盤 x/z。

    南投縣範圍只有東西南北約 65 公里，這種小範圍用等距圓柱投影
    （簡單地把經緯度差乘上「該緯度下 1 度是幾公里」）產生的失真
    可以忽略，不需要用到真正的地圖投影算法。

    等比縮放（兩軸用同一個縮放係數）是為了不讓南北/東西的相對距離
    失真——如果兩軸各自獨立縮放到填滿棋盤範圍，兩個實際相距 10 公里
    的地點，南北方向跟東西方向在棋盤上看起來的距離會不一樣，觀感上
    像是被拉伸過。

    lat 增加 -> z 減少（北在畫面「上方」，對應 z 變小，是一般地圖的
    直覺方向）；lon 增加 -> x 增加（東在右邊）。這只是方向選擇，
    不影響任何遊戲邏輯，之後覺得方向怪的話這裡兩行互換即可。
    """
    lat_min, lat_max, lon_min, lon_max = geo_bounds
    x_min, x_max, z_min, z_max = target_bounds

    lat_mid = (lat_min + lat_max) / 2.0
    km_per_deg_lon = KM_PER_DEG_LAT * math.cos(math.radians(lat_mid))

    real_width_km = (lon_max - lon_min) * km_per_deg_lon
    real_height_km = (lat_max - lat_min) * KM_PER_DEG_LAT

    target_width = x_max - x_min
    target_height = z_max - z_min

    # 兩軸都不能是 0（例如全域範圍只有一筆資料時 lat_min==lat_max），
    # 這種退化情況直接把點放在目標範圍正中央。
    if real_width_km <= 0 or real_height_km <= 0:
        return (x_min + target_width / 2.0, z_min + target_height / 2.0)

    scale = min(target_width / real_width_km, target_height / real_height_km)

    used_width = real_width_km * scale
    used_height = real_height_km * scale

    dx_km = (lon - lon_min) * km_per_deg_lon
    dy_km = (lat - lat_min) * KM_PER_DEG_LAT

    x = x_min + (target_width - used_width) / 2.0 + dx_km * scale
    # lat 增加 -> z 減少：用 (real_height_km - dy_km) 反過來映射
    z = z_min + (target_height - used_height) / 2.0 + (real_height_km - dy_km) * scale

    return (x, z)


def elevation_to_y(elev_m, elev_bounds, y_range=DEFAULT_Y_RANGE):
    """線性縮放海拔到棋盤高度。elev_bounds 同樣要用全域 min/max。"""
    elev_min, elev_max = elev_bounds
    y_min, y_max = y_range
    if elev_max <= elev_min:
        return (y_min + y_max) / 2.0
    t = (elev_m - elev_min) / (elev_max - elev_min)
    t = max(0.0, min(1.0, t))  # 防呆：理論上不會超出全域範圍，但保險起見夾住
    return y_min + t * (y_max - y_min)


def declutter(points, min_dist=DEFAULT_MIN_SEPARATION, target_bounds=DEFAULT_TARGET_BOUNDS,
              iterations=60, skip_pairs=None):
    """把彼此距離小於 min_dist 的點互相推開，解決棋盤格重疊/太擠的問題。

    為什麼需要這個函式：光靠放大 target_bounds 沒辦法解決兩種情況——
      1. 「鄉鎮退回」的地點（見 fill_special_positions 的姊妹邏輯，實際
         在 compute_adventure_positions 呼叫端處理）同一鄉鎮的好幾筆會
         退回同一個鄉鎮中心座標，距離精確是 0，不管棋盤多大都還是 0。
      2. 真實地點本身就密集的地方（例如南投市 13 個景點擠在市區），
         等比投影會忠實反映這種密集，範圍放大只能緩解不能根治。

    做法是標準的「鬆弛法」（relaxation）：每一輪找出距離小於 min_dist
    的每一對點，把兩點沿著彼此的連線各推開一半差距；重複到沒有違規
    或跑滿 iterations 輪為止。兩點完全重合（距離為 0，無連線方向可推）
    時，用點在陣列中的索引算出一個固定角度來決定推開方向——這樣同樣
    的輸入永遠推出同樣的結果，不會每次呼叫都不一樣。

    跑完之後會把座標夾回 target_bounds 範圍內（鬆弛過程可能把邊界
    附近的點推出範圍），代價是邊界附近極少數點的間距可能無法完全
    達到 min_dist，這是可接受的邊界情況，不是主要修正目標。

    skip_pairs: 可選，{(i, j), ...} 這些索引對（i<j）不參與推擠判斷。
    對完整 26 格棋盤做 declutter 時要用到——路徑上真正相鄰的兩格
    （被連接橋接著）本來就該貼近，不能因為「太近」被推開，否則會破壞
    order_by_angle 排好的環狀順序、讓連接線互相交叉（實測過這個後果）。
    只在真正不該靠近、卻剛好離得很近的非相鄰格子對之間做這件事。

    points: [(x, z), ...]
    回傳: 新的 [(x, z), ...]，長度與順序都與輸入一致
    """
    n = len(points)
    pts = [[p[0], p[1]] for p in points]
    skip = skip_pairs or set()

    for _ in range(iterations):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                if (i, j) in skip:
                    continue
                dx = pts[j][0] - pts[i][0]
                dz = pts[j][1] - pts[i][1]
                dist = math.hypot(dx, dz)
                if dist >= min_dist:
                    continue
                moved = True
                if dist < 1e-9:
                    angle = (2 * math.pi * j) / n
                    dx, dz = math.cos(angle), math.sin(angle)
                    dist = 1.0
                nx, nz = dx / dist, dz / dist
                push = (min_dist - dist) / 2.0
                pts[i][0] -= nx * push
                pts[i][1] -= nz * push
                pts[j][0] += nx * push
                pts[j][1] += nz * push
        if not moved:
            break

    x_min, x_max, z_min, z_max = target_bounds
    for p in pts:
        p[0] = max(x_min, min(x_max, p[0]))
        p[1] = max(z_min, min(z_max, p[1]))

    return [(p[0], p[1]) for p in pts]


def order_by_angle(points):
    """依「以這些點自己的重心為圓心」的極角排序，回傳原始索引的排列。

    這是一個視覺啟發式，不是嚴謹的最短路徑演算法：目的是讓走訪順序
    大致沿著點的分布繞一圈，而不是隨機亂跳，連接橋才不會在棋盤上
    到處交叉。不保證連接線完全不交叉（點的分布如果不是「星狀」，
    極角排序仍可能產生交叉），但對散佈在一個小縣境內的真實地點
    而言，這種情況很罕見——這件事在驗證階段會用真實資料實際模擬
    確認機率，不是憑印象斷定。

    points: [(x, z), ...]
    回傳: 排序後的原始索引列表，長度與輸入相同
    """
    n = len(points)
    if n <= 2:
        return list(range(n))

    cx = sum(p[0] for p in points) / n
    cz = sum(p[1] for p in points) / n

    indexed = [(math.atan2(p[1] - cz, p[0] - cx), i) for i, p in enumerate(points)]
    indexed.sort(key=lambda t: t[0])
    return [i for _, i in indexed]


def compute_adventure_positions(rows, geo_bounds, elev_bounds,
                                target_bounds=DEFAULT_TARGET_BOUNDS,
                                y_range=DEFAULT_Y_RANGE,
                                min_separation=DEFAULT_MIN_SEPARATION):
    """把 20 筆 (lat, lon, elevation_m) 換算成走訪順序與對應座標。

    rows: [(lat, lon, elev_m), ...]，任一值可為 None（防呆：資料庫忘了
          填經緯度時，退回全域範圍正中央 / 海拔中位數，不會噴錯）。

    回傳 (order, positions)：
        order      走訪順序，是 range(len(rows)) 的一個排列
        positions  依 order 排好的 [(x, y, z), ...]，
                   positions[k] 對應 rows[order[k]]
    """
    lat_min, lat_max, lon_min, lon_max = geo_bounds
    elev_min, elev_max = elev_bounds
    lat_mid_default = (lat_min + lat_max) / 2.0
    lon_mid_default = (lon_min + lon_max) / 2.0
    elev_mid_default = (elev_min + elev_max) / 2.0

    filled = [
        (lat if lat is not None else lat_mid_default,
         lon if lon is not None else lon_mid_default,
         elev if elev is not None else elev_mid_default)
        for lat, lon, elev in rows
    ]

    xz = [project_geo_to_xz(lat, lon, geo_bounds, target_bounds)
          for lat, lon, _ in filled]
    ys = [elevation_to_y(elev, elev_bounds, y_range) for _, _, elev in filled]

    # 🏆 推開太近/重合的冒險格（同鄉鎮退回同一中心點、或真實地點本身
    #    就密集）。min_separation 的預設值刻意是舊棋盤間距的兩倍——
    #    特殊格事後會插在相鄰兩個冒險格的「中點」，離每個鄰居的距離
    #    結構上必然是這裡間距的一半，門檻要夠高，插值出來的特殊格
    #    才不會比冒險格彼此還擠（見 DEFAULT_MIN_SEPARATION 的說明）。
    #
    #    ⚠️ declutter 只在這裡（20 個冒險格）做，不要等 26 格全部到齊
    #    後再對整個棋盤做一次——declutter 不懂路徑拓撲，會把本該貼著
    #    鄰居中點的特殊格推走，實測會讓連接線大量交叉。
    xz = declutter(xz, min_separation, target_bounds)

    order = order_by_angle(xz)
    positions = [(xz[i][0], ys[i], xz[i][1]) for i in order]
    return order, positions


def fill_special_positions(positions_26):
    """幫沒有真實座標的格子（值為 None）用前後相鄰格的中點補上座標。

    positions_26: 長度 26 的 list，每個元素是 (x,y,z) 或 None。
                  會直接修改並回傳同一個 list。

    用「往前/往後找最近的非 None 格」而不是直接假設 i-1/i+1 一定有值，
    是為了在特殊格分布規則以後若被改動時仍然穩固——目前的 6 個特殊格
    （索引 0,3,6,13,16,19）彼此都不相鄰，所以實際上第一次往前/往後找
    就會命中，但函式本身不依賴這個前提。
    """
    n = len(positions_26)
    none_indices = [i for i, p in enumerate(positions_26) if p is None]
    if not none_indices:
        return positions_26
    if len(none_indices) == n:
        raise ValueError("全部 26 格都沒有座標，無法插值")

    for i in none_indices:
        # 往前找最近的非 None
        j = i
        while positions_26[j % n] is None:
            j -= 1
        prev_pos = positions_26[j % n]
        # 往後找最近的非 None
        k = i
        while positions_26[k % n] is None:
            k += 1
        next_pos = positions_26[k % n]

        positions_26[i] = (
            (prev_pos[0] + next_pos[0]) / 2.0,
            (prev_pos[1] + next_pos[1]) / 2.0,
            (prev_pos[2] + next_pos[2]) / 2.0,
        )

    return positions_26
