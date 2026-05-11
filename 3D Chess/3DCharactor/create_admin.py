# create_admin.py
from database import SessionLocal
from models import User
from auth_utils import get_password_hash
import models, database

# 確保表格已建立
models.Base.metadata.create_all(bind=database.engine)

db = SessionLocal()

# 檢查管理員是否已存在，避免重複建立
existing_admin = db.query(User).filter(User.username == "admin").first()

if not existing_admin:
    admin = User(
        username="admin", 
        email="admin@gmail.com", 
        hashed_password=get_password_hash("123"), # 密碼設為 123
        role="admin"
    )
    db.add(admin)
    db.commit()
    print("管理者帳號 (admin) 建立成功！")
else:
    print("管理者帳號已存在。")

db.close()