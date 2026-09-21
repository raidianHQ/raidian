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
    jwt_access_token_expire_minutes: int = 1440

    ai_api_key: str = ""
    """Credential for the sole AI provider the Reflection Engine (ADR-0005,
    docs/DECISIONS.md) is permitted to call. Deliberately blank by default
    -- no real AI call is possible out of the box, mirroring
    jwt_secret_key's own "insecure but functional by default" stance
    inverted: here, an unconfigured deployment fails closed (the AI
    Narrative Layer refuses to run -- see
    app/services/reflection_engine/client.py::ReflectionEngineNotConfiguredError)
    rather than silently working with a bad default. Never read by, or
    exposed to, the frontend -- see
    Documentation/AI_NARRATIVE_LAYER_DESIGN.md Section 6.
    """
    ai_base_url: str = "https://api.anthropic.com"
    ai_model: str = "claude-sonnet-5"
    ai_anthropic_version: str = "2023-06-01"
    ai_request_timeout_seconds: float = 30.0
    ai_max_output_tokens: int = 2000

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
