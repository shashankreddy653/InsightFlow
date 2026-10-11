"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    insightflow_database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'insightflow.db'}"
    insightflow_max_upload_mb: int = 25
    insightflow_analysis_batch_size: int = 200
    insightflow_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    insightflow_llm_api_key: str = ""
    insightflow_llm_base_url: str = "https://api.openai.com/v1"
    insightflow_llm_model: str = "gpt-4o-mini"

    adaption_api_key: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.insightflow_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
