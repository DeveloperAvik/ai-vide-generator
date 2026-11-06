"""Storage abstraction. LocalStorage is used now; implement the same interface over boto3 for S3-compatible storage."""
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings
from app.security.paths import resolve_within, safe_name


class Storage(ABC):
    @abstractmethod
    def path(self, *parts: str) -> Path: ...

    @abstractmethod
    def save_bytes(self, rel: str, data: bytes) -> Path: ...


class LocalStorage(Storage):
    def __init__(self, root: Path | None = None):
        self.root = (root or get_settings().storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        p = resolve_within(self.root, *parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def save_bytes(self, rel: str, data: bytes) -> Path:
        p = self.path(*Path(rel).parts[:-1], safe_name(Path(rel).name))
        p.write_bytes(data)
        return p

    def lesson_dir(self, lesson_id: int, *sub: str) -> Path:
        d = self.path("lessons", str(int(lesson_id)), *sub)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def rel(self, p: Path) -> str:
        return str(p.resolve().relative_to(self.root))


def get_storage() -> LocalStorage:
    return LocalStorage()
