from datetime import datetime

from sqlalchemy import Column, String, DateTime, Numeric
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from .connection_to_database import Base


class Purchase(Base):
    __tablename__ = "purchases"

    guid = Column(String(64), unique=True, primary_key=True, nullable=False, index=True)

    registration_number = Column(String(50), index=True, nullable=True)
    name = Column(String(2000), nullable=False)

    # для денег предпочтительнее Numeric, чем Float
    initial_sum = Column(Numeric(18, 2), nullable=True)

    publication_datetime = Column(DateTime, nullable=True)
    submission_close_datetime = Column(DateTime, nullable=True)

    customer = Column(JSONB, nullable=False, default=dict)
    contact = Column(JSONB, nullable=False, default=dict)
    apply_request = Column(JSONB, nullable=False, default=dict)

    lots = Column(ARRAY(JSONB), nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source_file = Column(String(255), nullable=True)