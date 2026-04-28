from pydantic import BaseModel, Field, model_validator
from typing import Any, Optional


class SandboxInput(BaseModel):
    car_description: str = Field(..., description="车辆描述")
    vin: Optional[str] = Field(default=None, description="VIN/车架号，用于车300自动估值")
    license_plate: Optional[str] = Field(default=None, description="车牌号")
    first_registration: Optional[str] = Field(default=None, description="首次上牌日期 YYYY-MM-DD")
    mileage_km: Optional[float] = Field(default=None, description="表显里程(公里)")
    entry_date: str = Field(..., description="入库日期 YYYY-MM-DD")
    overdue_bucket: str = Field(default="M3(61-90天)", description="逾期阶段: M1/M2/M3/M4/M5/M6+")
    overdue_amount: float = Field(..., description="逾期金额(元)")
    che300_value: Optional[float] = Field(default=None, description="当前车300估值(元)，为空时系统自动估值")
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
    # 竞拍参数
    expected_sale_days: int = Field(default=7, description="预计成交天数")
    auction_discount_rate: Optional[float] = Field(default=None, description="竞拍折扣比例，例如0.90表示按估值九折")
    auction_discount_auto: bool = Field(default=True, description="竞拍折扣是否由系统建议")

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
    restructure_redefault_rate: Optional[float] = Field(default=0.30, description="重组后再违约率")
    collection_history_text: Optional[str] = Field(default=None, description="客户过往催收/逾期记录，用于AI分析再违约率")
    redefault_rate_auto: bool = Field(default=False, description="再违约率是否由系统根据历史记录建议")

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
    auction_discount_rate: float = 0
    auction_discount_suggested: bool = False
    auction_discount_note: str = ""
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
    redefault_rate_suggested: bool = False
    redefault_rate_note: str = ""
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


class SandboxSuggestionRequest(BaseModel):
    car_description: str = ""
    vehicle_type: str = "auto"
    vehicle_age_years: float = 3
    overdue_bucket: str = "M3(61-90天)"
    overdue_amount: float = 0
    che300_value: Optional[float] = None
    vehicle_recovered: bool = True
    vehicle_in_inventory: bool = True
    collection_history_text: Optional[str] = None


class SandboxSuggestionResult(BaseModel):
    auction_discount_rate: float
    auction_discount_note: str
    redefault_rate: Optional[float] = None
    redefault_rate_note: Optional[str] = None


class SandboxBatchImportRow(BaseModel):
    row_id: str
    row_number: int
    selected: bool = True
    input: SandboxInput
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    che300_auto_filled: bool = False
    che300_source: str = ""
    suggested_auction_discount_rate: Optional[float] = None
    suggested_redefault_rate: Optional[float] = None


class SandboxBatchImportPreview(BaseModel):
    total_rows: int
    rows: list[SandboxBatchImportRow]
    detected_columns: dict[str, str]
    unmapped_columns: list[str]


class SandboxBatchSimulationRequest(BaseModel):
    rows: list[SandboxBatchImportRow]


class SandboxBatchSimulationItem(BaseModel):
    row_id: str
    row_number: int
    status: str
    result: Optional[SandboxResult] = None
    error: Optional[str] = None


class SandboxBatchSimulationResult(BaseModel):
    total_rows: int
    success_rows: int
    error_rows: int
    results: list[SandboxBatchSimulationItem]
