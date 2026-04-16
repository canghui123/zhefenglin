from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date


class Asset(BaseModel):
    row_number: int
    car_description: str = Field(..., description="车型描述，如'2019 丰田凯美瑞 2.0G 豪华版'")
    vin: Optional[str] = Field(None, description="VIN码（车架号），17位")
    first_registration: Optional[date] = Field(None, description="首次登记日期")
    mileage: Optional[float] = Field(None, description="表显里程(万公里)")
    gps_online: Optional[bool] = Field(None, description="GPS是否在线")
    insurance_lapsed: Optional[bool] = Field(None, description="是否脱保")
    ownership_transferred: Optional[bool] = Field(None, description="是否被过户")
    loan_principal: Optional[float] = Field(None, description="债权本金(元)")
    buyout_price: Optional[float] = Field(None, description="买断价(元)")


class AssetParseError(BaseModel):
    row_number: int
    field: str
    message: str


class AssetParseResult(BaseModel):
    assets: list[Asset]
    errors: list[AssetParseError]
    total_rows: int
    success_rows: int
    column_mapping: dict[str, str] = Field(default_factory=dict)  # {Excel列名: 系统字段名}
    unmapped_columns: list[str] = Field(default_factory=list)  # 未识别的列名
    # 推荐的买断价策略：direct(已有买断价) / discount(有本金需折扣) / ai_suggest(需AI建议)
    suggested_strategy: str = "direct"
    strategy_message: str = ""


class PricingParameters(BaseModel):
    towing_cost: float = Field(default=1500, description="预期单台拖车费(元)")
    daily_parking: float = Field(default=30, description="预期单台日停车费(元/天)")
    capital_rate: float = Field(default=8.0, description="资金成本年化率(%)")
    disposal_period: int = Field(default=45, description="预期处置周期(天)")
    tow_success_rate_gps_online: float = Field(default=0.85, description="GPS在线拖回成功率")
    tow_success_rate_gps_offline: float = Field(default=0.40, description="GPS离线拖回成功率")
    # 车况：excellent(优秀) / good(良好) / normal(一般)，默认good
    vehicle_condition: Literal["excellent", "good", "normal"] = Field(
        default="good",
        description="车况评估：excellent/good/normal",
    )
    # 买断价策略：direct(Excel已有) / discount(本金×折扣) / ai_suggest(AI建议)
    buyout_strategy: Literal["direct", "discount", "ai_suggest"] = Field(
        default="direct",
        description="买断价计算策略",
    )
    # 本金折扣率（buyout_strategy=discount 时使用），例如 0.3 表示按本金30%买断
    discount_rate: Optional[float] = Field(
        default=None,
        gt=0,
        le=1,
        description="本金折扣率(0-1)",
    )
    advanced_condition_pricing: bool = Field(
        default=False,
        description="是否请求高级车况定价",
    )
    manual_selected: bool = Field(
        default=False,
        description="是否人工勾选高成本估值",
    )
    approval_mode: bool = Field(
        default=False,
        description="是否走审批报告模式",
    )
    strict_policy: bool = Field(
        default=False,
        description="被商业规则拦截时是否直接报错",
    )
    single_task_budget: Optional[float] = Field(
        default=None,
        description="单次任务预算上限",
    )

    @model_validator(mode="after")
    def validate_strategy_fields(self):
        if self.buyout_strategy == "discount" and self.discount_rate is None:
            raise ValueError("discount 策略必须提供 discount_rate")
        return self


class AssetPricingResult(BaseModel):
    row_number: int
    car_description: str
    buyout_price: float
    che300_valuation: Optional[float] = None
    depreciation_rate: Optional[float] = None
    towing_cost: float = 0
    parking_cost: float = 0
    capital_cost: float = 0
    total_cost: float = 0
    expected_revenue: float = 0
    net_profit: float = 0
    profit_margin: float = 0
    risk_flags: list[str] = Field(default_factory=list)


class PackageSummary(BaseModel):
    total_assets: int
    total_buyout_cost: float = 0
    total_expected_revenue: float = 0
    total_net_profit: float = 0
    overall_roi: float = 0
    recommended_max_discount: float = 0
    high_risk_count: int = 0
    risk_alerts: list[str] = Field(default_factory=list)


class PackageCalculationResult(BaseModel):
    package_id: int
    summary: PackageSummary
    assets: list[AssetPricingResult]
