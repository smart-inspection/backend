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

    secret_key: str = "c28b524c-400b-4ca0-aff9-f6d0ebd1cb92"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    paddle_max_image_width: int = 4000
    paddle_max_image_height: int = 4000

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()