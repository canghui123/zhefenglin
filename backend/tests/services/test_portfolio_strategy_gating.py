"""组合策略对比 — 物权前提门禁测试

《民事诉讼法》196-197 条的实现担保物权特别程序要求债权人已取得担保物占有；
对"未收回"分层推荐该路径在法律上不可行，必须被显式屏蔽并带上原因。

此前 compute_strategy_comparison 只屏蔽了 retail_auction / vehicle_transfer / bulk_clearance，
漏掉了 special_procedure，导致部分车辆未回收时系统仍把"实现担保物权"排为推荐路径。
"""
from __future__ import annotations

import pytest

from services.portfolio_engine import (
    compute_strategy_comparison,
    generate_role_recommendations,
)


def _seg(
    *,
    bucket: str = "M3(61-90天)",
    status: str = "未收回",
    count: int = 20,
    total_ead: float = 2_000_000,
    avg_vehicle_value: float = 80_000,
    avg_lgd: float = 0.45,
    avg_recovery_days: int = 120,
    expected_loss_amount: float = 900_000,
    expected_loss_rate: float = 0.45,
    cash_30d: float = 50_000,
    cash_90d: float = 400_000,
    cash_180d: float = 900_000,
    segment_name: str | None = None,
    recommended_strategy: str = "collection",
) -> dict:
    return {
        "segment_name": segment_name or f"{bucket} | {status}",
        "overdue_bucket": bucket,
        "recovered_status": status,
        "asset_count": count,
        "total_ead": total_ead,
        "avg_vehicle_value": avg_vehicle_value,
        "avg_lgd": avg_lgd,
        "avg_recovery_days": avg_recovery_days,
        "expected_loss_amount": expected_loss_amount,
        "expected_loss_rate": expected_loss_rate,
        "cash_30d": cash_30d,
        "cash_90d": cash_90d,
        "cash_180d": cash_180d,
        "recommended_strategy": recommended_strategy,
    }


def _by_type(results: list[dict]) -> dict[str, dict]:
    return {r["strategy_type"]: r for r in results}


def test_special_procedure_blocked_when_vehicle_not_recovered():
    """未收回分层：special_procedure 必须携带'不推荐原因'，不得被排到榜首。"""
    seg = _seg(status="未收回", bucket="M4(91-120天)")
    results = compute_strategy_comparison(seg)
    by_type = _by_type(results)

    assert "special_procedure" in by_type
    reasons = by_type["special_procedure"]["not_recommended_reasons"]
    assert reasons, "未收回分层 special_procedure 必须有约束提示"
    assert any("占有" in r or "未收回" in r for r in reasons), (
        f"约束提示文案应点明物权占有前提，实际: {reasons}"
    )

    # 2026-04-22 起系统不再做路径推荐，只用 not_recommended_reasons 作为约束提示
    # 排序现在是纯 net_recovery_pv 降序，不再把带约束的路径排到末尾


def test_api_does_not_return_recommended_strategy():
    """/strategies 端点不再返回推荐路径 —— 系统不替代人工判断。"""
    from api.portfolio import portfolio_strategies  # noqa: WPS433

    # 复现 api/portfolio.py 的 /strategies 端点逻辑
    import asyncio
    result = asyncio.run(portfolio_strategies(segment_index=0))

    assert result["recommended_strategy"] is None, (
        "系统不再做路径推荐，recommended_strategy 应固定为 None"
    )
    # 但所有路径的分析数据必须完整返回
    assert len(result["strategies"]) >= 5
    for s in result["strategies"]:
        assert "net_recovery_pv" in s
        assert "cost_breakdown" in s
        assert "not_recommended_reasons" in s


def test_api_recommendation_skips_special_procedure_for_not_recovered():
    """虽然不再由系统推荐，但约束提示（not_recommended_reasons）仍要正确标注。"""
    seg = _seg(status="未收回", bucket="M5(121-150天)")
    results = compute_strategy_comparison(seg)

    recommended = None
    for s in results:
        if not s["not_recommended_reasons"]:
            recommended = s["strategy_type"]
            break

    assert recommended is not None
    assert recommended != "special_procedure", (
        "未收回分层不得推荐'实现担保物权特别程序'，这是物权法硬前提"
    )


def test_special_procedure_available_when_vehicle_recovered():
    """已入库分层：special_procedure 应保持可选（不带阻断原因）。"""
    seg = _seg(
        status="已入库",
        bucket="M3(61-90天)",
        avg_lgd=0.35,
        expected_loss_amount=700_000,
    )
    results = compute_strategy_comparison(seg)
    by_type = _by_type(results)

    reasons = by_type["special_procedure"]["not_recommended_reasons"]
    # 成功率过低等业务原因仍可能触发，但不得有"未收回/占有"相关的阻断
    assert not any("占有" in r or "未收回" in r for r in reasons), (
        f"已入库分层 special_procedure 不应触发物权占有阻断：{reasons}"
    )
    assert not any("M1" in r or "M2" in r for r in reasons), (
        f"M3 已入库分层 special_procedure 不应触发逾期阶段阻断：{reasons}"
    )


def test_special_procedure_blocked_before_m3_even_when_in_inventory():
    """M1-M2 即便已入库，也不应把 special_procedure 作为可推荐路径。"""
    for bucket in ("M1(1-30天)", "M2(31-60天)"):
        seg = _seg(status="已入库", bucket=bucket)
        results = compute_strategy_comparison(seg)
        reasons = _by_type(results)["special_procedure"]["not_recommended_reasons"]

        assert reasons, f"{bucket} 已入库 special_procedure 必须带逾期阶段阻断原因"
        assert any("M3" in r or "M1-M2" in r for r in reasons), (
            f"阻断原因应点明至少 M3 以上，实际: {reasons}"
        )


def test_special_procedure_blocked_when_recovered_not_in_inventory():
    """已收回未入库：缺入库证据链，special_procedure 仍需屏蔽，推荐先入库。

    业务规则（用户 2026-04-22 明确）：只有"已入库"状态才允许推荐特别程序，
    "已收回未入库"虽有事实占有但缺入库备案证明，法院立案难以受理。
    """
    seg = _seg(status="已收回未入库", bucket="M3(61-90天)")
    results = compute_strategy_comparison(seg)
    by_type = _by_type(results)

    reasons = by_type["special_procedure"]["not_recommended_reasons"]
    assert reasons, "已收回未入库分层 special_procedure 必须带阻断原因"
    assert any("入库" in r for r in reasons), (
        f"阻断原因应点明需要入库备案，实际: {reasons}"
    )

    # 复现 api/portfolio.py 推荐逻辑：推荐策略不得是 special_procedure
    recommended = None
    for s in results:
        if not s["not_recommended_reasons"]:
            recommended = s["strategy_type"]
            break
    assert recommended != "special_procedure", (
        "已收回未入库分层不得推荐'实现担保物权特别程序'"
    )


def test_special_procedure_only_available_when_in_inventory():
    """断言：只有'已入库'是唯一允许推荐 special_procedure 的状态。"""
    for status in ("未收回", "已收回未入库"):
        seg = _seg(status=status, bucket="M4(91-120天)")
        results = compute_strategy_comparison(seg)
        by_type = _by_type(results)
        assert by_type["special_procedure"]["not_recommended_reasons"], (
            f"status={status} 时 special_procedure 必须带阻断原因"
        )


def test_dishonest_enforced_debtor_blocks_collection_strategy():
    seg = _seg(status="未收回", bucket="M3(61-90天)")
    seg["debtor_dishonest_enforced"] = True

    results = compute_strategy_comparison(seg)
    collection = _by_type(results)["collection"]

    assert collection["success_probability"] == 0
    assert any("失信" in reason for reason in collection["not_recommended_reasons"])

    seg = _seg(
        status="已入库",
        bucket="M4(91-120天)",
        avg_lgd=0.35,
        expected_loss_amount=700_000,
    )
    results = compute_strategy_comparison(seg)
    by_type = _by_type(results)
    reasons = by_type["special_procedure"]["not_recommended_reasons"]
    assert not any(
        "占有" in r or "未收回" in r or "入库" in r for r in reasons
    ), f"已入库分层 special_procedure 不应触发物权/入库阻断：{reasons}"


def test_exec_recommendation_splits_m4p_by_recovery_status():
    """executive 角色的 M4+ 建议应按三态分开：已入库才推荐特别程序，其它两态各自给引导。"""
    segments = [
        _seg(status="未收回", bucket="M4(91-120天)", count=30),
        _seg(status="已收回未入库", bucket="M5(121-150天)", count=15),
        _seg(status="已入库", bucket="M5(121-150天)", count=20),
    ]
    overview = {
        "total_ead": sum(s["total_ead"] for s in segments),
        "total_expected_loss": sum(s["expected_loss_amount"] for s in segments),
        "total_expected_loss_rate": 0.40,
        "cash_30d": 100_000,
        "recovered_rate": 0.35,
    }
    recs = generate_role_recommendations(overview, segments, "executive")

    def _is_recommending_special(text: str) -> bool:
        """文案是'推荐走特别程序'还是'解释为什么不能走特别程序'。"""
        if "特别程序" not in text:
            return False
        # 否定性表述：'不可/无物权/未收回'开头的解释不算推荐
        if any(neg in text for neg in ("不可", "无物权", "不能")):
            return False
        return True

    # 把特别程序作为"推荐解"的建议必须限定在已入库范围（不能泛化到"已收回"）
    recommending_special = [r for r in recs if _is_recommending_special(r["recommendation_text"])]
    for r in recommending_special:
        assert "已入库" in r["recommendation_title"] or "已入库" in r["recommendation_text"], (
            f"推荐特别程序的建议必须限定在已入库范围（不含'已收回未入库'）：{r}"
        )

    # 对未收回部分应建议收车或走普通诉讼保全，不得直接点名特别程序作为解
    not_recovered_recs = [
        r for r in recs
        if "未收回" in r.get("recommendation_title", "") or "未收回" in r.get("recommendation_text", "")
    ]
    for r in not_recovered_recs:
        txt = r["recommendation_text"]
        # 文案可以提到"不可直接走特别程序"作为解释，但不得把特别程序作为推荐解
        if "特别程序" in txt:
            assert "不可" in txt or "无" in txt, (
                f"未收回建议中提到特别程序时必须明确'不可/无物权前提'：{r}"
            )
