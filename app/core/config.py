from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Smart Inspection API"
    app_env: str = "dev"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    llm_temperature: float = 0.2
    llm_timeout: int = 120

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()