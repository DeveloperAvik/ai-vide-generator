import os
import shutil
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="studio_test_"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["STORAGE_ROOT"] = str(_tmp / "storage")
os.environ["MANIFESTS_ROOT"] = str(_tmp / "manifests")  # calibration samples must not leak into the real storage
os.environ["SECRET_KEY"] = "test-secret"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["FIRST_ADMIN_PASSWORD"] = ""
os.environ["SERVICE_TOKEN"] = "svc-token-for-tests"
os.environ["YOUTUBE_TOKEN_FILE"] = str(_tmp / "none.json")
os.environ["YOUTUBE_CLIENT_SECRETS"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security.auth import hash_password  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
needs_say = pytest.mark.skipif(not shutil.which("say") and not shutil.which("piper"), reason="no local TTS")


@pytest.fixture(autouse=True)
def fresh_db():
    from app.security import ratelimit
    ratelimit._hits.clear()  # the limiter is per-process; a long suite would otherwise exhaust the 10/min login budget
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add(User(email="admin@test.local", password_hash=hash_password("pw-test-123"), role="admin"))
    db.commit()
    db.close()
    yield


@pytest.fixture
def db():
    d = SessionLocal()
    yield d
    d.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "pw-test-123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
