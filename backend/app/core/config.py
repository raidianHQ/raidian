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

    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    """Comma-separated list of origins permitted to make cross-origin
    requests to this API (Access-Control-Allow-Origin). Defaults to the
    local Vite dev server only (frontend/vite.config.ts's own
    unoverridden default port) -- any real deployment MUST override this
    via RAIDIAN_CORS_ALLOWED_ORIGINS to include the deployed frontend's
    actual origin, mirroring jwt_secret_key's own override-required
    convention. See Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 3.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RAIDIAN_",
        extra="ignore",
    )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
