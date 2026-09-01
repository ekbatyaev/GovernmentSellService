from random import randint
from fastapi import Depends, status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.backend.db.table_models import Purchase, NewsLetter
from app.backend.functions import delete_expired, set_auth_code, pop_auth_code, verify_token
from app.backend.models import SuccessResponseModel, GetAllPurchasesModel, UpdatePurchaseModel, AdminProcessDay, \
    AdminBackfillModel, AdminProcessPeriodOfTime, DeleteExpiredModel, PutNewsLetterModel, PutPurchaseModel, \
    GetNewsLetterModel, GetAllNewsLettersModel, PurchaseResponseModel, DeletePurchaseModel, GetPurchaseModel, \
    DeleteNewsLetterModel, SendAuthCode, VerifyCode
from app.main import app
from app.settings import settings, logger, MOSCOW_TZ
from app.backend.email.functions import send_email
from app.backend.db.settings import get_db
from app.backend.scheduler import process_day, run_backfill

last_process_day_at, last_backfill_at = None, None

@app.get(f"{settings.app_base}/config", response_model=SuccessResponseModel)
async def get_config():
    return SuccessResponseModel(
        status="success",
        message="Config",
        data={
            "system_token": settings.system_token,
        },
    )


@app.get(f"{settings.app_base}/")
async def root():
    # Вариант A: файл лежит в /app/static/index.html
    return FileResponse("static/index.html")

@app.post(f"{settings.app_base}/put_purchase", response_model=SuccessResponseModel, status_code=status.HTTP_201_CREATED)
async def put_purchase(purchase_data: PutPurchaseModel, db: AsyncSession = Depends(get_db)):
    await verify_token(purchase_data.token)

    query = select(Purchase).where(Purchase.registration_number == purchase_data.registration_number)
    query = query.where(Purchase.filter_type_name == purchase_data.filter_type_name)

    existing_purchase = await db.scalar(query)

    if existing_purchase:
        existing_purchase.registration_number = purchase_data.registration_number
        existing_purchase.name = purchase_data.name
        existing_purchase.source_file = purchase_data.source_file
        existing_purchase.initial_sum = purchase_data.initial_sum
        existing_purchase.publication_datetime = purchase_data.publication_datetime
        existing_purchase.submission_start_datetime = purchase_data.submission_start_datetime
        existing_purchase.submission_close_datetime = purchase_data.submission_close_datetime
        existing_purchase.customer = purchase_data.customer or {}
        existing_purchase.contact = purchase_data.contact or {}
        existing_purchase.apply_request = purchase_data.apply_request or {}
        existing_purchase.result_info = purchase_data.result_info or {}
        existing_purchase.documents_list = purchase_data.documents_list or []
        existing_purchase.lots = purchase_data.lots or []

        existing_purchase.filter_type_name = purchase_data.filter_type_name
        existing_purchase.region_number = purchase_data.region_number

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Failed to update purchase")

        await db.refresh(existing_purchase)

        return SuccessResponseModel(
            status="success",
            message="Purchase updated",
            data=PurchaseResponseModel.model_validate(existing_purchase),
        )

    new_purchase = Purchase(
        guid=purchase_data.guid,
        registration_number=purchase_data.registration_number,
        name=purchase_data.name,
        source_file=purchase_data.source_file,
        initial_sum=purchase_data.initial_sum,
        publication_datetime=purchase_data.publication_datetime,
        submission_start_datetime=purchase_data.submission_start_datetime,
        submission_close_datetime=purchase_data.submission_close_datetime,
        customer=purchase_data.customer or {},
        contact=purchase_data.contact or {},
        apply_request=purchase_data.apply_request or {},
        result_info=purchase_data.result_info or {},
        documents_list=purchase_data.documents_list or [],
        lots=purchase_data.lots or [],
        filter_type_name=purchase_data.filter_type_name,
        region_number=purchase_data.region_number
    )

    try:
        db.add(new_purchase)
        await db.commit()
        await db.refresh(new_purchase)
        return SuccessResponseModel(
            status="success",
            message="Purchase created",
            data=PurchaseResponseModel.model_validate(new_purchase)
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create purchase")


@app.post(f"{settings.app_base}/delete_purchase", response_model=SuccessResponseModel)
async def delete_purchase(purchase_data: DeletePurchaseModel, db: AsyncSession = Depends(get_db)):
    await verify_token(purchase_data.token)

    purchase = await db.get(Purchase, purchase_data.guid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    await db.delete(purchase)
    await db.commit()
    return SuccessResponseModel(status="success", message="Deleted", data={"guid": purchase_data.guid})


@app.post(f"{settings.app_base}/get_purchase", response_model=SuccessResponseModel)
async def get_purchase(purchase_data: GetPurchaseModel, db: AsyncSession = Depends(get_db)):
    await verify_token(purchase_data.token)

    query = select(Purchase)

    if purchase_data.registration_number:
        query = query.where(Purchase.registration_number == purchase_data.registration_number.strip())

    # Если есть guid — добавляем условие (если это не первичный ключ, используем .where)
    if purchase_data.guid:
        query = query.where(Purchase.guid == purchase_data.guid.strip())

    # Интегрируем вашу фильтрацию по типу
    if purchase_data.filter_type_name:
        query = query.where(Purchase.filter_type_name == purchase_data.filter_type_name)

    if not purchase_data.guid and not purchase_data.registration_number:
        raise HTTPException(
            status_code=400,
            detail="Не передан ни один ключ поиска: guid или registration_number",
        )

    result = await db.execute(query)
    purchase = result.scalars().first()

    if not purchase:
        return SuccessResponseModel(
            status="success",
            message="Purchase not found",
            data={},
        )

    return SuccessResponseModel(
        status="success",
        message="Ok",
        data=PurchaseResponseModel.model_validate(purchase),
    )


@app.post(f"{settings.app_base}/get_all_purchases", response_model=SuccessResponseModel)
async def get_all_purchases(purchase_data: GetAllPurchasesModel, db: AsyncSession = Depends(get_db)):
    await verify_token(purchase_data.token)
    logger.info("get_all_purchases | %s", purchase_data)
    query = select(Purchase)

    if purchase_data.name:
        query = query.where(Purchase.name.ilike(f"%{purchase_data.name}%"))

    if purchase_data.filter_type_name:
        query = query.where(Purchase.filter_type_name == purchase_data.filter_type_name)

    if purchase_data.filter_type_name == "Тендеры для OEM" and purchase_data.oem_flag:
        query = query.where(Purchase.result_info["Слова маячки в тз"].astext == purchase_data.oem_flag)

    if purchase_data.filter_type_name == "Тендеры для ITM" and purchase_data.itm_option:
        query = query.where(Purchase.result_info["Категория заявки"].astext == purchase_data.itm_option)

    if purchase_data.region_numbers:
        query = query.where(Purchase.region_number.in_(purchase_data.region_numbers))
    elif purchase_data.region_number is not None:
        query = query.where(Purchase.region_number == purchase_data.region_number)

    if purchase_data.initial_sum_from is not None:
        query = query.where(Purchase.initial_sum >= purchase_data.initial_sum_from)
    if purchase_data.initial_sum_to is not None:
        query = query.where(Purchase.initial_sum <= purchase_data.initial_sum_to)

    pub_from = purchase_data.publication_datetime_from
    pub_to = purchase_data.publication_datetime_to
    if pub_from and pub_to:
        if pub_from.date() == pub_to.date():
            start = datetime.combine(pub_from.date(), datetime.min.time())
            end = start + timedelta(days=1)
            query = query.where(Purchase.publication_datetime >= start, Purchase.publication_datetime < end)
        else:
            query = query.where(Purchase.publication_datetime >= pub_from, Purchase.publication_datetime <= pub_to)
    elif pub_from:
        query = query.where(Purchase.publication_datetime >= pub_from)
    elif pub_to:
        query = query.where(Purchase.publication_datetime <= pub_to)

    submission_start_datetime_from = purchase_data.submission_start_datetime_from
    submission_start_datetime_to = purchase_data.submission_start_datetime_to

    if submission_start_datetime_from and submission_start_datetime_to:
        if submission_start_datetime_from.date() == submission_start_datetime_to.date():
            start = datetime.combine(submission_start_datetime_from.date(), datetime.min.time())
            end = start + timedelta(days=1)
            query = query.where(
                Purchase.submission_start_datetime >= start,
                Purchase.submission_start_datetime < end
            )
        else:
            end = datetime.combine(submission_start_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
            query = query.where(
                Purchase.submission_start_datetime >= submission_start_datetime_from,
                Purchase.submission_start_datetime < end
            )

    elif submission_start_datetime_from:
        query = query.where(Purchase.submission_start_datetime >= submission_start_datetime_from)

    elif submission_start_datetime_to:
        end = datetime.combine(submission_start_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
        query = query.where(Purchase.submission_start_datetime < end)

    submission_close_datetime_from = purchase_data.submission_close_datetime_from
    submission_close_datetime_to = purchase_data.submission_close_datetime_to

    if submission_close_datetime_from and submission_close_datetime_to:
        if submission_close_datetime_from.date() == submission_close_datetime_to.date():
            start = datetime.combine(submission_close_datetime_from.date(), datetime.min.time())
            end = start + timedelta(days=1)
            query = query.where(
                Purchase.submission_close_datetime >= start,
                Purchase.submission_close_datetime < end
            )
        else:
            end = datetime.combine(submission_close_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
            query = query.where(
                Purchase.submission_close_datetime >= submission_close_datetime_from,
                Purchase.submission_close_datetime < end
            )

    elif submission_close_datetime_from:
        query = query.where(Purchase.submission_close_datetime >= submission_close_datetime_from)

    elif submission_close_datetime_to:
        end = datetime.combine(submission_close_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
        query = query.where(Purchase.submission_close_datetime < end)

    if purchase_data.source_file:
        query = query.where(Purchase.source_file.ilike(f"%{purchase_data.source_file}%"))

    query = query.order_by(Purchase.publication_datetime.desc().nullslast())

    result = await db.execute(query)
    purchases = result.scalars().all()
    data = [PurchaseResponseModel.model_validate(p) for p in purchases]
    return SuccessResponseModel(status="success", message=f"Found {len(data)} purchases", data=data)


@app.post(f"{settings.app_base}/update_purchase", response_model=SuccessResponseModel)
async def update_purchase(purchase_data: UpdatePurchaseModel, db: AsyncSession = Depends(get_db)):
    await verify_token(purchase_data.token)

    guid = purchase_data.guid.strip() if purchase_data.guid else None
    registration_number = (
        purchase_data.registration_number.strip()
        if purchase_data.registration_number
        else None
    )

    if guid:
        result = await db.execute(select(Purchase).where(Purchase.guid == guid))
        purchase = result.scalars().first()
    elif registration_number:
        result = await db.execute(select(Purchase).where(Purchase.registration_number == registration_number))
        purchase = result.scalars().first()
    else:
        raise HTTPException(
            status_code=400,
            detail="Не передан ни один ключ поиска: guid или registration_number",
        )

    # Если даже при наличии одного из ключей запись не найдена в БД
    if not purchase:
        return SuccessResponseModel(
            status="success",
            message="Purchase not found",
            data={}
        )

    if purchase_data.filter_type_name and purchase.filter_type_name != purchase_data.filter_type_name:
        purchase = None

    if not purchase:
        return SuccessResponseModel(
            status="success",
            message="Purchase not found",
            data={},
        )

    update_data = purchase_data.model_dump(exclude_unset=True, exclude={"token", "guid", "registration_number"})
    for field, value in update_data.items():
        if value is not None:
            setattr(purchase, field, value)

    try:
        await db.commit()
        await db.refresh(purchase)
    except Exception:
        await db.rollback()
        raise

    return SuccessResponseModel(
        status="success",
        message="Updated",
        data=PurchaseResponseModel.model_validate(purchase),
    )


@app.get(f"{settings.app_base}/stats", response_model=SuccessResponseModel)
async def get_statistics(db: AsyncSession = Depends(get_db)):
    global last_backfill_at, last_process_day_at
    purchases_count = await db.scalar(select(func.count()).select_from(Purchase))
    newsletter_count = await db.scalar(select(func.count()).select_from(NewsLetter))
    return SuccessResponseModel(
        status="success",
        message="Statistics",
        data={"purchases_count": purchases_count, "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
              "newsletter_count": newsletter_count, "last_backfill_at": last_backfill_at,
              "last_process_day_at": last_process_day_at})


@app.get(f"{settings.app_base}/health", response_model=SuccessResponseModel)
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return SuccessResponseModel(status="success", message="Healthy")


# ---- Admin endpoints ----

@app.post(f"{settings.app_base}/admin/run_process_day", response_model=SuccessResponseModel)
async def admin_run_process_day(body: AdminProcessDay):
    await verify_token(body.token)
    global last_process_day_at
    date_str = body.date.strftime("%Y-%m-%d")
    last_process_day_at = datetime.now(MOSCOW_TZ).isoformat()
    result = await process_day(date_str, filter_number=body.filter_number)
    # logger.info(result)
    return SuccessResponseModel(status="success", message="Process day finished")


@app.post(f"{settings.app_base}/admin/run_backfill", response_model=SuccessResponseModel)
async def admin_run_backfill(body: AdminBackfillModel):
    await verify_token(body.token)
    global last_backfill_at
    last_backfill_at = datetime.now(MOSCOW_TZ).isoformat()
    result = await run_backfill(days=body.days, filter_number=body.filter_number)
    # logger.info(result)
    return SuccessResponseModel(status="success", message="Backfill finished")


@app.post(f"{settings.app_base}/admin/run_backfill_period_of_time", response_model=SuccessResponseModel)
async def admin_run_process_period_of_type(body: AdminProcessPeriodOfTime):
    await verify_token(body.token)
    global last_process_day_at
    date_from, date_to = body.date_from, body.date_to
    result = []
    last_process_day_at = datetime.now(MOSCOW_TZ).isoformat()
    logger.info(
        "Processing period of time from %s to %s have started",
        date_from.strftime("%Y-%m-%d"),
        date_to.strftime("%Y-%m-%d"),
    )
    # Строго по одному дню — предсказуемая нагрузка на портал закупок и наш
    # API. process_day и так параллелит регионы/архивы внутри себя.
    while date_from < date_to:
        day_result = await process_day(date_from.strftime("%Y-%m-%d"), filter_number=body.filter_number)
        result.append(day_result)
        date_from += timedelta(days=1)
    # logger.info(result)
    return SuccessResponseModel(status="success", message="Processing period of time successfully completed")


@app.get(f"{settings.app_base}/admin/job_status", response_model=SuccessResponseModel)
def admin_job_status():
    # без токена специально: можно закрыть, если хотите
    # get_last_status() не показана мне — оставляю как есть, ничего не
    # awaiт'ится внутри, признаков работы с БД/сетью не вижу.
    return SuccessResponseModel(status="success", message="Ok")


@app.post(f"{settings.app_base}/admin/delete_expired", response_model=SuccessResponseModel)
async def admin_delete_expired(body: DeleteExpiredModel, db: AsyncSession = Depends(get_db)):
    await verify_token(body.token)
    deleted = await delete_expired(db)
    await db.commit()
    return SuccessResponseModel(status="success", message="Expired deleted", data={"deleted": deleted})


@app.post(f"{settings.app_base}/put_newsletter", response_model=SuccessResponseModel, status_code=status.HTTP_201_CREATED)
async def put_newsletter(data: PutNewsLetterModel, db: AsyncSession = Depends(get_db)):
    await verify_token(data.token)

    newsletter = NewsLetter(
        email=data.email,
        filter_type_name=data.filter_type_name,
        district_name=data.district_name,
    )

    try:
        db.add(newsletter)
        await db.commit()
        await db.refresh(newsletter)

        return SuccessResponseModel(
            status="success",
            message="Email added",
            data={
                "email": newsletter.email,
                "filter_type_name": newsletter.filter_type_name,
                "district_name": newsletter.district_name,
            },
        )

    except IntegrityError:
        await db.rollback()

        result = await db.execute(select(NewsLetter).where(NewsLetter.email == data.email))
        existing = result.scalars().first()
        if existing:
            return SuccessResponseModel(
                status="success",
                message="Email already exists",
                data={
                    "email": existing.email,
                    "filter_type_name": existing.filter_type_name,
                    "district_name": existing.district_name,
                },
            )

        raise HTTPException(status_code=400, detail="Failed to add email")


@app.post(f"{settings.app_base}/delete_newsletter", response_model=SuccessResponseModel)
async def delete_newsletter(data: DeleteNewsLetterModel, db: AsyncSession = Depends(get_db)):
    await verify_token(data.token)

    query = select(NewsLetter).where(NewsLetter.email == data.email)

    if data.filter_type_name:
        query = query.where(NewsLetter.filter_type_name == data.filter_type_name)

    result = await db.execute(query)
    newsletters = result.scalars().all()

    if not newsletters:
        raise HTTPException(status_code=404, detail="Email not found")

    if len(newsletters) > 1 and not data.filter_type_name:
        raise HTTPException(
            status_code=400,
            detail="У email несколько подписок. Передайте filter_type_name для удаления конкретной подписки.",
        )

    for newsletter in newsletters:
        await db.delete(newsletter)

    await db.commit()

    return SuccessResponseModel(
        status="success",
        message="Deleted",
        data={
            "email": data.email,
            "deleted_count": len(newsletters),
        },
    )


@app.post(f"{settings.app_base}/get_newsletter", response_model=SuccessResponseModel)
async def get_newsletter(data: GetNewsLetterModel, db: AsyncSession = Depends(get_db)):
    await verify_token(data.token)

    query = select(NewsLetter).where(NewsLetter.email == data.email)

    if data.filter_type_name:
        query = query.where(NewsLetter.filter_type_name == data.filter_type_name)

    if data.district_name:
        query = query.where(NewsLetter.district_name == data.district_name)

    result = await db.execute(query)
    newsletters = result.scalars().all()

    if not newsletters:
        raise HTTPException(status_code=404, detail="Email not found")

    result_data = [
        {
            "email": n.email,
            "filter_type_name": n.filter_type_name,
            "district_name": n.district_name,
        }
        for n in newsletters
    ]

    return SuccessResponseModel(
        status="success",
        message="Ok",
        data=result_data,
    )


@app.post(f"{settings.app_base}/get_all_newsletters", response_model=SuccessResponseModel)
async def get_all_newsletters(data: GetAllNewsLettersModel, db: AsyncSession = Depends(get_db)):
    await verify_token(data.token)

    query = select(NewsLetter)

    if data.filter_type_name:
        query = query.where(NewsLetter.filter_type_name == data.filter_type_name)

    if data.district_name:
        query = query.where(NewsLetter.district_name == data.district_name)

    result = await db.execute(query)
    newsletters = result.scalars().all()

    result_data = [n.email for n in newsletters]

    return SuccessResponseModel(
        status="success",
        message="Ok",
        data=result_data,
    )


@app.post(f"{settings.app_base}/send_auth_code", response_model=SuccessResponseModel)
async def send_auth_code(data: SendAuthCode, db: AsyncSession = Depends(get_db)):
    await verify_token(data.token)

    code = randint(100000, 999999)

    try:
        subject = "Проверочный код"
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
            <h2 style="color:#2E86C1;">Проверочный код для рассылки Госзакупок</h2>
            <p>Здравствуйте!</p>
            <p>Ваш проверочный код для вашего email:</p>
            <p style="font-size: 1.5em; font-weight: bold; color:#E74C3C;">{code}</p>
            <p>Введите этот код в приложении, чтобы подтвердить или отменить рассылку.</p>
            <hr>
            <p style="font-size: 0.9em; color:#888;">
              Это письмо сформировано автоматически, отвечать на него не нужно.
            </p>
          </body>
        </html>
        """

        await send_email(
            data.email,
            subject,
            html_content
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Email not found")

    try:
        await set_auth_code(db, data.email, code)
    except Exception:
        raise HTTPException(status_code=500, detail="Code not saved")

    return SuccessResponseModel(
        status="success",
        message="Auth code created",
        data={"email": data.email},
    )


@app.post(f"{settings.app_base}/verify_code", response_model=SuccessResponseModel)
async def verify_code(data: VerifyCode, db: AsyncSession = Depends(get_db)):
    await verify_token(data.token)
    try:
        real_code = await pop_auth_code(db, data.email)
    except Exception:
        raise HTTPException(status_code=500, detail="Code data is not available")

    if real_code is None:
        raise HTTPException(status_code=404, detail="Code not found")

    if real_code != data.code:
        raise HTTPException(status_code=400, detail="Invalid code")

    return SuccessResponseModel(
        status="success",
        message="Auth completed",
        data={"auth": True}
    )