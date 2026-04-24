from pydantic import BaseModel, Field
from typing import Optional


class ExternalProviderCapability(BaseModel):
    provider_code: str
    provider_name: str
    category: str
    capabilities: list[str] = []
    enabled: bool = False
    integration_status: str = "reserved"


class FindCarSignalRequest(BaseModel):
    vehicle_identifier: Optional[str] = Field(default=None, description="VIN/车牌/内部车辆编号")
    province: Optional[str] = Field(default=None, description="车辆或债务人所在省份")
    city: Optional[str] = Field(default=None, description="车辆或债务人所在城市")
    gps_recent_days: Optional[int] = Field(default=None, description="最近GPS有效信号距今天数")
    etc_recent_days: Optional[int] = Field(default=None, description="最近高速ETC线索距今天数")
    violation_recent_days: Optional[int] = Field(default=None, description="最近违章线索距今天数")
    manual_hint: Optional[str] = Field(default=None, description="人工补充线索")


class FindCarSignalResult(BaseModel):
    score: float = Field(0, description="寻车线索评分，0-100")
    level: str = Field("low", description="low/medium/high")
    signals: list[str] = []
    recommended_action: str = ""


class JudicialRiskRequest(BaseModel):
    debtor_name: str = Field(..., description="债务人姓名或企业名称")
    id_card_last4: Optional[str] = Field(default=None, description="身份证后四位，预留给真实接口")
    litigation_count: int = Field(default=0, description="涉诉数量")
    dishonest_enforced: bool = Field(default=False, description="是否失信被执行人")
    restricted_consumption: bool = Field(default=False, description="是否限制高消费")


class JudicialRiskResult(BaseModel):
    risk_level: str = Field("low", description="low/medium/high")
    score: float = Field(0, description="司法风险评分，0-100")
    collection_blocked: bool = Field(False, description="是否否决继续催收等待还款路径")
    risk_tags: list[str] = []
    decision_note: str = ""
