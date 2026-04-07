from pydantic import BaseModel, Field
from typing import Optional


class SandboxInput(BaseModel):
    car_description: str = Field(..., description="车辆描述")
    entry_date: str = Field(..., description="入库日期 YYYY-MM-DD")
    overdue_amount: float = Field(..., description="逾期金额(元)")
    che300_value: float = Field(..., description="当前车300估值(元)")

    # 车辆信息（用于差异化贬值）
    vehicle_type: str = Field(default="domestic", description="车辆类型: luxury/japanese/german/domestic/new_energy")
    vehicle_age_years: float = Field(default=3, description="车龄(年)")

    # 成本参数
    daily_parking: float = Field(default=30, description="日停车费(元)")
    recovery_cost: float = Field(default=0, description="收车成本(元)，含拖车/GPS/人工等")
    annual_interest_rate: float = Field(default=24, description="逾期年利率(%)")

    # 竞拍参数
    expected_sale_days: int = Field(default=7, description="预计成交天数")
    commission_rate: float = Field(default=0.02, description="竞拍佣金比例")

    # 常规诉讼律师费
    litigation_lawyer_fee: float = Field(default=5000, description="常规诉讼律师费(固定,元)")
    litigation_has_recovery_fee: bool = Field(default=False, description="常规诉讼是否有回款比例律师费")
    litigation_recovery_fee_rate: float = Field(default=0.05, description="常规诉讼回款比例律师费(%)")

    # 实现担保物权特别程序律师费
    special_lawyer_fee: float = Field(default=3000, description="特别程序律师费(固定,元)")
    special_has_recovery_fee: bool = Field(default=False, description="特别程序是否有回款比例律师费")
    special_recovery_fee_rate: float = Field(default=0.03, description="特别程序回款比例律师费(%)")

    # 分期重组参数
    restructure_monthly_payment: float = Field(default=0, description="重组月还款额(元)")
    restructure_months: int = Field(default=12, description="重组期数(月)")
    restructure_redefault_rate: float = Field(default=0.30, description="重组后再违约率")


# ============ 路径A：等待赎车 ============

class TimePoint(BaseModel):
    days: int
    accumulated_parking: float
    accumulated_interest: float
    depreciated_value: float
    depreciation_amount: float = 0
    total_holding_cost: float = 0
    total_shrinkage: float
    net_position: float


class PathAResult(BaseModel):
    name: str = "继续等待赎车"
    timepoints: list[TimePoint]
    summary: str = ""


# ============ 路径B：常规诉讼 ============

class LegalCostDetail(BaseModel):
    """法律费用明细"""
    court_fee: float = Field(0, description="诉讼费(元)")
    execution_fee: float = Field(0, description="执行费(元)")
    preservation_fee: float = Field(0, description="保全费(元)")
    lawyer_fee_fixed: float = Field(0, description="固定律师费(元)")
    lawyer_fee_recovery: float = Field(0, description="回款比例律师费(元)")
    total_legal_cost: float = Field(0, description="法律费用合计(元)")


class AuctionRound(BaseModel):
    """司法拍卖轮次"""
    round_name: str
    discount_rate: float
    auction_price: float
    success_probability: float = 0


class LitigationScenario(BaseModel):
    label: str
    duration_months: int
    duration_days: int
    legal_cost: LegalCostDetail
    parking_cost: float
    interest_cost: float
    recovery_cost: float = 0
    auction_rounds: list[AuctionRound] = []
    expected_auction_price: float = 0
    total_cost: float
    net_recovery: float


class PathBResult(BaseModel):
    name: str = "常规诉讼"
    legal_cost: LegalCostDetail
    scenarios: list[LitigationScenario]
    summary: str = ""


# ============ 路径C：立即上架竞拍 ============

class PathCResult(BaseModel):
    name: str = "立即上架竞拍"
    expected_sale_days: int
    sale_price: float
    commission: float
    parking_during_sale: float
    recovery_cost: float = 0
    net_recovery: float
    summary: str = ""


# ============ 路径D：实现担保物权特别程序 ============

class PathDResult(BaseModel):
    name: str = "实现担保物权特别程序"
    duration_months: int = 3
    duration_days: int = 90
    legal_cost: LegalCostDetail
    parking_cost: float = 0
    interest_cost: float = 0
    recovery_cost: float = 0
    auction_rounds: list[AuctionRound] = []
    expected_auction_price: float = 0
    total_cost: float = 0
    net_recovery: float = 0
    summary: str = ""


# ============ 路径E：分期重组/和解 ============

class PathEResult(BaseModel):
    name: str = "分期重组/和解"
    monthly_payment: float = 0
    total_months: int = 0
    total_expected_recovery: float = 0
    redefault_rate: float = 0
    risk_adjusted_recovery: float = 0
    holding_cost: float = 0
    net_recovery: float = 0
    summary: str = ""


# ============ 汇总结果 ============

class SandboxResult(BaseModel):
    id: Optional[int] = None
    input: SandboxInput
    path_a: PathAResult
    path_b: PathBResult
    path_c: PathCResult
    path_d: PathDResult
    path_e: PathEResult
    recommendation: str = ""
    best_path: str = ""
