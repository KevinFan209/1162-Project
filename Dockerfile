# PyPoly 開發用映像
#
# ⚠️ WORKDIR 必須正好是 PyPoly/ 的內容所在。
#    main.py:57 的 StaticFiles(directory="static") 與 game_start.py:9 的
#    open('norm_hand_standards.json') 都是相對路徑，工作目錄錯了就會 500。
FROM python:3.13-slim

# 刻意不裝 mariadb-client：它單獨就佔 140MB，而我們只需要「等資料庫起來」
# 這一件事——entrypoint 改用已經裝好的 pymysql 做連線測試，效果相同。

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先只複製相依清單再安裝：改程式碼時這一層仍能命中快取，不必重裝套件
COPY PyPoly/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 開發模式下 PyPoly/ 會被 compose 掛載覆蓋掉這一層，
# 但仍然複製一份，讓映像單獨 docker run 也能啟動
COPY PyPoly/ ./
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
