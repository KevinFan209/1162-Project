情境用的 360 度全景圖放這裡，檔名就是 scenarios 資料表的 id：

    1.jpg ~ 107.jpg，對應 107 個南投情境地點。

對應關係以 seed_scenarios.sql 為準（id 1~107，一一對應圖檔）。
main.py 的 /game/map_config 會直接用 f"scenarios/{id}.jpg" 推導圖檔
路徑（資料表本身沒有存檔名欄位），所以圖檔只要照 id 命名就一定對得上。

（舊版 init_adventure_data.py 只灌 5 筆的種子腳本已經刪掉，README.md
跟 docker/entrypoint.sh 都改成跑 run_seed_scenarios.py，一律對應這
107 筆、不會再被蓋回舊資料。）

圖還沒放進來時：
  game.html 的 loadTextureSafe 會自動改用 sky_reward.jpg 當替代背景，
  遊戲流程照常進行，只是風景不是正確的那個地點。
