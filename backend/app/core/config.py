from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://studio:studio@localhost:5432/cyber_studio"
    secret_key: str = "change-me-in-env"
    service_token: str = ""  # bearer token for n8n; cannot approve
    access_token_minutes: int = 720
    storage_root: Path = ROOT / "storage" / "local"
    manifests_root: Path = ROOT / "storage" / "manifests"
    video_engine_dir: Path = ROOT / "video-engine"
    ai_dir: Path = ROOT / "ai"

    app_env: str = "development"  # development | production. Production refuses mock providers and weak secrets.
    reviewer_model: str = ""  # Ollama model for the independent technical review; empty = same model as the writer (run sequentially)
    reviewer_timeout_s: int = 900
    research_max_bytes: int = 2_000_000
    research_timeout_s: float = 15
    research_user_agent: str = "ciphercast-research/1.0 (+local educational tool)"
    llm_fallback_provider: str = ""  # e.g. "ollama": used when the primary raises LLMError
    voice_name: str = "default"  # label stored with generations for consistency tracking
    render_engine: str = "ffmpeg"  # ffmpeg | remotion

    # AI provider mode: "mock" (offline), "ollama", "anthropic"
    llm_provider: str = "mock"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_timeout_s: int = 900  # max silence while Ollama generates one answer (read timeout); queue time is NOT counted, see ollama_queue_wait_s
    ollama_connect_timeout_s: float = 10
    ollama_connect_retries: int = 2  # only for "cannot connect" (e.g. Ollama restarting): exponential backoff 2s, 4s + jitter. Timeouts are never retried here.
    ollama_queue_wait_s: int = 3600  # max wait for another generation in this process to finish (one local model serves one request at a time)

    # Voice: "auto" picks piper -> macos_say -> none
    voice_provider: str = "auto"
    piper_binary: str = "piper"
    piper_model: str = ""
    kokoro_model: str = str(ROOT / "voice" / "models" / "kokoro" / "kokoro-v1.0.onnx")  # Apache-2.0 model, runs locally on CPU
    kokoro_voices: str = str(ROOT / "voice" / "models" / "kokoro" / "voices-v1.0.bin")
    kokoro_voice: str = "am_michael"
    kokoro_speed: float = 1.0
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    avatar_provider: str = "static"
    heygen_api_key: str = ""
    heygen_avatar_id: str = ""
    musetalk_dir: str = ""

    youtube_client_secrets: str = ""
    youtube_token_file: str = str(ROOT / "storage" / "youtube_token.json")
    youtube_redirect_uri: str = "http://localhost:8000/api/youtube/oauth/callback"

    rate_limit_per_minute: int = 120
    first_admin_email: str = "admin@example.com"
    first_admin_password: str = ""
    cors_origins: str = "http://localhost:3000"


RUNTIME_FILE = ROOT / "storage" / "runtime_config.json"
RUNTIME_KEYS = {"llm_provider", "llm_fallback_provider", "anthropic_api_key", "anthropic_model", "ollama_url", "ollama_model",
                "voice_provider", "piper_model", "avatar_provider"}


@lru_cache
def get_settings() -> Settings:
    """Env/.env first, then overrides saved from the dashboard (storage/runtime_config.json, mode 0600)."""
    import json
    s = Settings()
    if RUNTIME_FILE.exists():
        try:
            for k, v in json.loads(RUNTIME_FILE.read_text()).items():
                if k in RUNTIME_KEYS:
                    setattr(s, k, v)
        except (ValueError, OSError):
            pass
    return s


def save_runtime(updates: dict) -> None:
    import json
    cur = {}
    if RUNTIME_FILE.exists():
        cur = json.loads(RUNTIME_FILE.read_text())
    cur.update({k: v for k, v in updates.items() if k in RUNTIME_KEYS})
    RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_FILE.write_text(json.dumps(cur))
    RUNTIME_FILE.chmod(0o600)
    get_settings.cache_clear()
