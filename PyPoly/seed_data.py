from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models

# 初始化：確保資料表已根據新欄位建立
models.Base.metadata.create_all(bind=engine)

def seed_data():
    db = SessionLocal()
    # 清除舊資料 (選用，避免重複執行導致資料堆疊)
    db.query(models.Question).delete()
    db.query(models.CountryScenario).delete()

    for i in range(1, 21):
        diff = "easy" if i <= 7 else "normal" if i <= 14 else "hard"
        
        # 🏆 基礎版題目：選項分開存放
        db.add(models.Question(
            category="basic", 
            difficulty=diff, 
            content=f"基礎題 {i}: {i}+{i}=?", 
            opt1=f"{i*2}",    # 選項 1 的純內容
            opt2=f"{i+5}",    # 選項 2 的純內容
            opt3=f"{i-1}",    # 選項 3 的純內容
            answer=1          # 正確答案直接是數字 1
        ))

        # 進階版題目 (如果是簡答題，選項留空)
        db.add(models.Question(
            category="advanced", 
            difficulty=diff, 
            content=f"進階題 {i}: 請輸入數字 {i} 的英文：", 
            opt1=None, opt2=None, opt3=None,
            answer=i # 假設進階題答案是數字本身
        ))

        # 國家情境保持不變
        db.add(models.CountryScenario(
            name=f"Country_{i}", 
            scenario=f"這是第 {i} 個國家的神祕情境描述..."
        ))
        
    db.commit()
    db.close()
    print("✅ 成功插入 20 筆分欄位題目資料！")

if __name__ == "__main__":
    seed_data()