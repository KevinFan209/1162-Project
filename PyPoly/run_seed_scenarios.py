# run_seed_scenarios.py
# 🏆 UTF-8 輸出保險：cp950(繁中) 主控台印中文/emoji 會拋 UnicodeEncodeError。
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import text
from database import engine

# 執行 seed_scenarios.sql：107 筆正式情境資料（含天空盒對應的 id）。
# 這個檔取代掉舊的 init_adventure_data.py（只灌 5 筆、id=1~5）——
# 107 筆上線後 init_adventure_data.py 已不再是現況的種子資料，見
# static/assets/skyboxes/scenarios/README.txt 的說明。
#
# 不用 mysql CLI 是因為 Docker 映像特意不裝 mariadb-client（省 140MB），
# 這裡直接用專案本來就有的 SQLAlchemy/pymysql 連線執行。
# seed_scenarios.sql 目前只有 4 條語句（SET NAMES / DELETE / ALTER /
# 一個大 INSERT），用註解行以外的部分單純按 ; 切開即可，沒有語句內部
# 出現 ASCII 分號的情況。

SQL_PATH = "seed_scenarios.sql"

def run():
    with open(SQL_PATH, encoding="utf-8") as f:
        content = f.read()

    lines = [l for l in content.splitlines() if not l.strip().startswith("--")]
    statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    print(f"✅ 已執行 {SQL_PATH}，共 {len(statements)} 條語句")

if __name__ == "__main__":
    run()
