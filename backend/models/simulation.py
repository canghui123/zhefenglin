from pydantic import BaseModel, Field, model_validator
from typing import Optional


class SandboxInput(BaseModel):
    car_description: str = Field(..., description="车辆描述")
    entry_date: str = Field(..., description="入库日期 YYYY-MM-DD")
    overdue_bucket: str = Field(default="M3(61-90天)", description="逾期阶段: M1/M2/M3/M4/M5/M6+")
    overdue_amount: float = Field(..., description="逾期金额(元)")
    che300_value: float = Field(..., description="当前车300估值(元)")
    province: Optional[str] = Field(default=None, description="资产所在地省份")
    city: Optional[str] = Field(default=None, description="资产所在地城市")

    # 车辆信息（用于差异化贬值）
    vehicle_type: str = Field(default="domestic", description="车辆类型: luxury/japanese/german/domestic/new_energy")
    vehicle_age_years: float = Field(default=3, description="车龄(年)")

    # 成本参数
    daily_parking: float = Field(default=30, description="日停车费(元)")
    recovery_cost: float = Field(default=0, description="收车成本(元)，含拖车/GPS/人工等")
    sunk_collection_cost: float = Field(default=0, description="已发生催收沉没成本(元)，不进入决策对比")
    sunk_legal_cost: float = Field(default=0, description="已发生法务沉没成本(元)，不进入决策对比")
    annual_interest_rate: float = Field(default=24, description="逾期年利率(%)")

    # 车辆占有状态 — 影响路径 C/D 是否可选
    # 实现担保物权特别程序要求债权人已取得担保物占有，并形成入库证据链；
    # 未收回或未入库时系统自动屏蔽路径 D。
    vehicle_recovered: bool = Field(
        default=True,
        description="车辆是否已回收（影响路径C/D是否可选）",
    )
    vehicle_in_inventory: bool = Field(
        default=True,
        description="车辆是否已入库（路径D特别程序的硬前提）",
    )
    debtor_dishonest_enforced: bool = Field(
        default=False,
        description="外部司法数据是否提示债务人为失信被执行人",
    )
    external_find_car_score: Optional[float] = Field(
        default=None,
        description="外部寻车线索评分，0-100；用于后续派单优先级",
    )

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

    @model_validator(mode="after")
    def normalize_vehicle_inventory_state(self):
        if not self.vehicle_recovered:
            self.vehicle_in_inventory = False
        return self


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
    success_probability: float = 0
    future_marginal_net_benefit: float = 0
    sunk_cost_excluded: float = 0


class PathAResult(BaseModel):
    name: str = "继续等待赎车"
    timepoints: list[TimePoint]
    summary: str = ""
    success_probability: float = 0
    future_marginal_net_benefit: float = 0
    sunk_cost_excluded: float = 0
    available: bool = True
    unavailable_reason: str = ""


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
    success_probability: float = 0
    future_marginal_net_benefit: float = 0
    sunk_cost_excluded: float = 0


class PathBResult(BaseModel):
    name: str = "常规诉讼"
    legal_cost: LegalCostDetail
    scenarios: list[LitigationScenario]
    summary: str = ""
    success_probability: float = 0
    future_marginal_net_benefit: float = 0
    sunk_cost_excluded: float = 0


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
    success_probability: float = 0
    future_marginal_net_benefit: float = 0
    sunk_cost_excluded: float = 0
    # 路径可用性 — 车辆未回收时为 False
    available: bool = True
    unavailable_reason: str = ""


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
    success_probability: float = 0
    future_marginal_net_benefit: float = 0
    sunk_cost_excluded: float = 0
    # 路径可用性 — 需债权人已占有担保物、车辆已入库，且至少 M3 以上
    available: bool = True
    unavailable_reason: str = ""


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
    success_probability: float = 0
    future_marginal_net_benefit: float = 0
    sunk_cost_excluded: float = 0


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
