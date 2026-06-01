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
    energy_type: Literal["fuel", "bev", "phev", "erev", "hybrid", "unknown"] = Field(
        default="unknown",
        description="能源类型：fuel/bev/phev/erev/hybrid/unknown",
    )
    battery_health_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="新能源电池健康度(0-100)",
    )
    battery_warranty_valid: Optional[bool] = Field(None, description="电池质保是否有效")
    operating_vehicle: Optional[bool] = Field(None, description="是否运营车")
    ride_hailing_vehicle: Optional[bool] = Field(None, description="是否网约车")
    battery_replacement_history: Optional[bool] = Field(None, description="是否有电池更换历史")
    range_km: Optional[float] = Field(None, description="标称或当前续航里程(km)")
    overdue_days: Optional[int] = Field(
        None,
        ge=0,
        description="逾期天数。汽车金融不良资产核心要素之一，决定催收路径与处置紧迫性。",
    )
    in_storage: Optional[bool] = Field(
        None,
        description="是否已入库（是否已收车至处置仓）。决定可走拖回路径 vs 远程债权转让路径。",
    )
    storage_days: Optional[int] = Field(
        None,
        ge=0,
        description="在库天数（已入库后停放天数）。影响资金占用成本和残值衰减。",
    )
    buyout_price: Optional[float] = Field(
        None,
        description="历史兼容字段。当前资产包出让定价不再从Excel识别或使用买断价。",
    )


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
    # 当前定价主线为金融公司出让方视角，不再推荐买断价策略
    suggested_strategy: str = "seller_transfer_analysis"
    strategy_message: str = ""


class AssetFieldOverride(BaseModel):
    car_description: Optional[str] = Field(None, description="修正后的车型描述")
    vin: Optional[str] = Field(None, description="修正后的VIN码")
    first_registration: Optional[date] = Field(None, description="修正后的首次登记日期")
    mileage: Optional[float] = Field(None, description="修正后的表显里程(万公里)")
    gps_online: Optional[bool] = Field(None, description="修正后的GPS是否在线")
    insurance_lapsed: Optional[bool] = Field(None, description="修正后的是否脱保")
    ownership_transferred: Optional[bool] = Field(None, description="修正后的是否被过户")
    loan_principal: Optional[float] = Field(None, description="修正后的债权本金(元)")
    energy_type: Optional[Literal["fuel", "bev", "phev", "erev", "hybrid", "unknown"]] = Field(
        None,
        description="修正后的能源类型",
    )
    battery_health_score: Optional[int] = Field(None, ge=0, le=100, description="修正后的电池健康度")
    battery_warranty_valid: Optional[bool] = Field(None, description="修正后的电池质保是否有效")
    operating_vehicle: Optional[bool] = Field(None, description="修正后的是否运营车")
    ride_hailing_vehicle: Optional[bool] = Field(None, description="修正后的是否网约车")
    battery_replacement_history: Optional[bool] = Field(None, description="修正后的电池更换历史")
    range_km: Optional[float] = Field(None, description="修正后的续航里程(km)")
    overdue_days: Optional[int] = Field(None, ge=0, description="修正后的逾期天数")
    in_storage: Optional[bool] = Field(None, description="修正后的是否在库")
    storage_days: Optional[int] = Field(None, ge=0, description="修正后的在库天数")

    @field_validator("car_description", "vin", mode="before")
    @classmethod
    def normalize_blank_strings(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("vin", mode="after")
    @classmethod
    def normalize_vin(cls, value):
        return value.upper() if value else value


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
    asset_package_type: Literal["inventory", "non_inventory"] = Field(
        default="inventory",
        description="资产包类型：inventory=在库车资产包，non_inventory=非在库车资产包",
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
    approval_request_id: Optional[int] = Field(
        default=None,
        description="已通过审批的审批单ID",
    )
    strict_policy: bool = Field(
        default=False,
        description="被商业规则拦截时是否直接报错",
    )
    single_task_budget: Optional[float] = Field(
        default=None,
        description="单次任务预算上限",
    )
    asset_overrides: dict[int, AssetFieldOverride] = Field(
        default_factory=dict,
        description="按Excel行号补录/修正资产字段后重新计算",
    )

    @model_validator(mode="after")
    def validate_strategy_fields(self):
        if self.buyout_strategy == "discount" and self.discount_rate is None:
            raise ValueError("discount 策略必须提供 discount_rate")
        return self


class AssetPricingResult(BaseModel):
    row_number: int
    car_description: str
    loan_principal: Optional[float] = None
    buyout_price: float
    # 本行实际应用的买断价策略 — direct/discount/ai_suggest
    # 或 missing_* 表示降级（例如 discount 策略下该行无本金）
    applied_strategy: str = "direct"
    che300_valuation: Optional[float] = None
    pricing_basis: str = ""
    pricing_basis_amount: float = 0
    recommended_transfer_price_low: float = 0
    recommended_transfer_price_mid: float = 0
    recommended_transfer_price_high: float = 0
    recommended_discount_low: float = 0
    recommended_discount_mid: float = 0
    recommended_discount_high: float = 0
    principal_discount_low: Optional[float] = None
    principal_discount_mid: Optional[float] = None
    principal_discount_high: Optional[float] = None
    valuation_discount_low: Optional[float] = None
    valuation_discount_mid: Optional[float] = None
    valuation_discount_high: Optional[float] = None
    collateral_coverage_ratio: Optional[float] = None
    exposure_gap: Optional[float] = None
    depreciation_rate: Optional[float] = None
    towing_cost: float = 0
    parking_cost: float = 0
    capital_cost: float = 0
    total_cost: float = 0
    expected_revenue: float = 0
    net_profit: float = 0
    profit_margin: float = 0
    risk_flags: list[str] = Field(default_factory=list)
    valuation_confidence_score: int = 0
    valuation_confidence_level: str = "unknown"
    valuation_source: str = "unknown"
    valuation_warnings: list[str] = Field(default_factory=list)
    valuation_anomaly_tags: list[str] = Field(default_factory=list)
    energy_type: str = "unknown"
    market_liquidity_score: int = 0
    market_liquidity_level: str = "medium"
    market_liquidity_adjustment: float = 0
    expected_sale_days_adjusted: int = 0
    liquidity_risk_tags: list[str] = Field(default_factory=list)
    new_energy_risk_tags: list[str] = Field(default_factory=list)
    new_energy_adjustment: float = 0


class ValuationConfidenceResult(BaseModel):
    score: int
    level: Literal["high", "medium", "low", "very_low", "mock"]
    source: str
    warnings: list[str] = Field(default_factory=list)
    anomaly_tags: list[str] = Field(default_factory=list)


class BuyerOfferAnalysis(BaseModel):
    buyer_offer_price: float
    buyer_offer_note: Optional[str] = None
    buyer_offer_discount: Optional[float] = None
    buyer_offer_gap: float
    buyer_offer_gap_rate: Optional[float] = None
    buyer_offer_assessment: str
    negotiation_suggestions: list[str] = Field(default_factory=list)


class TradeabilityResult(BaseModel):
    score: int
    level: Literal["A", "B", "C", "D", "E"]
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    breakdown: dict[str, float] = Field(default_factory=dict)


class TransferComplianceChecklist(BaseModel):
    asset_scope_confirmed: bool = Field(default=False, description="符合可转让资产范围")
    internal_approval_completed: bool = Field(default=False, description="内部审批已完成")
    asset_authenticity_verified: bool = Field(default=False, description="资产真实性已核验")
    transfer_restriction_checked: bool = Field(default=False, description="限制转让情形已核验")
    pricing_basis_archived: bool = Field(default=False, description="估值和定价依据已归档")
    inquiry_process_recorded: bool = Field(default=False, description="询价/竞价过程已留痕")
    debtor_notification_arranged: bool = Field(default=False, description="债务人通知已安排")
    no_hidden_repurchase_commitment: bool = Field(default=False, description="无抽屉协议/回购兜底")
    archive_completed: bool = Field(default=False, description="资料归档已完成")
    watermark_export_completed: bool = Field(default=False, description="导出和报告水印已完成")


class TransferComplianceResult(BaseModel):
    compliance_score: int
    compliance_level: str
    checklist: TransferComplianceChecklist
    missing_items: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    archive_requirements: list[str] = Field(default_factory=list)
    summary: str = ""


class MarketLiquidityResult(BaseModel):
    score: int
    level: Literal["high", "medium", "low", "very_low"]
    adjustment: float = 0
    expected_sale_days_adjusted: int
    liquidity_risk_tags: list[str] = Field(default_factory=list)
    energy_type: Literal["fuel", "bev", "phev", "erev", "hybrid", "unknown"] = "unknown"
    new_energy_risk_tags: list[str] = Field(default_factory=list)
    new_energy_adjustment: float = 0


class PackageSummary(BaseModel):
    total_assets: int
    total_buyout_cost: float = 0
    total_expected_revenue: float = 0
    total_net_profit: float = 0
    overall_roi: float = 0
    recommended_max_discount: float = 0
    asset_package_type: Literal["inventory", "non_inventory"] = "inventory"
    discount_basis: str = ""
    total_principal: float = 0
    total_vehicle_valuation: float = 0
    valuation_coverage_rate: float = 0
    recommended_transfer_price_low: float = 0
    recommended_transfer_price_mid: float = 0
    recommended_transfer_price_high: float = 0
    recommended_discount_low: float = 0
    recommended_discount_mid: float = 0
    recommended_discount_high: float = 0
    principal_recovery_rate_low: Optional[float] = None
    principal_recovery_rate_mid: Optional[float] = None
    principal_recovery_rate_high: Optional[float] = None
    valuation_realization_rate_low: Optional[float] = None
    valuation_realization_rate_mid: Optional[float] = None
    valuation_realization_rate_high: Optional[float] = None
    collateral_coverage_ratio: Optional[float] = None
    analysis_report: str = ""
    pricing_methodology: str = ""
    high_risk_count: int = 0
    risk_alerts: list[str] = Field(default_factory=list)
    # 本次计算请求的买断价策略及参数（让前端一眼看清策略是否生效）
    requested_strategy: str = "direct"
    discount_rate_used: Optional[float] = None
    # 各策略实际命中的行数统计
    strategy_breakdown: dict[str, int] = Field(default_factory=dict)
    tradeability_score: int = 0
    tradeability_level: Literal["A", "B", "C", "D", "E"] = "E"
    tradeability_summary: str = ""
    tradeability_recommendations: list[str] = Field(default_factory=list)
    tradeability_breakdown: dict[str, float] = Field(default_factory=dict)
    buyer_offer_analysis: Optional[BuyerOfferAnalysis] = None
    compliance_checklist: Optional[TransferComplianceResult] = None
    avg_market_liquidity_score: Optional[float] = None
    low_liquidity_count: int = 0
    new_energy_asset_count: int = 0
    market_liquidity_summary: str = ""
    # ── B1: 不良资产业务字段聚合(逾期 / 在库 / 数据完整性)─────────────
    # 这些字段让 Agent 不必遍历每台车,直接从 summary 读到分层结果。
    overdue_segments_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="逾期分层计数 {M3-/M3-M6/M6-M12/M12+/unknown: count}",
    )
    m12_plus_count: int = Field(
        default=0,
        description="逾期 > 365 天的车辆数(M12+池),决定法务推进 / 债权转让强度",
    )
    m6_m12_count: int = Field(
        default=0,
        description="逾期 180-365 天的车辆数(M6-M12池),协商减免 / 资料补全候选",
    )
    missing_vin_count: int = Field(
        default=0,
        description="缺 VIN 车辆数,直接影响出让合规与定价可信度",
    )
    in_storage_count: int = Field(
        default=0,
        description="已入库(已收车)车辆数",
    )
    not_in_storage_count: int = Field(
        default=0,
        description="未入库车辆数 —— 可能需走债权转让而非拖车处置",
    )
    storage_days_avg: Optional[float] = Field(
        default=None,
        description="已入库车辆的平均在库天数(空时无在库车辆)",
    )
    long_storage_count: int = Field(
        default=0,
        description="在库 > 90 天的车辆数,资金占用 / 残值衰减预警",
    )


class PackageCalculationResult(BaseModel):
    package_id: int
    summary: PackageSummary
    assets: list[AssetPricingResult]
