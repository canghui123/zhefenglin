"""B1 — pricing_engine 业务字段聚合集成测试。

验证 calculate_package 对新加的不良资产业务字段做正确聚合,并通过
PackageSummary 透传给上层 Agent。
"""

from __future__ import annotations

from datetime import date

import pytest

from models.asset import Asset, PricingParameters
from models.valuation import ValuationResult
from services.pricing_engine import calculate_package


def _vin(prefix: str = "DEMO") -> str:
    """生成 17 位 VIN。"""
    return f"{prefix}{'A' * (17 - len(prefix))}"


def _asset(
    *,
    row: int,
    vin: str | None = None,
    overdue_days: int | None = None,
    in_storage: bool | None = None,
    storage_days: int | None = None,
    principal: float = 100_000,
) -> Asset:
    """构造一个合规的 Asset。"""
    return Asset(
        row_number=row,
        car_description=f"测试车辆-{row}",
        vin=vin if vin else None,
        first_registration=date(2020, 6, 1),
        mileage=4.0,
        gps_online=True,
        insurance_lapsed=False,
        ownership_transferred=False,
        loan_principal=principal,
        energy_type="fuel",
        overdue_days=overdue_days,
        in_storage=in_storage,
        storage_days=storage_days,
    )


def _val(row: int, valuation: float = 80_000) -> ValuationResult:
    return ValuationResult(
        model_id=f"mock_{row}",
        model_name="测试估值",
        excellent_price=valuation * 1.1,
        good_price=valuation,
        medium_price=valuation * 0.9,
        is_mock=True,
        source="mock",
    )


# ============================================================
# 聚合字段透传到 summary
# ============================================================

def test_summary_includes_overdue_segments_breakdown():
    """summary 应含 overdue_segments_breakdown 完整 5 段计数."""
    assets = [
        _asset(row=1, vin=_vin("DEM1"), overdue_days=50),    # M3-
        _asset(row=2, vin=_vin("DEM2"), overdue_days=120),   # M3-M6
        _asset(row=3, vin=_vin("DEM3"), overdue_days=200),   # M6-M12
        _asset(row=4, vin=_vin("DEM4"), overdue_days=500),   # M12+
        _asset(row=5, vin=_vin("DEM5"), overdue_days=700),   # M12+
        _asset(row=6, vin=_vin("DEM6"), overdue_days=None),  # unknown
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    seg = result.summary.overdue_segments_breakdown
    assert seg["M3-"] == 1
    assert seg["M3-M6"] == 1
    assert seg["M6-M12"] == 1
    assert seg["M12+"] == 2
    assert seg["unknown"] == 1
    assert seg["total"] == 6


def test_summary_m12_plus_count_matches_breakdown():
    assets = [_asset(row=i, vin=_vin(f"D{i}"), overdue_days=700) for i in range(1, 6)]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    assert result.summary.m12_plus_count == 5
    assert result.summary.m6_m12_count == 0


def test_summary_missing_vin_count_and_risk_flag():
    """缺 VIN 不仅计数对,还要在 result.assets 上加 risk_flag."""
    assets = [
        _asset(row=1, vin=_vin("V1")),       # 有 VIN
        _asset(row=2, vin=None),              # 缺 VIN
        _asset(row=3, vin=None),              # 缺 VIN
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    assert result.summary.missing_vin_count == 2

    # row 2 / 3 上应有"缺VIN（数据完整性）"风险标签
    flags_by_row = {r.row_number: r.risk_flags for r in result.assets}
    assert any("缺VIN" in f for f in flags_by_row[2])
    assert any("缺VIN" in f for f in flags_by_row[3])
    assert not any("缺VIN" in f for f in flags_by_row[1])


def test_summary_in_storage_aggregation():
    assets = [
        _asset(row=1, vin=_vin("V1"), in_storage=True, storage_days=10),
        _asset(row=2, vin=_vin("V2"), in_storage=True, storage_days=120),  # 长期
        _asset(row=3, vin=_vin("V3"), in_storage=True, storage_days=20),
        _asset(row=4, vin=_vin("V4"), in_storage=False),
        _asset(row=5, vin=_vin("V5"), in_storage=False),
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    assert result.summary.in_storage_count == 3
    assert result.summary.not_in_storage_count == 2
    assert result.summary.long_storage_count == 1  # 仅 row 2 在库 > 90
    assert result.summary.storage_days_avg == pytest.approx(50.0, abs=0.1)  # (10+120+20)/3


def test_summary_storage_days_avg_none_when_no_in_storage():
    assets = [_asset(row=i, vin=_vin(f"V{i}"), in_storage=False) for i in range(1, 4)]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    assert result.summary.storage_days_avg is None


# ============================================================
# risk_alerts 触发
# ============================================================

def test_m12_plus_triggers_risk_alert():
    assets = [_asset(row=i, vin=_vin(f"V{i}"), overdue_days=500) for i in range(1, 4)]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    assert any("M12+" in alert for alert in result.summary.risk_alerts)


def test_missing_vin_triggers_risk_alert():
    assets = [
        _asset(row=1, vin=None),
        _asset(row=2, vin=None),
        _asset(row=3, vin=_vin("V3")),
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    assert any("缺 VIN" in alert for alert in result.summary.risk_alerts)


def test_long_storage_triggers_risk_alert():
    assets = [
        _asset(row=1, vin=_vin("V1"), in_storage=True, storage_days=200),
        _asset(row=2, vin=_vin("V2"), in_storage=True, storage_days=150),
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    assert any("在库超 90 天" in alert for alert in result.summary.risk_alerts)


# ============================================================
# tradeability 处置时效性维度真正基于 in_storage + storage_days
# ============================================================

def test_tradeability_timeliness_high_for_recent_in_storage():
    """全部在库 < 30 天时,处置时效性维度满分."""
    assets = [
        _asset(row=i, vin=_vin(f"V{i}"), in_storage=True, storage_days=10)
        for i in range(1, 6)
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    timeliness = result.summary.tradeability_breakdown["处置时效性"]
    # 满分 10
    assert timeliness >= 9.0, f"全部新鲜在库应给满分时效,实际 {timeliness}"


def test_tradeability_timeliness_low_for_long_storage():
    """全部在库 > 180 天时,处置时效性维度接近 1/10 分."""
    assets = [
        _asset(row=i, vin=_vin(f"V{i}"), in_storage=True, storage_days=250)
        for i in range(1, 6)
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    timeliness = result.summary.tradeability_breakdown["处置时效性"]
    assert timeliness <= 2.0, f"长期在库应低时效分,实际 {timeliness}"


def test_tradeability_timeliness_quarter_for_not_in_storage():
    """全部未入库时,处置时效性 = 1/4 满分 = 2.5."""
    assets = [
        _asset(row=i, vin=_vin(f"V{i}"), in_storage=False)
        for i in range(1, 6)
    ]
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)
    timeliness = result.summary.tradeability_breakdown["处置时效性"]
    assert 2.0 <= timeliness <= 3.0, f"未入库应给 1/4 分,实际 {timeliness}"


# ============================================================
# 演示数据回归:问题包应该被识别为高 M12+ + 缺 VIN
# ============================================================

def test_demo_risky_package_signature_is_detected():
    """模拟问题包关键特征:大量 M12+ + 3 台缺 VIN + 部分长期在库."""
    assets = []
    # 19 台 M12+
    for i in range(1, 20):
        assets.append(_asset(row=i, vin=_vin(f"D{i:02d}"), overdue_days=600))
    # 3 台缺 VIN
    for i in range(20, 23):
        assets.append(_asset(row=i, vin=None, overdue_days=300))
    # 8 台长期在库
    for i in range(23, 31):
        assets.append(_asset(
            row=i, vin=_vin(f"D{i}"),
            in_storage=True, storage_days=120, overdue_days=400,
        ))
    valuations = {a.row_number: _val(a.row_number) for a in assets}
    result = calculate_package(assets, PricingParameters(), valuations)

    assert result.summary.m12_plus_count >= 19
    assert result.summary.missing_vin_count == 3
    assert result.summary.long_storage_count == 8
    # 至少 3 个相关 risk_alerts
    relevant = [a for a in result.summary.risk_alerts if any(
        k in a for k in ["M12+", "缺 VIN", "在库超 90 天"]
    )]
    assert len(relevant) >= 3, f"问题包应有 3+ 相关风险预警,实际 {relevant}"
