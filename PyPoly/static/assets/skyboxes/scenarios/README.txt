情境用的 360 度全景圖放這裡，檔名就是 scenarios 資料表的 id：

    1.jpg ~ 107.jpg，對應 107 個南投情境地點。

對應關係以 seed_scenarios.sql 為準（id 1~107，一一對應圖檔）。
main.py 的 /game/map_config 會直接用 f"scenarios/{id}.jpg" 推導圖檔
路徑（資料表本身沒有存檔名欄位），所以圖檔只要照 id 命名就一定對得上。

⚠️ init_adventure_data.py 這個舊的種子腳本還留著，只會灌 5 筆舊資料
（id=1~5）並清空整個 scenarios 資料表。如果之後重新初始化資料庫時
照 README.md 的步驟跑了這個腳本，107 筆會被蓋回舊的 5 筆，圖檔雖然
還在但大部分會對不到任何情境。要確認目前是不是用 107 筆版本，可以
直接查 scenarios 資料表的筆數，或改用 seed_scenarios.sql 重新灌。

圖還沒放進來時：
  game.html 的 loadTextureSafe 會自動改用 sky_reward.jpg 當替代背景，
  遊戲流程照常進行，只是風景不是正確的那個地點。
