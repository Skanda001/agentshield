"""Centralized settings loaded from environment, with production safety checks."""
from typing import List, Literal

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
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Policy
    POLICY_DIR: str = "./policies"

    # Audit
    AUDIT_HMAC_SECRET: str = Field(
        default="replace-with-a-different-32-char-random-secret"
    )
        # API key hashing
    API_KEY_HMAC_SECRET: str = Field(
        default="replace-with-a-third-32-char-random-secret"
    )

    # Kill switch
    KILL_SWITCH_ENABLED: bool = True

    # HITL
    SLACK_WEBHOOK_URL: str = ""
    APPROVAL_BASE_URL: str = "http://localhost:8001"
    APPROVAL_TIMEOUT_MINUTES: int = 30

    # Supabase Audit Logging
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_TABLE: str = "agentshield_call_logs"

    # Groq LLM
    GROQ_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @field_validator("AGENTSHIELD_JWT_SECRET", "AUDIT_HMAC_SECRET", "API_KEY_HMAC_SECRET")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("secret must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def _production_safety(self):
        """Refuse to boot in production with placeholder secrets."""
        if self.APP_ENV == "production":
            for name in ("AGENTSHIELD_JWT_SECRET", "AUDIT_HMAC_SECRET"):
                value = getattr(self, name)
                if value.startswith("replace-with"):
                    raise ValueError(
                        f"{name} must be changed before running in production"
                    )

            if self.API_DOCS_ENABLED and not self.ALLOW_PUBLIC_DOCS:
                raise ValueError(
                    "API_DOCS_ENABLED must be false in production "
                    "(or set ALLOW_PUBLIC_DOCS=true to explicitly allow it)"
                )
        return self


settings = Settings()