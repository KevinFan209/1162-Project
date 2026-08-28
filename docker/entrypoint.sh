#!/bin/sh
# PyPoly 容器啟動流程
#
# ⚠️ 這個檔案必須是 LF 換行。CRLF 會讓 Linux 找不到直譯器並噴
#    "bad interpreter"，而錯誤訊息完全看不出是換行問題。
#    根目錄的 .gitattributes 已加上 *.sh text eol=lf 來保證這件事。
set -e

# 等資料庫就緒。
# compose 已經有 healthcheck，這裡再保險一層：healthcheck 通過到真正能建立
# 連線之間仍有短暫空窗，直接啟動偶爾會撞上 connection refused。
#
# 用 pymysql 而不是 mariadb-client：後者光是裝進映像就要 140MB，
# 而 pymysql 本來就是專案相依（SQLAlchemy 的驅動）。
python - <<'PY'
import sys, time
import sqlalchemy
import database

print("⏳ 等待資料庫就緒...", flush=True)
for i in range(60):
    try:
        with database.engine.connect() as c:
            c.execute(sqlalchemy.text("SELECT 1"))
        print("✅ 資料庫已就緒", flush=True)
        break
    except Exception as e:
        if i == 0:
            print(f"   （尚未就緒：{type(e).__name__}）", flush=True)
        time.sleep(1)
else:
    print("❌ 等待資料庫逾時（60 秒）", flush=True)
    sys.exit(1)
PY

# 建立資料表。main.py 啟動時也會呼叫 create_all()，但先在這裡做完，
# 才能在下一步判斷「題庫是不是空的」。
python -c "
import models, database
models.Base.metadata.create_all(bind=database.engine)
print('✅ 資料表已確認')
"

# 只在題庫為空時才灌資料。
# seed_data.py 會先 delete() 再重建，每次啟動都跑等於白做工，
# 也會把組員自己加的題目洗掉。
NEED_SEED=$(python -c "
import models, database
db = database.SessionLocal()
print('yes' if db.query(models.Question).count() == 0 else 'no')
db.close()
")

if [ "$NEED_SEED" = "yes" ]; then
    echo "🌱 首次啟動，正在灌入題庫與冒險格資料..."
    python seed_data.py
    python init_adventure_data.py
else
    echo "⏭️  題庫已有資料，略過 seed"
fi

# create_admin.py 自己有存在性檢查，可以無條件執行
python create_admin.py

echo "🚀 啟動 PyPoly (main:sio_app)"
# ⚠️ 進入點是 sio_app 不是 app；用 app 的話 /socket.io 會全部 404
exec uvicorn main:sio_app --host 0.0.0.0 --port 8000 --reload
