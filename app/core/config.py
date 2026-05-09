from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Smart Inspection API"
    app_env: str = "dev"
    debug: bool = True
    database_url: str = "sqlite:///database.db"
    api_v1_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()