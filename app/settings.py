from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
import sys

async_client_fastapi = httpx.AsyncClient(timeout=30)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

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

    llm_api_key: str
    llm_base_url: str
    llm_model_name: str
    llm_folder_id: str

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

    smtp_server: str
    smtp_port: str
    smtp_user: str
    smtp_email: str
    smtp_password: str
    smtp_test_email: str

    base_url: str
    download_url: str

    soap_timeout: int = 30
    max_concurrent_semaphore: int = 5
    download_timeout: int = 60
    tmp_dir: str

settings = Settings()

if __name__ == "__main__":
    print(settings.model_dump())
