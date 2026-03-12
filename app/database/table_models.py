from sqlalchemy import (
    Column, String,
    DateTime, Float
)

from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from datetime import datetime
from .connection_to_database import Base


class Purchase(Base):
    __tablename__ = "purchases"
    # --- Закупка ---
    guid = Column(String(64), unique=True, primary_key=True, nullable=False, index=True)
    registration_number = Column(String(50), index=True)
    name = Column(String(2000), nullable=False)
    initial_sum = Column(Float(50))
    publication_datetime = Column(DateTime)
    submission_close_datetime = Column(DateTime)

    # --- Заказчик ---
    customer = Column(JSONB, nullable=False)

    # --- Контакт ---
    contact = Column(JSONB, nullable=False)

    # --- Заявка ---
    apply_request = Column(JSONB, nullable=False)

    # --- Лот ---
    lots = Column(ARRAY(JSONB), nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)

    source_file = Column(String(255))