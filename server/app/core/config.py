from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # server/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'benchgres.db'}"

    TARGET_HOST: str = "localhost"
    TARGET_PORT: int = 5434
    TARGET_USER: str = "benchgres_ro"
    TARGET_PASSWORD: str = "benchgres_ro"

    THROWAWAY_HOST: str = "localhost"
    THROWAWAY_PORT: int = 5433
    THROWAWAY_USER: str = "postgres"
    THROWAWAY_PASSWORD: str = "postgres"

    STATEMENT_TIMEOUT_MS: int = 60000

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
