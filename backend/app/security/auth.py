from datetime import datetime, timedelta, timezone

import hmac

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


DUMMY_HASH = bcrypt.hashpw(b'dummy-password', bcrypt.gensalt()).decode()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, s.secret_key, algorithm="HS256")


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    svc = get_settings().service_token
    if svc and hmac.compare_digest(token.encode(), svc.encode()):
        return User(id=0, email="n8n@service", password_hash="", role="service", is_active=True)  # transient, never persisted
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        user = db.get(User, int(data["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid token")
    if not user or not user.is_active:
        raise HTTPException(401, "Inactive user")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


def require_human(user: User = Depends(current_user)) -> User:
    """Approvals must come from a person: the automation service token is refused."""
    if user.role not in ("admin", "reviewer"):
        raise HTTPException(403, "Human reviewer required")
    return user
