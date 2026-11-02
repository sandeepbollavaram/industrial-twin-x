"""Runtime configuration, read from the environment and .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_db: str = "twinx"
    postgres_user: str = "twinx"
    postgres_password: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 15432
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    factory_id: str = "plant-01"
    model_path: str = "research/models/current/bundle.joblib"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
