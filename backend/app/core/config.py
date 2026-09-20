from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = f"sqlite:///{(BACKEND_ROOT / 'farmlink.db').as_posix()}"
# Uploaded listing images live here. Served by FastAPI at /uploads/<filename>.
UPLOAD_DIR = BACKEND_ROOT / 'uploads'

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / '.env',
        extra='ignore',
    )

    # Anchored to backend/farmlink.db regardless of the shell's working directory.
    database_url: str = Field(default=DEFAULT_SQLITE_URL)
    jwt_secret: str = Field(default='local-demo-secret-change-in-production')
    jwt_expire_minutes: int = 720
    frontend_origin: str = 'http://localhost:5173'
    demo_mode: bool = True

    # After a farmer rejects a buyer's order on a listing, that buyer cannot
    # place another order on the SAME listing for this many hours. Guards
    # against a buyer repeatedly re-requesting produce the farmer declined.
    buyer_rejection_cooldown_hours: int = 48

    # Distinct reports against a farmer before their lifespan_hours field is
    # locked in the create-listing form. Read by GET /reports/against-me.
    report_lock_threshold: int = 3

@lru_cache
def get_settings() -> Settings:
    return Settings()
