from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from db.base import Base


class CarModel(Base):
    __tablename__ = "car_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    che300_model_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    series: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    displacement: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fuel_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    guide_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
