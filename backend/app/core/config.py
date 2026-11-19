"""Centralized settings loaded from environment, with production safety checks."""
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    APP_ENV: Literal["development", "production"] = "development"
    APP_NAME: str = "AgentShield"
    LOG_LEVEL: str = "INFO"

    # Demo mode — when True, unauthenticated tenant/agent registration is allowed
    # Must be False in production. Rate limiting is applied regardless.
    DEMO_MODE: bool = False

    # DB
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://agentshield:agentshield@localhost:5432/agentshield"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    AGENTSHIELD_JWT_SECRET: str = Field(
        default="replace-with-at-least-32-random-characters-please"
    )
    AGENTSHIELD_JWT_ALGORITHM: str = "HS256"
    AGENTSHIELD_ACCESS_TOKEN_MINUTES: int = 30

    # API
    API_DOCS_ENABLED: bool = True
    ALLOW_PUBLIC_DOCS: bool = False

    # CORS — explicit allow-list; CORS_ALLOWED_REGEX is optional and additive.
    # Never use a wildcard regex with allow_credentials=True.
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    CORS_ALLOWED_REGEX: str = ""

    # Policy
    POLICY_DIR: str = "./policies"

    # Audit
    AUDIT_HMAC_SECRET: str = Field(
        default="replace-with-a-different-32-char-random-secret"
    )
    # API key hashing — must differ from AUDIT_HMAC_SECRET
    API_KEY_HMAC_SECRET: str = Field(
        default="replace-with-a-third-32-char-random-secret"
    )

    # Kill switch
    KILL_SWITCH_ENABLED: bool = True

    # HITL
    SLACK_WEBHOOK_URL: str = ""
    APPROVAL_BASE_URL: str = "http://localhost:8000"
    APPROVAL_TIMEOUT_MINUTES: int = 30

    # Supabase Audit Logging
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_TABLE: str = "agentshield_call_logs"

    # Groq LLM
    GROQ_API_KEY: str = ""

    @field_validator("AGENTSHIELD_JWT_SECRET", "AUDIT_HMAC_SECRET", "API_KEY_HMAC_SECRET")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("secret must be at least 32 characters")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS comma-separated string into a list.

        Falls back to [] (deny all) in production when the list is empty.
        In development falls back to localhost defaults.
        Set CORS_ORIGINS explicitly in production to restrict access.
        """
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return origins

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        """Refuse to boot in production with placeholder secrets."""
        if self.APP_ENV == "production":
            _PLACEHOLDERS = ("replace-with",)
            for name in ("AGENTSHIELD_JWT_SECRET", "AUDIT_HMAC_SECRET", "API_KEY_HMAC_SECRET"):
                value = getattr(self, name)
                if any(value.startswith(p) for p in _PLACEHOLDERS):
                    raise ValueError(
                        f"{name} must be changed before running in production"
                    )

            # The two HMAC secrets must be different to limit blast radius of a leak
            if self.AUDIT_HMAC_SECRET == self.API_KEY_HMAC_SECRET:
                raise ValueError(
                    "AUDIT_HMAC_SECRET and API_KEY_HMAC_SECRET must be different values"
                )

            if self.API_DOCS_ENABLED and not self.ALLOW_PUBLIC_DOCS:
                raise ValueError(
                    "API_DOCS_ENABLED must be false in production "
                    "(or set ALLOW_PUBLIC_DOCS=true to explicitly allow it)"
                )

            if self.DEMO_MODE:
                raise ValueError(
                    "DEMO_MODE must be false in production"
                )
        return self


settings = Settings()
