from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import User
from app.security.auth import hash_password
from app.security.ratelimit import rate_limit_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.app_env == "production":
        if len(s.secret_key) < 32 or s.secret_key == "change-me-in-env":
            raise RuntimeError("APP_ENV=production requires SECRET_KEY of at least 32 chars")
        if s.service_token and len(s.service_token) < 32:
            raise RuntimeError("SERVICE_TOKEN must be at least 32 chars")
        if "*" in s.cors_origins:
            raise RuntimeError("wildcard CORS not allowed in production")
    if s.secret_key in ("change-me-in-env", "") or len(s.secret_key) < 32:
        import logging
        logging.getLogger("studio").warning("SECRET_KEY is weak/default - generate one with: openssl rand -hex 32")
    if s.first_admin_password:  # bootstrap admin only when explicitly configured
        db = SessionLocal()
        try:
            if not db.query(User).filter_by(email=s.first_admin_email).first():
                db.add(User(email=s.first_admin_email, password_hash=hash_password(s.first_admin_password), role="admin"))
                db.commit()
        finally:
            db.close()
    yield


_prod = get_settings().app_env == "production"
app = FastAPI(title="CipherCast", version="1.0.0", lifespan=lifespan,
              docs_url=None if _prod else "/docs", redoc_url=None, openapi_url=None if _prod else "/openapi.json")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp

app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
app.middleware("http")(rate_limit_middleware)
app.include_router(router)
