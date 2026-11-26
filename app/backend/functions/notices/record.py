from app.backend.database.models import NoticeDatabase
from app.backend.database.settings import db_session
from app.settings import logger
from app.schemas.purchase import Notice, FilterNotice, UpdateNotice
from app.backend.database.crud.purchase import search_purchases, put_purchase, update_purchase, upsert_notice
from sqlalchemy.exc import IntegrityError
from typing import Literal
import asyncio


async def save_purchase_record(purchase: Notice, registration_numbers_dict_per_day: dict,
                               record_semaphore: asyncio.Semaphore) -> None:
    async with record_semaphore:
        try:
            async with db_session() as db:
                try:
                    purchase_status: Literal["created", "updated"] = await upsert_notice(db, purchase)
                except IntegrityError as e:
                    logger.warning(
                        f"Pipeline: ошибка сохранения закупки | reg={
                            purchase.registration_number} | guid={
                            purchase.guid}: {e}"
                    )
                    registration_numbers_dict_per_day[purchase.filter_type_name][purchase.region_number].skipped.append(
                        purchase.registration_number
                    )

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
                elif purchase_status == "created":
                    logger.info(
                        "Pipeline: создана новая закупка через API | reg=%s | guid=%s",
                        purchase.registration_number,
                        purchase.guid,
                    )

                    registration_numbers_dict_per_day[purchase.filter_type_name][purchase.region_number].created.append(
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


async def save_protocol_record(protocol: Notice, registration_numbers_dict_per_day: dict,
                               record_semaphore: asyncio.Semaphore) -> None:
    async with record_semaphore:
        try:
            async with db_session() as db:
                try:
                    purchase_status: Literal["created", "updated"] = await upsert_notice(db, protocol)
                except IntegrityError as e:
                    logger.warning(
                        f"Pipeline: ошибка сохранения закупки | reg={
                            protocol.registration_number} | guid={
                            protocol.guid, }: {e}"
                    )
                    registration_numbers_dict_per_day[protocol.filter_type_name][protocol.region_number].skipped.append(
                        protocol.registration_number
                    )

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
                elif purchase_status == "created":
                    logger.info(
                        "Pipeline: создана новая закупка через API | reg=%s | guid=%s",
                        protocol.registration_number,
                        protocol.guid,
                    )

                    registration_numbers_dict_per_day[protocol.filter_type_name][protocol.region_number].created.append(
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
                registration_numbers_dict_per_day[filter_type_name][region_number].skipped.append(registration_number)
            else:
                logger.error(
                    "Pipeline: не удалось учесть запись как skipped — нет ключей | purchase=%s",
                    protocol,
                )
