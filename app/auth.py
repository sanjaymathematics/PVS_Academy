import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .database import get_db

# In production, set SECRET_KEY via environment variable and never commit it.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Anyone registering as "teacher" must supply this code. Set your own value
# via the TEACHER_SIGNUP_CODE environment variable on Render — do not rely
# on the default below in production.
TEACHER_SIGNUP_CODE = os.environ.get("TEACHER_SIGNUP_CODE", "changeme-teacher-code")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def require_teacher(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.Role.teacher:
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user


# ---------- login rate limiting ----------
# Simple in-memory tracker keyed by email. Resets whenever the process
# restarts (e.g. on redeploy) — fine for a small classroom app, not meant
# to be a hardened defense.
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
_failed_logins: dict[str, list[datetime]] = {}


def _recent_attempts(email: str) -> list[datetime]:
    cutoff = datetime.utcnow() - timedelta(minutes=LOCKOUT_MINUTES)
    attempts = [t for t in _failed_logins.get(email, []) if t > cutoff]
    _failed_logins[email] = attempts
    return attempts


def is_login_locked(email: str) -> bool:
    return len(_recent_attempts(email)) >= MAX_LOGIN_ATTEMPTS


def register_failed_login(email: str) -> None:
    attempts = _recent_attempts(email)
    attempts.append(datetime.utcnow())
    _failed_logins[email] = attempts


def clear_failed_logins(email: str) -> None:
    _failed_logins.pop(email, None)


def generate_temp_password() -> str:
    return secrets.token_urlsafe(6)
