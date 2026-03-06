from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .table_models import Purchase
from fastapi.responses import FileResponse
from .connection_to_database import init_db, get_db
import os
from fastapi.staticfiles import StaticFiles

# Инициализация переменных окружения
load_dotenv()
SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")

# Создаем приложение
app = FastAPI(
    title="Zakupki Database API",
    description="API для управления госзакупками",
    version="1.0.0"
)

# Монтируем index.html
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic модели для запросов
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
    customer_json: Any
    contact_json: Any
    apply_request_json: Any
    lot: Any


class DeletePurchaseModel(BaseModel):
    token: str
    guid: str


class GetPurchaseModel(BaseModel):
    token: str
    guid: str


class GetAllPurchasesModel(BaseModel):
    token: str
    name: Optional[str] = None
    initial_sum_from: Optional[float] = None
    initial_sum_to: Optional[float] = None
    publication_datetime_from: Optional[datetime] = None
    publication_datetime_to: Optional[datetime] = None
    submission_close_datetime_from: Optional[datetime] = None
    submission_close_datetime_to: Optional[datetime] = None
    source_file: Optional[str] = None


class UpdatePurchaseModel(BaseModel):
    token: str
    guid: str
    registration_number: Optional[str] = None
    name: Optional[str] = None
    source_file: Optional[str] = None
    initial_sum: Optional[float] = None
    created_at: Optional[datetime] = None
    publication_datetime: Optional[datetime] = None
    submission_close_datetime: Optional[datetime] = None
    customer_json: Optional[Any] = None
    contact_json: Optional[Any] = None
    apply_request_json: Optional[Any] = None
    lot: Optional[Any] = None


# Pydantic модели для ответов
class PurchaseResponseModel(BaseModel):
    guid: str
    registration_number: str
    name: str
    source_file: str
    initial_sum: float
    created_at: datetime
    publication_datetime: datetime
    submission_close_datetime: datetime
    customer_json: Any
    contact_json: Any
    apply_request_json: Any
    lot: Any

    class Config:
        from_attributes = True


class SuccessResponseModel(BaseModel):
    status: str
    message: str
    data: Optional[Any] = None


class ErrorResponseModel(BaseModel):
    status: str
    message: str
    details: Optional[str] = None


# Зависимости
def verify_token(token: str):
    """
    Проверка токена авторизации
    """
    if SYSTEM_TOKEN != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return True


# Инициализация базы данных при запуске
@app.on_event("startup")
def startup_event():
    """Инициализация при запуске"""
    init_db()
    print("Database initialized")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

# Ручки для пользователей
@app.post("/put_purchase",
          response_model=SuccessResponseModel,
          status_code=status.HTTP_201_CREATED,
          responses={
              400: {"model": ErrorResponseModel},
              401: {"model": ErrorResponseModel}
          })
def put_purchase(
        purchase_data: PutPurchaseModel,
        db: Session = Depends(get_db)
):
    """
    Создание новой заявки на закупку
    """
    # Проверка токена
    verify_token(purchase_data.token)

    new_purchase = Purchase(
        guid=purchase_data.guid,
        registration_number=purchase_data.registration_number,
        name=purchase_data.name,
        initial_sum=purchase_data.initial_sum,
        publication_datetime=purchase_data.publication_datetime,
        submission_close_datetime=purchase_data.submission_close_datetime,
        customer_json=purchase_data.customer_json,
        contact_json=purchase_data.contact_json,
        apply_request_json=purchase_data.apply_request_json,
        lot=purchase_data.lot,
        created_at=purchase_data.created_at,
        source_file=purchase_data.source_file
    )

    try:
        db.add(new_purchase)
        db.commit()
        db.refresh(new_purchase)

        return SuccessResponseModel(
            status="success",
            message="Purchase created successfully",
            data=PurchaseResponseModel.from_orm(new_purchase)
        )

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create purchase: {str(e)}"
        )


@app.delete("/delete_purchase",
            response_model=SuccessResponseModel,
            status_code=status.HTTP_200_OK,
            responses={
                404: {"model": ErrorResponseModel},
                400: {"model": ErrorResponseModel},
                401: {"model": ErrorResponseModel}
            })
def delete_purchase(
        purchase_data: DeletePurchaseModel,
        db: Session = Depends(get_db)
):
    """
    Удаление закупки
    """
    # Проверка токена
    verify_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )

    try:
        db.delete(purchase)
        db.commit()

        return SuccessResponseModel(
            status="success",
            message=f"Purchase with guid {purchase_data.guid} deleted successfully",
            data={"guid": purchase_data.guid}
        )

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete purchase: {str(e)}"
        )


@app.post("/get_purchase",
          response_model=SuccessResponseModel,
          status_code=status.HTTP_200_OK,
          responses={
              404: {"model": ErrorResponseModel},
              401: {"model": ErrorResponseModel}
          })
def get_purchase(
        purchase_data: GetPurchaseModel,
        db: Session = Depends(get_db)
):
    """
    Получение закупки по GUID
    """
    # Проверка токена
    verify_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )

    return SuccessResponseModel(
        status="success",
        message="Purchase retrieved successfully",
        data=PurchaseResponseModel.from_orm(purchase)
    )


@app.put("/update_purchase",
         response_model=SuccessResponseModel,
         status_code=status.HTTP_200_OK,
         responses={
             404: {"model": ErrorResponseModel},
             400: {"model": ErrorResponseModel},
             401: {"model": ErrorResponseModel}
         })
def update_purchase(
        purchase_data: UpdatePurchaseModel,
        db: Session = Depends(get_db)
):
    """
    Обновление закупки
    """
    # Проверка токена
    verify_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )

    # Обновляем только переданные поля (исключая token и guid)
    update_data = purchase_data.dict(exclude_unset=True, exclude={"token", "guid"})
    for field, value in update_data.items():
        if value is not None:  # Обновляем только не-None значения
            setattr(purchase, field, value)

    try:
        db.commit()
        db.refresh(purchase)

        return SuccessResponseModel(
            status="success",
            message="Purchase updated successfully",
            data=PurchaseResponseModel.from_orm(purchase)
        )

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update purchase: {str(e)}"
        )


@app.post("/get_all_purchases",
          response_model=SuccessResponseModel,
          status_code=status.HTTP_200_OK,
          responses={
              401: {"model": ErrorResponseModel}
          })
def get_all_purchases(
        purchase_data: GetAllPurchasesModel,
        db: Session = Depends(get_db)
):
    """
    Получение списка всех закупок с фильтрацией
    """
    verify_token(purchase_data.token)

    query = select(Purchase)

    # Поиск по названию
    if purchase_data.name:
        query = query.where(
            Purchase.name.ilike(f"%{purchase_data.name}%")
        )

    # Фильтр по сумме
    if purchase_data.initial_sum_from is not None:
        query = query.where(
            Purchase.initial_sum >= purchase_data.initial_sum_from
        )

    if purchase_data.initial_sum_to is not None:
        query = query.where(
            Purchase.initial_sum <= purchase_data.initial_sum_to
        )

    # Фильтр по дате публикации
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

    # Фильтр по дате окончания подачи
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

    # Поиск по source_file
    if purchase_data.source_file:
        query = query.where(
            Purchase.source_file.ilike(f"%{purchase_data.source_file}%")
        )

    # Сортировка
    query = query.order_by(Purchase.created_at.desc())

    purchases = db.scalars(query).all()

    # Преобразуем в список response моделей
    purchases_list = [PurchaseResponseModel.from_orm(purchase) for purchase in purchases]

    return SuccessResponseModel(
        status="success",
        message=f"Found {len(purchases_list)} purchases",
        data=purchases_list
    )

@app.get("/dfwerjewbfd")
async def get_config():
    return {
        "system_token": SYSTEM_TOKEN
    }

@app.get("/stats",
         response_model=SuccessResponseModel,
         status_code=status.HTTP_200_OK)
def get_statistics(db: Session = Depends(get_db)):
    """
    Получение общей статистики
    """
    # Количество закупок
    purchases_count = db.scalar(select(func.count()).select_from(Purchase))

    return SuccessResponseModel(
        status="success",
        message="Statistics retrieved successfully",
        data={
            "purchases_count": purchases_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.get("/health",
         response_model=SuccessResponseModel,
         status_code=status.HTTP_200_OK,
         responses={
             503: {"model": ErrorResponseModel}
         })
def health_check(db: Session = Depends(get_db)):
    """
    Проверка здоровья приложения и базы данных
    """
    try:
        # Проверяем соединение с базой данных
        db.execute(select(1))
        return SuccessResponseModel(
            status="success",
            message="Application is healthy",
            data={
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )