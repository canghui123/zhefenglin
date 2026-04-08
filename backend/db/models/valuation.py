from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from db.base import Base


class ValuationCache(Base):
    __tablename__ = "valuation_cache"
    __table_args__ = (
        UniqueConstraint(
            "che300_model_id",
            "registration_date",
            "query_date",
            "city_code",
            name="uq_valuation_cache_lookup",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    che300_model_id: Mapped[str] = mapped_column(String, nullable=False)
    registration_date: Mapped[str] = mapped_column(String, nullable=False)
    query_date: Mapped[str] = mapped_column(String, nullable=False)
    city_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    excellent_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    good_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    medium_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fair_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dealer_buy_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dealer_sell_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class DepreciationCache(Base):
    __tablename__ = "depreciation_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    valuation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prediction_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
