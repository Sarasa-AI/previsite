from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

MAX_BCRYPT_BYTES = 72

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """بررسی تطابق رمز عبور"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8")[:MAX_BCRYPT_BYTES],
        hashed_password.encode("utf-8"),
    )

def get_password_hash(password: str) -> str:
    """هش کردن رمز عبور"""
    return bcrypt.hashpw(
        password.encode("utf-8")[:MAX_BCRYPT_BYTES],
        bcrypt.gensalt(),
    ).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """ساخت JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """رمزگشایی JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
