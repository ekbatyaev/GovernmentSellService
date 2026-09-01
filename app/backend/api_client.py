from datetime import datetime

import httpx
from typing import Any, Dict
from app.settings import settings, logger, async_client_fastapi, MOSCOW_TZ


async def api_datum_query(token: str, endpoint: str, **filters: Any) -> Dict[str, Any]:
    url = f"{settings.app_url}{settings.app_base}/{endpoint}"
    payload = {"token": token, **filters}
    attempts = 0
    while attempts < settings.retry_count:
        try:
            response = await async_client_fastapi.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}, attempt: {attempts}")
        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {e}, attempt: {attempts}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}, attempt: {attempts}")
        attempts += 1
    else:
        logger.error(f"All attempts of posting {endpoint} failed at {str(datetime.now(MOSCOW_TZ).isoformat())}")
        return {}