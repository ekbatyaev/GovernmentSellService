from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .table_models import Purchase
from .connection_to_database import init_db, get_db
import json
import os

#Инициализация переменных окружения
load_dotenv()
SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")

# Создаем приложение
app = FastAPI(
    title="Zakupki Database API",
    description="API для управления госзакупками",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic модели

class PutPurchaseModel(BaseModel):
    token: str
    guid: str
    registration_number: str
    name: str
    source_file: str
    initial_sum: float
    created_at: datetime
    publication_datetime: datetime
    submission_close_datetime: datetime
    customer_json: json
    contact_json: json
    apply_request_json: json
    lot: json

class DeletePurchaseModel(BaseModel):
    token: str
    guid: str

class GetPurchaseModel(BaseModel):
    token: str
    guid: str

class GetPurchaseResponseModel(BaseModel):
    guid: str
    registration_number: str
    name: str
    source_file: str
    initial_sum: float
    created_at: datetime
    publication_datetime: datetime
    submission_close_datetime: datetime
    customer_json: json
    contact_json: json
    apply_request_json: json
    lot: json

class GetAllPurchasesModel(BaseModel):
    token: str
    name: Optional[str] = None
    initial_sum_from: Optional[float] = None
    initial_sum_to: Optional[float] = None
    publication_datetime_from: Optional[datetime ]= None
    publication_datetime_to: Optional[datetime] = None
    submission_close_datetime_from: Optional[datetime] = None
    submission_close_datetime_to: Optional[datetime] = None
    source_file: Optional[str] = None

class UpdatePurchaseModel(BaseModel):
    token: str
    guid: str
    registration_number: Optional[str]
    name: Optional[str]
    source_file: Optional[str]
    initial_sum: Optional[float]
    created_at: Optional[datetime]
    publication_datetime: Optional[datetime]
    submission_close_datetime: Optional[datetime]
    customer_json: Optional[json]
    contact_json: Optional[json]
    apply_request_json: Optional[json]
    lot: Optional[json]

class UpdatePurchaseResponseModel(BaseModel):
    guid: str
    registration_number: str
    name: str
    source_file: str
    initial_sum: float
    created_at: datetime
    publication_datetime: datetime
    submission_close_datetime: datetime
    customer_json: json
    contact_json: json
    apply_request_json: json
    lot: json

# Зависимости
def get_proceed_token(user_token):
    """
    Проверка токена авторизации
    """
    if SYSTEM_TOKEN == user_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return True

# Инициализация базы данных при запуске
@app.on_event("startup")
def startup_event():
    """Инициализация при запуске"""
    init_db()
    print("Database initialized")


# Ручки для пользователей

@app.post("/put_purchase", status_code=status.HTTP_201_PUT)
def put_purchase(
        purchase_data: PutPurchaseModel,
        db: Session = Depends(get_db)
) -> bool:

    # Проверка токена
    get_proceed_token(purchase_data.token)

    """
    Создание новой заявки на закупку
    """

    new_purchase = Purchase(
        guid = purchase_data.guid,
        registration_number = purchase_data.registration_number,
        name = purchase_data.name,
        initial_sum = purchase_data.initial_sum,
        publication_datetime = purchase_data.publication_datetime,
        submission_close_datetime = purchase_data.submission_close_datetime,
        customer_json = purchase_data.customer_json,
        contact_json = purchase_data.contact_json,
        apply_request_json = purchase_data.apply_request_json,
        lot = purchase_data.lot,
        created_at = purchase_data.created_at,
        source_file = purchase_data.source_file
    )

    try:
        db.add(new_purchase)
        db.commit()
        db.refresh(new_purchase)

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to put purchase: {str(e)}"
        )

    return True


@app.delete("/delete_purchase")
def delete_purchase(
        purchase_data: DeletePurchaseModel,
        db: Session = Depends(get_db)

) -> bool:

    # Проверка токена
    get_proceed_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    try:
        db.delete(purchase)
        db.commit()

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete purchase: {str(e)}"
        )

    return True


@app.delete("/get_purchase", response_model = GetPurchaseResponseModel)
def get_purchase(
        purchase_data: GetPurchaseModel,
        db: Session = Depends(get_db)

):
    # Проверка токена
    get_proceed_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )

    response_dict = \
        {
            "guid": purchase.guid,
            "registration_number": purchase.registration_number,
            "name": purchase.name,
            "initial_sum": purchase.initial_sum,
            "publication_datetime": purchase.publication_datetime,
            "submission_close_datetime":  purchase.submission_close_datetime,
            "customer_json": purchase.customer_json,
            "contact_json": purchase.contact_json,
            "apply_request_json": purchase.apply_request_json,
            "lot": purchase.lot,
            "created_at": purchase.created_at,
            "source_file": purchase.source_file
    }

    return GetPurchaseResponseModel(**response_dict)

@app.put("/update_purchase", response_model=UpdatePurchaseModel)
def update_purchase(
        purchase_data: UpdatePurchaseModel,
        db: Session = Depends(get_db)
):
    """
    Обновление закупки
    """

    # Проверка токена
    get_proceed_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )

    # Обновляем только переданные поля
    update_data = purchase_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(purchase, field, value)


    try:
        db.commit()
        db.refresh(purchase)

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update purchase: {str(e)}"
        )

    response_dict = \
        {
            "guid": purchase.guid,
            "registration_number": purchase.registration_number,
            "name": purchase.name,
            "initial_sum": purchase.initial_sum,
            "publication_datetime": purchase.publication_datetime,
            "submission_close_datetime": purchase.submission_close_datetime,
            "customer_json": purchase.customer_json,
            "contact_json": purchase.contact_json,
            "apply_request_json": purchase.apply_request_json,
            "lot": purchase.lot,
            "created_at": purchase.created_at,
            "source_file": purchase.source_file
        }

    return UpdatePurchaseResponseModel(**response_dict)

@app.post("/get_all_purchases", response_model=List[GetPurchaseResponseModel])
def get_all_purchases(
        purchase_data: GetAllPurchasesModel,
        db: Session = Depends(get_db)
):
    """
    Получение списка всех закупок с фильтрацией
    """

    get_proceed_token(purchase_data.token)

    query = select(Purchase)

    # --- Поиск по названию ---
    if purchase_data.name:
        query = query.where(
            Purchase.name.ilike(f"%{purchase_data.name}%")
        )

    # --- Фильтр по сумме ---
    if purchase_data.initial_sum_from is not None:
        query = query.where(
            Purchase.initial_sum >= purchase_data.initial_sum_from
        )

    if purchase_data.initial_sum_to is not None:
        query = query.where(
            Purchase.initial_sum <= purchase_data.initial_sum_to
        )

    # --- Фильтр по дате публикации ---
    pub_from = purchase_data.publication_datetime_from
    pub_to = purchase_data.publication_datetime_to

    if pub_from and pub_to:
        if pub_from.date() == pub_to.date():
            start = datetime.combine(pub_from.date(), datetime.min.time())
            end = start + timedelta(days=1)

            query = query.where(
                Purchase.publication_datetime >= start,
                Purchase.publication_datetime < end
            )
        else:
            query = query.where(
                Purchase.publication_datetime >= pub_from,
                Purchase.publication_datetime <= pub_to
            )
    elif pub_from:
        query = query.where(
            Purchase.publication_datetime >= pub_from
        )
    elif pub_to:
        query = query.where(
            Purchase.publication_datetime <= pub_to
        )

    # --- Фильтр по дате окончания подачи ---
    sub_from = purchase_data.submission_close_datetime_from
    sub_to = purchase_data.submission_close_datetime_to

    if sub_from and sub_to:
        if sub_from.date() == sub_to.date():
            start = datetime.combine(sub_from.date(), datetime.min.time())
            end = start + timedelta(days=1)

            query = query.where(
                Purchase.submission_close_datetime >= start,
                Purchase.submission_close_datetime < end
            )
        else:
            query = query.where(
                Purchase.submission_close_datetime >= sub_from,
                Purchase.submission_close_datetime <= sub_to
            )
    elif sub_from:
        query = query.where(
            Purchase.submission_close_datetime >= sub_from
        )
    elif sub_to:
        query = query.where(
            Purchase.submission_close_datetime <= sub_to
        )

    # --- Поиск по source_file ---
    if purchase_data.source_file:
        query = query.where(
            Purchase.source_file.ilike(f"%{purchase_data.source_file}%")
        )

    # --- Сортировка ---
    query = query.order_by(Purchase.created_at.desc())

    purchases = db.scalars(query).all()

    # --- Формирование ответа ---
    result = []

    for purchase in purchases:
        purchases_dict = {
            "guid": purchase.guid,
            "registration_number": purchase.registration_number,
            "name": purchase.name,
            "initial_sum": purchase.initial_sum,
            "publication_datetime": purchase.publication_datetime,
            "submission_close_datetime": purchase.submission_close_datetime,
            "customer_json": purchase.customer_json,
            "contact_json": purchase.contact_json,
            "apply_request_json": purchase.apply_request_json,
            "lot": purchase.lot,
            "created_at": purchase.created_at,
            "source_file": purchase.source_file
        }

        result.append(purchases_dict)

    return result


# Статистика

@app.get("/stats")
def get_statistics(db: Session = Depends(get_db)):
    """
    Получение общей статистики
    """
    from sqlalchemy import func

    # Количество тем
    purchases_count = db.scalar(select(func.count()).select_from(Purchase))

    return {
        "purchases_count": purchases_count,
        "timestamp": datetime.utcnow().isoformat()
    }


# Эндпоинт для проверки здоровья

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Проверка здоровья приложения и базы данных
    """
    try:
        # Проверяем соединение с базой данных
        db.execute(select(1))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )