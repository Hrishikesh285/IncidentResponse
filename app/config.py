"""Application configuration loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configurable settings for OpsMemory, sourced from .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Groq LLM
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "qwen/qwen3-32b"

    # Hindsight memory
    hindsight_api_key: str = ""
    hindsight_base_url: str = "https://api.hindsight.vectorize.io"
    hindsight_bank_id: str = "opsmemory-prod"

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "opsmemory"

    # Soft preference for local fallbacks when external services are missing.
    # Presence of API keys always wins and enables live backends.
    demo_mode: bool = True

    @property
    def use_groq(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def use_hindsight(self) -> bool:
        return bool(self.hindsight_api_key.strip())


settings = Settings()
