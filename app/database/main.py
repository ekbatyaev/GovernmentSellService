from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
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

@app.get("/get_all_purchases", response_model=List[GetPurchaseResponseModel])
def get_all_purchases(
        purchase_data: GetAllPurchasesModel,
        db: Session = Depends(get_db)
):

    """
    Получение списка всех закупок с пагинацией и поиском
    """

    # Проверка токена
    get_proceed_token(purchase_data.token)
    query = select(Purchase)

    # Сортировка по дате создания
    query = query.order_by(Purchase.created_at.desc())

    purchases = db.scalars(query).all()

    # Формируем ответ с информацией о создателях
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

# TO DO: Поиск по формулировкам работ, обновление информации в топике, поиск по оплате

@app.get("/users/{user_id}", response_model=UserInfoResponse)
def get_user_by_id(
        user_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Получение информации о пользователе по ID
    Только для аутентифицированных пользователей
    """
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserInfoResponse(
        id=user.id,
        username=user.username,
        achievements_count=user.achievements_count,
        last_used=user.last_used
    )

# Ручки для тем

@app.post("/get_final_theme_test", response_model=TopicFinalTestResponse, status_code=status.HTTP_201_CREATED)
def get_final_test(
        topic_data: TopicFinalTest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    current_user.last_used = datetime.utcnow()
    db.commit()
    db.refresh(current_user)

    try:
        model_response = final_theme_test(title = topic_data.title,
                         description = topic_data.description)

    except Exception as e:
        print("Ошибка: ", e)
        return {"model_response": True}

    return TopicFinalTestResponse(**model_response)

@app.post("/theme_learning", response_model=UserThemeLearningResponse, status_code=status.HTTP_201_CREATED)
def get_theme_learning_conversation(
        topic_data: UserThemeLearning,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):

    current_user.last_used = datetime.utcnow()
    db.commit()
    db.refresh(current_user)

    try:
        model_response = learning_with_llm_request(user_request = topic_data.user_request, theme_name = topic_data.theme_name,
                                  additional_info = topic_data.additional_info, old_context = topic_data.old_context)
    except Exception as e:
        print("Ошибка: ", e)
        return {"model_response": True}

    return UserThemeLearningResponse(**model_response)


@app.get("/topics", response_model=List[TopicResponse])
def get_all_topics(
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Получение списка всех тем с пагинацией и поиском
    """

    query = select(Topic)

    # Добавляем поиск по названию или описанию
    if search:
        query = query.where(
            or_(
                Topic.title.ilike(f"%{search}%"),
                Topic.description.ilike(f"%{search}%")
            )
        )

    # Сортировка по дате создания
    query = query.order_by(Topic.created_at.desc())

    # Применяем пагинацию
    query = query.offset(skip).limit(limit)

    topics = db.scalars(query).all()

    # Формируем ответ с информацией о создателях
    result = []
    for topic in topics:
        topic_dict = {
            "id": topic.id,
            "title": topic.title,
            "description": topic.description,
            "data_json": topic.data_json,
            "created_at": topic.created_at,
            "creator_id": topic.creator_id,
            "creator_username": None
        }

        if topic.creator:
            topic_dict["creator_username"] = topic.creator.username

        result.append(topic_dict)

    return result



@app.put("/topics/update_{topic_id}", response_model=TopicResponse)
def update_topic(
        topic_id: int,
        topic_data: TopicUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Обновление темы (только создатель может обновлять)
    """
    topic = db.get(Topic, topic_id)

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )

    # Проверяем права доступа
    if topic.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own topics"
        )

    # Обновляем только переданные поля
    update_data = topic_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(topic, field, value)

    db.commit()
    db.refresh(topic)

    # Обновляем словарь для ответа
    topic_dict = {
        "id": topic.id,
        "title": topic.title,
        "description": topic.description,
        "data_json": topic.data_json,
        "created_at": topic.created_at,
        "creator_id": topic.creator_id,
        "creator_username": current_user.username
    }

    return topic_dict



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