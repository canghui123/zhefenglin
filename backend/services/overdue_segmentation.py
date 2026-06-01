"""逾期天数 / 在库状态分层模块。

汽车金融不良资产业内常用 M3 / M6 / M12 分层,决定处置策略与紧迫度:

| Segment   | 逾期天数      | 业内别称 | 主推策略                          |
|-----------|---------------|----------|-----------------------------------|
| M3-       | < 90 天       | 关注     | 早期催收 / 续谈 / 协商             |
| M3-M6     | 90-180 天     | 次级早期 | 协商减免 / 资料补全 / 法务初步     |
| M6-M12    | 180-365 天    | 次级深度 | 法务推进 / 转 AMC / 准备出让       |
| M12+      | > 365 天      | 可疑/损失| 优先法务推进 / 纳入债权转让池      |

参考依据:
- 银保监会五级分类标准
- 汽车金融行业惯例(各家汽融公司 M 月度报表口径)

此模块**只提供分层判断和业务知识**,具体怎么消费由各 Agent 决定:
- `asset_package_diagnosis_agent` -> 写入 key_findings + risk_warnings
- `operation_planning_agent`      -> M6/M12 进入法务推进池 / 债权转让池
- `task_generation_agent`         -> M12+ 自动生成 high 优先级 legal 任务草稿
- `pricing_engine.tradeability`   -> "处置时效性"维度评分(配合在库状态)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, Optional


class OverdueSegment(str, Enum):
    """逾期分层枚举。"""

    UNKNOWN = "unknown"
    M3_MINUS = "M3-"
    M3_M6 = "M3-M6"
    M6_M12 = "M6-M12"
    M12_PLUS = "M12+"


# 中文展示用标签
OVERDUE_SEGMENT_LABELS: dict[OverdueSegment, str] = {
    OverdueSegment.UNKNOWN: "逾期数据缺失",
    OverdueSegment.M3_MINUS: "M3-(< 90 天)",
    OverdueSegment.M3_M6: "M3-M6(90-180 天)",
    OverdueSegment.M6_M12: "M6-M12(180-365 天)",
    OverdueSegment.M12_PLUS: "M12+(> 365 天)",
}


# 各分层主推处置策略文案
OVERDUE_SEGMENT_ADVICE: dict[OverdueSegment, str] = {
    OverdueSegment.UNKNOWN: "缺逾期天数,需先补资料才能判断处置路径",
    OverdueSegment.M3_MINUS: "短期逾期,优先催收与续谈",
    OverdueSegment.M3_M6: "中期逾期,协商减免、资料补全并准备法务",
    OverdueSegment.M6_M12: "长期逾期,推进法务流程或转 AMC",
    OverdueSegment.M12_PLUS: "严重逾期,优先法务推进或纳入债权转让池",
}


# 高优先级 segment —— Agent 在生成任务草稿时把这些归为 high 优先级
HIGH_PRIORITY_SEGMENTS: set[OverdueSegment] = {
    OverdueSegment.M6_M12,
    OverdueSegment.M12_PLUS,
}


# 进入法务推进池的 segment
LEGAL_ADVANCEMENT_SEGMENTS: set[OverdueSegment] = {
    OverdueSegment.M6_M12,
    OverdueSegment.M12_PLUS,
}


# 进入债权转让池的 segment
DEBT_TRANSFER_SEGMENTS: set[OverdueSegment] = {
    OverdueSegment.M12_PLUS,
}


def classify_overdue_days(days: Optional[int]) -> OverdueSegment:
    """根据逾期天数判定 segment。

    None / 0 / 负数 -> UNKNOWN(不假装识别,避免误导后续 Agent 决策)
    1-89             -> M3_MINUS
    90-179           -> M3_M6
    180-364          -> M6_M12
    365+             -> M12_PLUS
    """
    if days is None or days <= 0:
        return OverdueSegment.UNKNOWN
    if days < 90:
        return OverdueSegment.M3_MINUS
    if days < 180:
        return OverdueSegment.M3_M6
    if days < 365:
        return OverdueSegment.M6_M12
    return OverdueSegment.M12_PLUS


def segment_label(segment: OverdueSegment) -> str:
    """获取中文展示标签。"""
    return OVERDUE_SEGMENT_LABELS[segment]


def segment_advice(segment: OverdueSegment) -> str:
    """获取该 segment 的主推处置建议。"""
    return OVERDUE_SEGMENT_ADVICE[segment]


def aggregate_overdue_segments(
    assets: Iterable[Any],
    *,
    days_attr: str = "overdue_days",
) -> dict[str, dict[str, Any]]:
    """聚合一组资产的逾期分层分布。

    Args:
        assets: 任何有 overdue_days 属性的对象(Asset / dict 等)
        days_attr: 字段名(默认 overdue_days)

    Returns:
        {
            "M3-":  {"count": 5, "label": "M3-(< 90 天)"},
            "M3-M6": {"count": 2, "label": "..."},
            ...
            "total": 30,
        }
    """
    counter: dict[OverdueSegment, int] = {seg: 0 for seg in OverdueSegment}
    total = 0
    for asset in assets:
        days = _read_attr(asset, days_attr)
        seg = classify_overdue_days(days if isinstance(days, int) else None)
        counter[seg] += 1
        total += 1

    breakdown: dict[str, dict[str, Any]] = {}
    for seg in OverdueSegment:
        breakdown[seg.value] = {
            "count": counter[seg],
            "label": OVERDUE_SEGMENT_LABELS[seg],
        }
    breakdown["total"] = total  # type: ignore[assignment]
    return breakdown


def _read_attr(obj: Any, attr: str) -> Optional[int]:
    """通用读字段:既支持 Asset 对象也支持 dict。"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        val = obj.get(attr)
    else:
        val = getattr(obj, attr, None)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ============================================================
# 在库时效评分(供 pricing_engine.tradeability 用)
# ============================================================

def storage_timeliness_score(
    *,
    in_storage: Optional[bool],
    storage_days: Optional[int],
    max_score: float = 10.0,
) -> float:
    """根据在库状态 + 在库天数计算"处置时效性"得分(0..max_score)。

    业务设计:
    - 未入库(in_storage=False): 1/4 分,远程债权处置慢
    - 在库未知(in_storage=None): 1/4 分,数据缺口
    - 在库 ≤ 30 天: 满分,新鲜资产快速处置
    - 在库 31-90 天: 7/10 分
    - 在库 91-180 天: 4/10 分,资金占用警告
    - 在库 > 180 天: 1/10 分,处置已严重滞后

    返回 0..max_score 范围内的浮点数。
    """
    if in_storage is None:
        return max_score * 0.25
    if in_storage is False:
        return max_score * 0.25

    # in_storage is True
    if storage_days is None:
        return max_score * 0.7  # 已入库但天数不详,给中等分

    if storage_days <= 30:
        return max_score
    if storage_days <= 90:
        return max_score * 0.7
    if storage_days <= 180:
        return max_score * 0.4
    return max_score * 0.1
