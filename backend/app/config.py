from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Panel Caballito y Muñequita API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./panel_caballito_dev.db"
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    # Cualquier API compatible con OpenAI: llama.cpp local, Groq, OpenRouter, etc.
    llama_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    llm_timeout: float = 60.0
    secret_key: str = "dev-only-change-me"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        # Render entrega "postgres://" o "postgresql://"; usamos el driver psycopg 3.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    current = Settings()
    if current.app_env == "production" and current.secret_key == "dev-only-change-me":
        raise RuntimeError("Falta definir SECRET_KEY en producción.")
    return current


settings = get_settings()
