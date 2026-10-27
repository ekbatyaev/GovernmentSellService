from datetime import datetime
from app.settings import logger, MOSCOW_TZ
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.crud.purchase import search_purchases, delete_purchase
from app.backend.database.crud.service import search_auth_codes, delete_auth_code
from app.schemas.purchase import Notice, FilterNotice
from app.schemas.service import FilterAuthCode
from sqlalchemy.exc import IntegrityError
from typing import Any

def moscow_datetime() -> datetime:
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)

async def get_row_base_info(purchase: Notice) -> dict[str, Any]:
    row = {
        "Реестровый номер": purchase.registration_number,
        "Название закупки": purchase.name,
        "Сумма закупки": purchase.initial_sum,
        "Дата начала подачи заявок": purchase.submission_start_datetime,
        "Дата окончания подачи заявок": purchase.submission_close_datetime,
        "Дата публикации": purchase.publication_datetime,
        "Заказчик название": purchase.customer.full_name
    }
    return row

async def complete_row_tender(filter_name: str, purchase: Notice) -> dict[str, Any]:
    row = await get_row_base_info(purchase)

    if filter_name == "Тендеры для Россетей":
        row = {**row,
               "Победитель": purchase.result_info.get("Победитель"),
               "Другие участники": purchase.result_info.get("Другие участники"),
               "Ячейки": purchase.result_info.get("Ячейки"),
               "Кол-во ячеек": purchase.result_info.get("Кол-во ячеек"),
               "Типовой проект": purchase.result_info.get("Типовой проект"),
               "Проектировщик": purchase.result_info.get("Проектировщик"),
               "Дата исполнения договора": purchase.result_info.get("Дата исполнения договора"),
               "Филиал/РЭС": purchase.result_info.get("Филиал/РЭС"),
               "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.registration_number}"
               }
    elif filter_name == "Тендеры для OEM":
        row = {**row,
               "Контактное лицо": (purchase.contact.last_name + " " + purchase.contact.first_name + " "
                                   + purchase.contact.middle_name),
               "Телефон": purchase.contact.phone,
               "Email": purchase.contact.email,
               "Победитель": purchase.result_info.get("Победитель"),
               "Итоговая цена контракта": purchase.result_info.get("Итоговая цена контракта"),
               "Слова маячки в тз": purchase.result_info.get("Слова маячки в тз"),
               "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.registration_number}"
               }

    elif filter_name == "Тендеры для ITM":
        row = {**row,
               "Победитель": purchase.result_info.get("Победитель"),
               "ИНН": purchase.result_info.get("ИНН"),
               "Итоговая цена контракта": purchase.result_info.get("Итоговая цена контракта"),
               "Другие участники": purchase.result_info.get("Другие участники"),
               "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.registration_number}"
               }

    return row

async def clean_notices(db: AsyncSession, **kwargs) -> None:
    try:
        purchases = await search_purchases(db, FilterNotice(**kwargs))
    except IntegrityError as e:
        logger.exception(f"Произошла ошибка получения данных заявок: {e}")
        raise

    deleted_count = 0
    for purchase in purchases:
        try:
            delete_status = await delete_purchase(db, purchase.guid)
            deleted_count += int(delete_status)

        except IntegrityError as e:
            logger.exception(f"Произошла ошибка удаления старой заявки: {e}")
            continue

    logger.info(
        f"Daily job: успешно удалено {deleted_count} заявок из {len(purchases)}"
    )

async def clean_auth_codes(db: AsyncSession, **kwargs) -> None:
    try:
        auth_codes = await search_auth_codes(db, FilterAuthCode(**kwargs))
    except IntegrityError as e:
        logger.exception(f"Произошла ошибка получения данных заявок: {e}")
        raise

    deleted_count = 0
    for auth_code in auth_codes:
        try:
            delete_status = await delete_auth_code(db, auth_code.guid)
            deleted_count += int(delete_status)

        except IntegrityError as e:
            logger.exception(f"Произошла ошибка удаления старой заявки: {e}")
            continue

    logger.info(
        f"Daily job: успешно удалено {deleted_count} заявок из {len(auth_codes)}"
    )
