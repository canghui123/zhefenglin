"""组合驾驶舱数据模型"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class PortfolioOverview(BaseModel):
    """组合总览"""
    snapshot_date: str
    scenario_name: str = "baseline"
    total_ead: float = Field(0, description="存量不良余额(元)")
    total_asset_count: int = Field(0, description="存量笔数")
    total_expected_loss: float = Field(0, description="预计总损失额")
    total_expected_loss_rate: float = Field(0, description="预计总损失率")
    cash_30d: float = Field(0, description="30天预计净现金回流")
    cash_90d: float = Field(0, description="90天预计净现金回流")
    cash_180d: float = Field(0, description="180天预计净现金回流")
    recovered_rate: float = Field(0, description="已收车率")
    in_inventory_rate: float = Field(0, description="已入库率")
    avg_inventory_days: float = Field(0, description="平均库存天数")
    high_risk_segment_count: int = Field(0, description="高风险分层数")
    provision_impact: float = Field(0, description="拨备压力变化")
    capital_release_score: float = Field(0, description="资本释放评分(0-100)")
    # 建议区
    monthly_judgment: str = ""
    top_risks: list[str] = []
    top_actions: list[str] = []
    resource_suggestions: list[str] = []


class SegmentDetail(BaseModel):
    """分层详情"""
    segment_id: int
    segment_name: str
    overdue_bucket: Optional[str] = None
    recovered_status: Optional[str] = None
    inventory_bucket: Optional[str] = None
    asset_count: int = 0
    total_ead: float = 0
    avg_vehicle_value: float = 0
    avg_lgd: float = 0
    avg_recovery_days: int = 0
    expected_loss_amount: float = 0
    expected_loss_rate: float = 0
    cash_30d: float = 0
    cash_90d: float = 0
    cash_180d: float = 0
    recommended_strategy: Optional[str] = None


class SegmentationResult(BaseModel):
    """分层分析结果"""
    snapshot_id: int
    dimension: str = "overdue_bucket"
    segments: list[SegmentDetail] = []
    total_ead: float = 0
    total_loss: float = 0


class StrategyComparison(BaseModel):
    """单路径模拟结果"""
    strategy_type: str
    strategy_name: str
    success_probability: float = 0
    expected_recovery_gross: float = 0
    total_cost: float = 0
    net_recovery_pv: float = 0
    expected_loss_amount: float = 0
    expected_loss_rate: float = 0
    expected_recovery_days: int = 0
    capital_release_score: float = 0
    cost_breakdown: dict = {}
    risk_notes: list[str] = []
    not_recommended_reasons: list[str] = []


class StrategyResult(BaseModel):
    """路径模拟结果"""
    snapshot_id: int
    segment_id: int
    segment_name: str
    strategies: list[StrategyComparison] = []
    recommended_strategy: Optional[str] = None


class CashflowBucket(BaseModel):
    """现金流桶"""
    bucket_day: int
    gross_cash_in: float = 0
    gross_cash_out: float = 0
    net_cash_flow: float = 0
    discounted_net_cash_flow: float = 0


class CashflowByStrategy(BaseModel):
    """按路径拆分的现金流"""
    strategy_type: str
    strategy_name: str
    buckets: list[CashflowBucket] = []
    total_net_cash: float = 0


class CashflowBySegment(BaseModel):
    """按分层拆分的现金流"""
    segment_name: str
    buckets: list[CashflowBucket] = []
    total_net_cash: float = 0


class CashflowResult(BaseModel):
    """现金回流分析"""
    snapshot_id: int
    total_buckets: list[CashflowBucket] = []
    by_strategy: list[CashflowByStrategy] = []
    by_segment: list[CashflowBySegment] = []
    total_long_tail: float = Field(0, description="长尾占压金额(180天以上)")
    cash_return_rate: float = Field(0, description="回现率")


class RoleRecommendation(BaseModel):
    """角色建议"""
    role_level: str
    recommendation_title: str
    recommendation_text: str
    expected_impact: dict = {}
    feasibility_score: float = 0
    realism_score: float = 0
    resource_needs: list[str] = []
    priority: int = 3
    approval_needed: bool = False
    deadline_window: Optional[str] = None


class ExecutiveDashboard(BaseModel):
    """高管驾驶页"""
    overview: PortfolioOverview
    loss_contribution_by_segment: list[dict] = []
    resource_suggestions: list[str] = []
    approval_items: list[str] = []
    recommendations: list[RoleRecommendation] = []
