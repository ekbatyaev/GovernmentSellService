from datetime import datetime
from decimal import Decimal
from sqlalchemy import Enum, String, DateTime, Numeric, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.backend.database.settings import Base
from typing import Literal



class NoticeDatabase(Base):
    __tablename__ = "purchases"

    guid: Mapped[str] = mapped_column(String(64), primary_key=True)

    registration_number: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(2000))

    initial_sum: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    publication_datetime: Mapped[datetime] = mapped_column(DateTime)
    submission_start_datetime: Mapped[datetime] = mapped_column(DateTime)
    submission_close_datetime: Mapped[datetime] = mapped_column(DateTime)

    customer: Mapped[dict] = mapped_column(JSONB, default=dict)
    contact: Mapped[dict] = mapped_column(JSONB, default=dict)
    apply_request: Mapped[dict] = mapped_column(JSONB, default=dict)
    result_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    documents_list: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    lots: Mapped[list[dict]] = mapped_column(ARRAY(JSONB), default=list)

    filter_type_name: Mapped[str] = mapped_column(String(1000))
    region_number: Mapped[str] = mapped_column(String(100))

    source_file: Mapped[str] = mapped_column(String(255))


class NewsLetterDatabase(Base):
    __tablename__ = "newsletter"

    guid: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(64), index=True)

    filter_type_name: Mapped[str] = mapped_column(String(1000))
    district_name: Mapped[str] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint(
            "newsletters", "filter_type_name", "district_name",
            name="uq_newsletter_email_filter_type_district",
        ),
        Index("ix_newsletter_filter_district", "filter_type_name", "district_name"),
    )


class AuthCodeDatabase(Base):
    __tablename__ = "auth_codes"

    guid: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255))

    code: Mapped[int]

    created_at: Mapped[datetime]
    last_checked_at: Mapped[datetime]


class UserDatabase(Base):
    __tablename__ = "users"

    guid: Mapped[str] = mapped_column(String(64), primary_key=True)

    email: Mapped[str] = mapped_column(String(255),
                                       unique=True)
    password: Mapped[str] = mapped_column(String(255))

    role: Mapped[Literal["admin", "user", "guest"]] = mapped_column(
        Enum("admin", "user", "guest", name="user_role", native_enum=False, create_constraint=True),
        default="guest",
        server_default="guest",
    )

    created_at: Mapped[datetime]