# init_adventure_data.py
import models
from database import SessionLocal, engine

# 🏆 確保資料表已根據新的 models.py 定義建立
models.Base.metadata.create_all(bind=engine)

def seed_data():
    db = SessionLocal()
    try:
        # 1. 清空舊有資料 (避免重複執行時資料堆疊)
        print("🧹 正在清理舊有的冒險格資料...")
        db.query(models.CountryScenario).delete()
        
        # 2. 定義冒險格資料 (結合南投特色、情境敘事、與 Open Data 關聯)
        grids = [
            models.CountryScenario(
                name="中興新村 - 世界茶業博覽會",
                township="南投市",
                scenario="秋風微涼，你走進綠意盎然的中興新村，空氣中隱約飄來陣陣清幽的茶香。每年秋季，這裡匯聚了全南投的茶職人，是國際級的茶文化盛事。茶農正向你介紹今年得獎的烏龍茶，並邀請你一同體驗焙茶的樂趣。",
                skybox_url="nantou_tea_expo.jpg",
                base_price=1200,
                base_toll=240,
                api_station_name="南投"
            ),
            models.CountryScenario(
                name="埔里酒廠",
                township="埔里鎮",
                scenario="你漫步在埔里街道，感受小鎮水源充足帶來的涼意。歷史悠久的酒廠飄出濃郁酒糟香氣，老長輩說，這裡的甘露水才是釀造頂級紹興酒的秘密。看著夕陽映在水圳上，你彷彿能看見這座小鎮百年來的酒香歲月。",
                skybox_url="puli_winery.jpg",
                base_price=1000,
                base_toll=200,
                api_station_name="埔里"
            ),
            models.CountryScenario(
                name="魚池 - 日月潭",
                township="魚池鄉",
                scenario="清晨的薄霧籠罩著潭面，邵族長老的歌聲在湖面迴盪。這裡是全台人氣最高的景點，藍綠色的湖水映照著四周的山巒。微風吹過，你感受到大自然的洗禮，這塊土地蘊含著豐富的文化與生命力。",
                skybox_url="sun_moon_lake.jpg",
                base_price=2500,
                base_toll=500,
                api_station_name="日月潭"
            ),
            models.CountryScenario(
                name="中寮土窯",
                township="中寮鄉",
                scenario="走進中寮的山區，你注意到不少農舍上方正冒著淡淡青煙。那是老農正用龍眼木慢火烘焙龍眼乾，這股柴火氣息與果甜的交織，是中寮傳承百年的記憶。老農遞給你一顆果肉飽滿的龍眼乾，笑著說：『這是時間換來的味道。』",
                skybox_url="zhongliao_longan.jpg",
                base_price=800,
                base_toll=160,
                api_station_name="南投"
            ),
            models.CountryScenario(
                name="竹山天梯",
                township="竹山鎮",
                scenario="橫跨深谷的天梯，挑戰著你的膽量。站在橋上向下望去，是深不見底的太極峽谷。這裡的山風冷冽而清新，每一口呼吸引領著你深入體驗竹山的壯闊景觀。職人告訴你，只有尊重土地的人，才能領略這片美景。",
                skybox_url="zhushan_bridge.jpg",
                base_price=1500,
                base_toll=300,
                api_station_name="竹山"
            )
        ]

        # 3. 寫入資料庫
        db.add_all(grids)
        db.commit()
        print(f"✅ 成功初始化 {len(grids)} 筆冒險格資料！")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 初始化失敗: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()