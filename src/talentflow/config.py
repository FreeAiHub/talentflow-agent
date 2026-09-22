"""Application settings (env prefix: TALENTFLOW_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TALENTFLOW_", env_file=".env", extra="ignore"
    )

    database_url: str = "sqlite:///./talentflow.db"
    openai_api_key: str | None = None
    vapi_api_key: str | None = None
    # Response is sent only after human confirmation while True.
    human_in_the_loop: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
