"""B1 — 逾期分层模块单元测试。

覆盖:
- classify_overdue_days 边界值
- aggregate_overdue_segments 聚合行为
- storage_timeliness_score 各档位
"""

from __future__ import annotations

import pytest

from services.overdue_segmentation import (
    DEBT_TRANSFER_SEGMENTS,
    HIGH_PRIORITY_SEGMENTS,
    LEGAL_ADVANCEMENT_SEGMENTS,
    OVERDUE_SEGMENT_ADVICE,
    OVERDUE_SEGMENT_LABELS,
    OverdueSegment,
    aggregate_overdue_segments,
    classify_overdue_days,
    segment_advice,
    segment_label,
    storage_timeliness_score,
)


# ============================================================
# classify_overdue_days
# ============================================================

@pytest.mark.parametrize("days,expected", [
    # 无效输入 → UNKNOWN
    (None, OverdueSegment.UNKNOWN),
    (0, OverdueSegment.UNKNOWN),
    (-1, OverdueSegment.UNKNOWN),
    (-365, OverdueSegment.UNKNOWN),
    # M3- 边界
    (1, OverdueSegment.M3_MINUS),
    (45, OverdueSegment.M3_MINUS),
    (89, OverdueSegment.M3_MINUS),
    # M3-M6 边界
    (90, OverdueSegment.M3_M6),
    (135, OverdueSegment.M3_M6),
    (179, OverdueSegment.M3_M6),
    # M6-M12 边界
    (180, OverdueSegment.M6_M12),
    (272, OverdueSegment.M6_M12),
    (364, OverdueSegment.M6_M12),
    # M12+ 边界
    (365, OverdueSegment.M12_PLUS),
    (612, OverdueSegment.M12_PLUS),
    (1100, OverdueSegment.M12_PLUS),
])
def test_classify_overdue_days_boundaries(days, expected):
    assert classify_overdue_days(days) == expected


def test_segment_label_returns_chinese():
    """所有 segment 都有中文标签."""
    for seg in OverdueSegment:
        label = segment_label(seg)
        assert label
        assert isinstance(label, str)


def test_segment_advice_returns_actionable_text():
    """每个 segment 都有具体业务建议(不为空,且含动作词)."""
    for seg in OverdueSegment:
        advice = segment_advice(seg)
        assert advice
        # 至少含一个动作关键词
        action_words = ["催收", "续谈", "协商", "法务", "AMC", "转让", "补资料"]
        assert any(word in advice for word in action_words), \
            f"segment {seg} advice 应含动作词:{advice}"


# ============================================================
# 业务规则常量
# ============================================================

def test_high_priority_segments_only_include_m6_m12_and_m12_plus():
    """高优先级 segment(影响 task draft 优先级)只包括 M6-M12 和 M12+."""
    assert HIGH_PRIORITY_SEGMENTS == {OverdueSegment.M6_M12, OverdueSegment.M12_PLUS}


def test_legal_advancement_segments_excludes_m3_minus():
    """法务推进池不包含早期逾期(M3-)."""
    assert OverdueSegment.M3_MINUS not in LEGAL_ADVANCEMENT_SEGMENTS
    assert OverdueSegment.UNKNOWN not in LEGAL_ADVANCEMENT_SEGMENTS


def test_debt_transfer_segments_only_m12_plus():
    """债权转让池只包含 M12+(只有严重逾期才考虑转让)."""
    assert DEBT_TRANSFER_SEGMENTS == {OverdueSegment.M12_PLUS}


# ============================================================
# aggregate_overdue_segments
# ============================================================

class _MockAsset:
    """测试用 mock,模拟 Asset 对象."""
    def __init__(self, overdue_days):
        self.overdue_days = overdue_days


def test_aggregate_overdue_segments_with_objects():
    """传入对象时正确聚合."""
    assets = [
        _MockAsset(60),    # M3-
        _MockAsset(120),   # M3-M6
        _MockAsset(200),   # M6-M12
        _MockAsset(500),   # M12+
        _MockAsset(700),   # M12+
        _MockAsset(None),  # UNKNOWN
    ]
    result = aggregate_overdue_segments(assets)
    assert result["M3-"]["count"] == 1
    assert result["M3-M6"]["count"] == 1
    assert result["M6-M12"]["count"] == 1
    assert result["M12+"]["count"] == 2
    assert result["unknown"]["count"] == 1
    assert result["total"] == 6


def test_aggregate_overdue_segments_with_dicts():
    """传入 dict 时也正确聚合(便于 evidence payload 使用)."""
    assets = [
        {"overdue_days": 60},
        {"overdue_days": 500},
        {"overdue_days": 500},
    ]
    result = aggregate_overdue_segments(assets)
    assert result["M3-"]["count"] == 1
    assert result["M12+"]["count"] == 2
    assert result["total"] == 3


def test_aggregate_overdue_segments_empty_input():
    """空输入 -> 全 0."""
    result = aggregate_overdue_segments([])
    assert result["total"] == 0
    for seg in OverdueSegment:
        assert result[seg.value]["count"] == 0


def test_aggregate_overdue_segments_demo_risky_package_distribution():
    """演示问题包预期分布(19 台 M12+),sanity check 演示数据."""
    # 问题包逾期分布:300-1100 天,按 random 大概率全部 > 365
    risky_overdues = [300, 360, 420, 510, 600, 700, 800, 950, 1100] * 3 + [None, 50, 120]
    result = aggregate_overdue_segments([_MockAsset(d) for d in risky_overdues])
    # 大量 M12+ 是问题包的核心特征
    assert result["M12+"]["count"] >= 10, \
        f"演示问题包应有大量 M12+,实际 {result['M12+']['count']}"


# ============================================================
# storage_timeliness_score
# ============================================================

@pytest.mark.parametrize("in_storage,storage_days,expected", [
    # 未入库 -> 1/4 分
    (False, None, 2.5),
    (False, 100, 2.5),  # 未入库时 days 无意义
    # 在库未知 -> 1/4 分
    (None, None, 2.5),
    (None, 30, 2.5),
    # 在库且天数已知
    (True, 0, 10.0),
    (True, 15, 10.0),
    (True, 30, 10.0),     # 边界:30 天满分
    (True, 31, 7.0),
    (True, 60, 7.0),
    (True, 90, 7.0),       # 边界:90 天 70%
    (True, 91, 4.0),
    (True, 150, 4.0),
    (True, 180, 4.0),      # 边界:180 天 40%
    (True, 181, 1.0),
    (True, 365, 1.0),
    # 在库但天数缺失
    (True, None, 7.0),     # 已入库但 days 不详,中等分
])
def test_storage_timeliness_score(in_storage, storage_days, expected):
    score = storage_timeliness_score(in_storage=in_storage, storage_days=storage_days)
    assert score == pytest.approx(expected, abs=0.01), \
        f"in_storage={in_storage}, storage_days={storage_days}, 期望 {expected}, 实际 {score}"


def test_storage_timeliness_score_custom_max():
    """支持自定义满分(便于不同维度复用)."""
    score = storage_timeliness_score(in_storage=True, storage_days=15, max_score=20.0)
    assert score == pytest.approx(20.0, abs=0.01)


def test_label_and_advice_dict_coverage():
    """LABELS / ADVICE 字典必须覆盖所有 enum 值,避免 KeyError."""
    for seg in OverdueSegment:
        assert seg in OVERDUE_SEGMENT_LABELS
        assert seg in OVERDUE_SEGMENT_ADVICE
