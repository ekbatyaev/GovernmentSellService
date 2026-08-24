from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    system_token: str

    daily_job_hour_msk: int = 10
    daily_job_minute_msk: int = 0

    token: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: str

    retry_count: int
    retry_delay: int

    scheduler_lock_key: int = 424242

    backfill_days: int = 10
    backfill_on_startup: bool = False

    app_url: str
    app_base: str = ""

settings = Settings()

if __name__ == "__main__":
    print(settings.model_dump())
