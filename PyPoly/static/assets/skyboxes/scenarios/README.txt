情境用的 360 度全景圖放這裡，檔名就是 scenarios 資料表的 id：

    1.jpg  中興新村 - 世界茶業博覽會
    2.jpg  埔里酒廠
    3.jpg  魚池 - 日月潭
    4.jpg  中寮土窯
    5.jpg  竹山天梯

對應關係以 init_adventure_data.py 為準（該檔已寫死 id=1~5）。

為什麼放在這個子目錄：
  上一層已有 24.jpg~107.jpg 共 84 張圖，若直接放同一層，
  情境數成長到 24 個以上就會撞名，而且不會報錯，只會默默顯示錯的地方。

圖還沒放進來時：
  game.html 的 loadTextureSafe 會自動改用 sky_reward.jpg 當替代背景，
  遊戲流程照常進行，只是風景不是正確的那個地點。
