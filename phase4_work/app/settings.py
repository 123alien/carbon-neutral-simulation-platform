import os
from dataclasses import dataclass
from pathlib import Path
from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_DEFAULTS = {
    "test": "sqlite:///./test_carbon_sim.db",
    "e2e": "sqlite:///./frontend_smoke.db",
}

@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    database_url_source: str

def load_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        parsed = make_url(explicit)
        database_name = (parsed.database or "").replace("\\", "/").lower()
        if environment == "development" and database_name.endswith("frontend_smoke.db"):
            raise RuntimeError("development must not use frontend_smoke.db; use APP_ENV=e2e for smoke data")
        if environment == "development" and parsed.get_backend_name() not in {"postgresql", "postgres"}:
            raise RuntimeError("development DATABASE_URL must use PostgreSQL; SQLite is reserved for automated tests")
        if environment == "production" and parsed.get_backend_name() not in {"postgresql", "postgres"}:
            raise RuntimeError("production DATABASE_URL must use PostgreSQL")
        return Settings(environment, explicit, "DATABASE_URL environment variable")
    if environment in {"development", "production"}:
        raise RuntimeError(f"DATABASE_URL is required when APP_ENV={environment}; development and production must use PostgreSQL")
    if environment not in ENV_DEFAULTS:
        raise RuntimeError(f"unsupported APP_ENV: {environment}")
    return Settings(environment, ENV_DEFAULTS[environment], f"built-in {environment} default")

def database_identity(database_url: str) -> tuple[str, str]:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        raw = url.database or ":memory:"
        location = raw if raw == ":memory:" else str((ROOT_DIR / raw).resolve()) if not Path(raw).is_absolute() else str(Path(raw).resolve())
        return "sqlite", location
    return url.get_backend_name(), url.database or "unknown"
