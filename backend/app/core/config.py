from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = f"sqlite:///{(BACKEND_ROOT / 'farmlink.db').as_posix()}"
# Uploaded listing images live here. Served by FastAPI at /uploads/<filename>.
UPLOAD_DIR = BACKEND_ROOT / 'uploads'

# The secret this repo ships with. Fine locally, published on GitHub, so it
# cannot be trusted to sign anything a stranger could reach.
DEMO_JWT_SECRET = 'local-demo-secret-change-in-production'

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / '.env',
        extra='ignore',
    )

    # Anchored to backend/farmlink.db regardless of the shell's working directory.
    database_url: str = Field(default=DEFAULT_SQLITE_URL)
    jwt_secret: str = Field(default=DEMO_JWT_SECRET)
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

    @model_validator(mode='after')
    def _refuse_demo_secret_outside_demo_mode(self):
        """Refuse to start with the published secret once DEMO_MODE is off.

        The demo secret is in this repository, so anyone who can read the code
        can sign a token claiming to be an admin. That is harmless on a laptop
        nobody can reach, and not harmless on a public host.

        Raising here rather than warning means a real deployment cannot come up
        misconfigured — it fails at startup, loudly, instead of running quietly
        with a key the whole internet has.
        """
        if not self.demo_mode and self.jwt_secret == DEMO_JWT_SECRET:
            raise ValueError(
                'JWT_SECRET is still the demo default while DEMO_MODE is off. '
                'Anyone with this repository can forge an admin token. '
                'Set JWT_SECRET to a long random string, or set DEMO_MODE=true '
                'if this is only a local demo.'
            )
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()