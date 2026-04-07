from pydantic import BaseModel
from typing import Optional


class ValuationRequest(BaseModel):
    model_id: str
    registration_date: str
    mileage: Optional[float] = None
    city_code: Optional[str] = None


class ValuationResult(BaseModel):
    model_id: str
    model_name: str = ""
    excellent_price: Optional[float] = None
    good_price: Optional[float] = None
    medium_price: Optional[float] = None
    fair_price: Optional[float] = None
    dealer_buy_price: Optional[float] = None
    dealer_sell_price: Optional[float] = None
    is_mock: bool = False


class CarModel(BaseModel):
    che300_model_id: str
    brand: str
    series: str
    model_name: str
    year: Optional[int] = None
    displacement: Optional[str] = None
    fuel_type: Optional[str] = None
    guide_price: Optional[float] = None


class ModelMatchResult(BaseModel):
    model: CarModel
    confidence: float
    match_detail: str
