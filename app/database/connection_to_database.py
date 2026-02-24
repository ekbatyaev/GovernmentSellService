from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
import os

# Загружаем переменные окружения
load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")  # "db" для Docker Compose
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# Создаем строку подключения
DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Создаем движок с настройками для переподключения
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_recycle=300,    # Пересоздание соединений каждые 5 минут
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    pass


def init_db():
    """
    Инициализация базы данных - создание таблиц
    """
    Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    """
    Dependency для получения сессии базы данных
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()