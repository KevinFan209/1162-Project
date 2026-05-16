from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os
from dotenv import load_dotenv
from fastapi import Header, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer

load_dotenv()

# 使用 pbkdf2_sha256（比 bcrypt 在某些 Windows 環境更穩定）
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# JWT 設定
SECRET_KEY = os.getenv("SECRET_KEY", "pypoly-adventure-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 有效期 24 小時

# 密碼加密：將明文密碼 (如 123) 轉為雜湊碼
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# 驗證密碼：比對明文密碼與資料庫中的雜湊碼
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# 建立 JWT Token：登入成功後核發身分憑證
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(authorization: str = Header(None)):
    """
    從 Header 的 Authorization 欄位解析 JWT Token 並回傳 username
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供認證憑證")
    
    token = authorization.split(" ")[1]
    
    try:
        # 解碼 Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="無效的認證資訊")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="登入資訊已過期，請重新登入")