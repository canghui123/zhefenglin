from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class Asset(BaseModel):
    row_number: int
    car_description: str = Field(..., description="车型描述，如'2019 丰田凯美瑞 2.0G 豪华版'")
    vin: Optional[str] = Field(None, description="VIN码（车架号），17位")
    first_registration: Optional[date] = Field(None, description="首次登记日期")
    gps_online: Optional[bool] = Field(None, description="GPS是否在线")
    insurance_lapsed: Optional[bool] = Field(None, description="是否脱保")
    ownership_transferred: Optional[bool] = Field(None, description="是否被过户")
    loan_principal: Optional[float] = Field(None, description="债权本金(元)")
    buyout_price: Optional[float] = Field(None, description="买断价(元)")
    province: Optional[str] = Field(None, description="资产所在地省份")
    city: Optional[str] = Field(None, description="资产所在地城市")
    region_code: Optional[str] = Field(None, description="区域配置编码")


class AssetParseError(BaseModel):
    row_number: int
    field: str
    message: str


class AssetParseResult(BaseModel):
    assets: list[Asset]
    errors: list[AssetParseError]
    total_rows: int
    success_rows: int


class PricingParameters(BaseModel):
    towing_cost: float = Field(default=1500, description="预期单台拖车费(元)")
    daily_parking: float = Field(default=30, description="预期单台日停车费(元/天)")
    capital_rate: float = Field(default=8.0, description="资金成本年化率(%)")
    disposal_period: int = Field(default=45, description="预期处置周期(天)")
    tow_success_rate_gps_online: float = Field(default=0.85, description="GPS在线拖回成功率")
    tow_success_rate_gps_offline: float = Field(default=0.40, description="GPS离线拖回成功率")


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
    province: Optional[str] = None
    city: Optional[str] = None
    region_code: Optional[str] = None
    risk_flags: list[str] = []


class PackageSummary(BaseModel):
    total_assets: int
    total_buyout_cost: float = 0
    total_expected_revenue: float = 0
    total_net_profit: float = 0
    overall_roi: float = 0
    recommended_max_discount: float = 0
    high_risk_count: int = 0
    risk_alerts: list[str] = []


class PackageCalculationResult(BaseModel):
    package_id: int
    summary: PackageSummary
    assets: list[AssetPricingResult]
