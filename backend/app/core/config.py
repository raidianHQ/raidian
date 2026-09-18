from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables or a .env file.

    All Raidian Wise settings are prefixed with RAIDIAN_ to avoid collisions with
    other environment variables in shared hosting environments (e.g. Render).
    """

    database_url: str = "sqlite:///./raidian_wise.db"

    jwt_secret_key: str = "insecure-development-secret-change-me"
    """Signing secret for access tokens (HS256, app/core/security.py). This
    default is deliberately insecure and exists only so local development
    and the test suite work with zero required configuration, mirroring
    database_url's own zero-config-friendly default above -- any real
    deployment MUST override it via RAIDIAN_JWT_SECRET_KEY. See
    Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 9.2.
    """
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RAIDIAN_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
