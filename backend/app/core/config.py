import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = Field(default='sqlite:///./farmlink.db')
    jwt_secret: str = Field(default='local-demo-secret-change-in-production')
    jwt_expire_minutes: int = 720
    frontend_origin: str = 'http://localhost:5173'
    demo_mode: bool = True

@lru_cache
def get_settings() -> Settings: return Settings()
