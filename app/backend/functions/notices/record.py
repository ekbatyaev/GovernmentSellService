from app.backend.database.models import NoticeDatabase
from app.backend.database.settings import db_session
from app.settings import logger
from app.schemas.purchase import Notice, FilterNotice, UpdateNotice
from app.backend.database.crud.purchase import search_purchases, put_purchase, update_purchase
from sqlalchemy.exc import IntegrityError
from typing import Literal
import asyncio

async def save_purchase_record(purchase: Notice, registration_numbers_dict_per_day: dict, record_semaphore: asyncio.Semaphore) -> None:
    async with record_semaphore:
        try:
            async with db_session() as db:
                # Ищем заявку
                try:
                    purchases: list[Notice] = await search_purchases(db,
                                                                     FilterNotice(registration_number=purchase.registration_number,
                                                                        list_filter_type_name=[purchase.filter_type_name]))
                except IntegrityError as e:
                    logger.exception(f"Произошла ошибка получения данных поиска заявок: {e}, ")
                    raise

                # Если не находим создаем
                if len(purchases) == 0:
                    try:
                        purchase: NoticeDatabase = await put_purchase(db, purchase)
                    except IntegrityError as e:
                        logger.exception(f"Произошла ошибка создания заявки: {e} ")
                        raise

                    logger.info(
                        "Pipeline: создана новая закупка через API | reg=%s | guid=%s",
                        purchase.registration_number,
                        purchase.guid,
                    )

                    registration_numbers_dict_per_day[purchase.filter_type_name][purchase.region_number].created.append(
                        purchase.registration_number
                    )

                # Если находим обновляем
                elif len(purchases) > 1:
                    logger.exception(
                        "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s",
                        purchase.registration_number,
                        purchase.guid,
                    )
                    registration_numbers_dict_per_day[purchase.filter_type_name][purchase.region_number].skipped.append(
                        purchase.registration_number
                    )
                elif len(purchases) == 1:
                    try:
                        purchase_status: Literal["not found", "updated"] = await update_purchase(db, purchases[0].guid, UpdateNotice(**purchase.model_dump()))
                    except IntegrityError as e:
                        logger.exception(f"Произошла ошибка создания заявки: {e} ")
                        raise

                    if purchase_status == "updated":
                        logger.info(
                            "Pipeline: обновлена закупка через API | reg=%s | guid=%s",
                            purchase.registration_number,
                            purchase.guid,
                        )

                        registration_numbers_dict_per_day[purchase.filter_type_name][
                            purchase.region_number].updated.append(
                            purchase.registration_number
                        )
                    else:
                        logger.exception(
                            "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s",
                            purchase.registration_number,
                            purchase.guid,
                        )

                        registration_numbers_dict_per_day[purchase.filter_type_name][
                            purchase.region_number].skipped.append(
                            purchase.registration_number
                        )

        except Exception as e:
            logger.exception(
                "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s, ошибка=%s",
                purchase.registration_number,
                purchase.guid,
                e
            )

            filter_type_name = purchase.filter_type_name
            region_number = purchase.region_number
            registration_number = purchase.registration_number
            if filter_type_name and region_number and registration_number:
                registration_numbers_dict_per_day[filter_type_name][region_number].skipped.append(registration_number)
            else:
                logger.error(
                    "Pipeline: не удалось учесть запись как skipped — нет ключей | purchase=%s",
                    purchase,
                )


async def save_protocol_record(protocol: Notice, registration_numbers_dict_per_day: dict, record_semaphore: asyncio.Semaphore) -> None:
    async with record_semaphore:
        try:
            async with db_session() as db:
                # Ищем заявку
                try:
                    purchases: list[Notice] = await search_purchases(db,
                                                                     FilterNotice(
                                                                         registration_number=protocol.registration_number,
                                                                         list_filter_type_name=[
                                                                             protocol.filter_type_name]))
                except IntegrityError as e:
                    logger.exception(f"Произошла ошибка получения данных поиска заявок: {e}, ")
                    raise

                    # Если находим обновляем
                if len(purchases) > 1:
                    logger.exception(
                        "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s",
                        protocol.registration_number,
                    )
                    registration_numbers_dict_per_day[protocol.filter_type_name][protocol.region_number].skipped.append(
                        protocol.registration_number
                    )
                elif len(purchases) == 0:
                    try:
                        purchase: NoticeDatabase = await put_purchase(db, protocol)
                    except IntegrityError as e:
                        logger.exception(f"Произошла ошибка создания заявки: {e} ")
                        raise

                    logger.info(
                        "Pipeline: создана новая закупка через API | reg=%s | guid=%s",
                        protocol.registration_number,
                        protocol.guid,
                    )

                    registration_numbers_dict_per_day[protocol.filter_type_name][protocol.region_number].created.append(
                        protocol.registration_number
                    )
                elif len(purchases) == 1:
                    try:
                        purchase_status: Literal["not found", "updated"] = await update_purchase(db, purchases[0].guid, UpdateNotice(result_info=protocol.result_info,
                                                                                                                                     documents_list=protocol.documents_list,
                                                                                                                                     publication_datetime=protocol.publication_datetime))
                    except IntegrityError as e:
                        logger.exception(f"Произошла ошибка создания заявки: {e} ")
                        raise

                    if purchase_status == "updated":
                        logger.info(
                            "Pipeline: обновлена закупка через API | reg=%s | guid=%s",
                            protocol.registration_number,
                            protocol.guid,
                        )

                        registration_numbers_dict_per_day[protocol.filter_type_name][
                            protocol.region_number].updated.append(
                            protocol.registration_number
                        )
                    else:
                        logger.exception(
                            "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s",
                            protocol.registration_number,
                            protocol.guid,
                        )

                        registration_numbers_dict_per_day[protocol.filter_type_name][
                            protocol.region_number].skipped.append(
                            protocol.registration_number
                        )


        except Exception as e:
            logger.exception(
                "Pipeline: ошибка update_purchase для протокола | reg=%s, ошибка=%s",
                protocol.registration_number, e
            )
            filter_type_name = protocol.filter_type_name
            region_number = protocol.region_number
            registration_number = protocol.registration_number
            if filter_type_name and region_number and registration_number:
                registration_numbers_dict_per_day[filter_type_name][region_number][
                    "skipped"
                ].append(registration_number)
            else:
                logger.error(
                    "Pipeline: не удалось учесть запись как skipped — нет ключей | purchase=%s",
                    protocol,
                )