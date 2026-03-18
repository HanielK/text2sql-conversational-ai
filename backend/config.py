import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH, override=True)


def _get_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y"}


class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    DB_HOST = os.getenv("DB_HOST", "")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "")
    DB_USER = os.getenv("DB_USER", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    APP_ENV = os.getenv("APP_ENV", "dev")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SQL_ROW_LIMIT = int(os.getenv("SQL_ROW_LIMIT", "100"))
    SQL_TIMEOUT_SECONDS = int(os.getenv("SQL_TIMEOUT_SECONDS", "30"))
    ENABLE_SQL_DEBUG = _get_bool("ENABLE_SQL_DEBUG", "true")
    ENABLE_FILE_LOGGING = _get_bool("ENABLE_FILE_LOGGING", "true")

    FEEDBACK_DIR = str(BASE_DIR / "data" / "feedback")
    LOG_DIR = str(BASE_DIR / "logs")


settings = Settings()

if not settings.OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY not found. Confirm it exists in your .env file "
        f"at: {ENV_PATH}"
    )