from sqlalchemy import Column, String, DateTime, Numeric, Integer, UniqueConstraint, Index
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

    submission_start_datetime = Column(DateTime, nullable=True)
    submission_close_datetime = Column(DateTime, nullable=True)

    customer = Column(JSONB, nullable=False, default=dict)
    contact = Column(JSONB, nullable=False, default=dict)
    apply_request = Column(JSONB, nullable=False, default=dict)
    result_info = Column(JSONB, nullable=False, default=dict)
    documents_list = Column(ARRAY(String), nullable=False, default=list)
    lots = Column(ARRAY(JSONB), nullable=False, default=list)

    filter_type_name = Column(String(1000), nullable=False)
    region_number = Column(String(100), nullable=False)

    source_file = Column(String(255), nullable=True)

class NewsLetter(Base):
    __tablename__ = "newsletter"

    id = Column(Integer, primary_key=True)
    email = Column(String(64), nullable=False, index=True)

    filter_type_name = Column(String(1000), nullable=False)
    district_name = Column(String(1000), nullable=False)

    __table_args__ = (

        UniqueConstraint(

            "email",

            "filter_type_name",

            "district_name",

            name="uq_newsletter_email_filter_type_district",

        ),

        Index(

            "ix_newsletter_filter_district",

            "filter_type_name",

            "district_name",

        ),

    )