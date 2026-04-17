from pydantic import BaseModel, Field
from typing import Optional


class ValuationRequest(BaseModel):
    model_id: str
    registration_date: str
    mileage: Optional[float] = None
    city_code: Optional[str] = None
    advanced_condition_pricing: bool = Field(default=False, description="是否请求高级车况定价")
    manual_selected: bool = Field(default=False, description="是否人工勾选高成本估值")
    approval_mode: bool = Field(default=False, description="是否走审批报告模式")
    approval_request_id: Optional[int] = Field(default=None, description="已通过审批的审批单ID")
    strict_policy: bool = Field(default=False, description="被商业规则拦截时是否直接报错")
    single_task_budget: Optional[float] = Field(default=None, description="单次任务预算上限")


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
