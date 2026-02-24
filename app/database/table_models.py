from sqlalchemy import (
    Column, Integer, String,
    DateTime, CheckConstraint, Float, JSONB
)
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
    customer_json = Column(JSONB, nullable=False)

    # --- Контакт ---
    contact_json = Column(JSONB, nullable=False)

    # --- Заявка ---
    apply_request_json = Column(JSONB, nullable=False)

    # --- Лот (он один) ---
    lot = Column(JSONB, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    source_file = Column(String(255))

    __table_args__ = (
        CheckConstraint("length(name) > 0", name="purchase_name_not_empty")
    )