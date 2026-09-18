from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables or a .env file.

    All Raidian Wise settings are prefixed with RAIDIAN_ to avoid collisions with
    other environment variables in shared hosting environments (e.g. Render).
    """

    database_url: str = "sqlite:///./raidian_wise.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RAIDIAN_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
