"""组合损失引擎 + 现金回流引擎.

优先使用客户通过数据接入中心导入的有效资产台账；没有导入数据时才回退
内置演示组合，保证空库环境仍可浏览产品能力。
"""

import json
import random
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from repositories import data_import_repo

# ============ 常量 ============

OVERDUE_BUCKETS = [
    "M1(1-30天)", "M2(31-60天)", "M3(61-90天)",
    "M4(91-120天)", "M5(121-150天)", "M6+(>150天)",
]

RECOVERED_STATUSES = ["未收回", "已收回未入库", "已入库"]

STRATEGY_TYPES = {
    "collection": "继续催收等待还款",
    "restructure": "分期重组/和解",
    "retail_auction": "收车后零售/竞拍",
    "litigation": "常规诉讼",
    "special_procedure": "实现担保物权特别程序",
    "debt_transfer": "债权资产包转让",
    "vehicle_transfer": "现车资产包转让",
    "bulk_clearance": "长库龄批量出清",
}

STRATEGY_PROFILES = {
    "collection": {
        "success_rate_base": 0.25, "avg_recovery_days": 45,
        "cost_rate": 0.02, "recovery_rate": 0.30,
    },
    "restructure": {
        "success_rate_base": 0.35, "avg_recovery_days": 90,
        "cost_rate": 0.03, "recovery_rate": 0.55,
    },
    "retail_auction": {
        "success_rate_base": 0.80, "avg_recovery_days": 30,
        "cost_rate": 0.15, "recovery_rate": 0.65,
    },
    "litigation": {
        "success_rate_base": 0.45, "avg_recovery_days": 270,
        "cost_rate": 0.12, "recovery_rate": 0.40,
    },
    "special_procedure": {
        "success_rate_base": 0.60, "avg_recovery_days": 120,
        "cost_rate": 0.08, "recovery_rate": 0.55,
    },
    "debt_transfer": {
        "success_rate_base": 0.95, "avg_recovery_days": 14,
        "cost_rate": 0.05, "recovery_rate": 0.25,
    },
    "vehicle_transfer": {
        "success_rate_base": 0.90, "avg_recovery_days": 14,
        "cost_rate": 0.05, "recovery_rate": 0.45,
    },
    "bulk_clearance": {
        "success_rate_base": 0.95, "avg_recovery_days": 7,
        "cost_rate": 0.03, "recovery_rate": 0.20,
    },
}


def _bucket_index(bucket: str) -> int:
    normalized = (bucket or "").upper()
    for i, b in enumerate(OVERDUE_BUCKETS):
        if normalized.startswith(b[:2]):
            return i
    return 2


def _money(value: Optional[float], fallback: float = 0) -> float:
    if value is None:
        return float(fallback)
    try:
        return max(float(value), 0)
    except (TypeError, ValueError):
        return float(fallback)


def _row_financials(row) -> tuple[float, float]:
    ead = _money(row.loan_principal) or _money(row.overdue_amount)
    vehicle_value = _money(row.vehicle_value, ead * 0.65 if ead else 0)
    if not ead and vehicle_value:
        ead = vehicle_value / 0.65
    return ead, vehicle_value


def _row_lgd(row) -> float:
    ead, vehicle_value = _row_financials(row)
    bucket_idx = _bucket_index(row.overdue_bucket or "")
    status = row.recovered_status or "未收回"
    base = 0.28 + bucket_idx * 0.08
    if status == "已入库":
        base -= 0.10
    elif status == "已收回未入库":
        base -= 0.03
    elif status == "未收回":
        base += 0.12
    if ead and vehicle_value:
        exposure_gap = max(0, ead - vehicle_value) / ead
        base += exposure_gap * 0.18
    return min(0.95, max(0.08, base))


def _row_recovery_days(row) -> int:
    bucket_idx = _bucket_index(row.overdue_bucket or "")
    status = row.recovered_status or "未收回"
    days = 30 + bucket_idx * 22
    if status == "已入库":
        days = max(7, days - 30)
    elif status == "已收回未入库":
        days += 15
    else:
        days += 50
    return int(days)


def _segment_strategy(overdue_bucket: str, recovered_status: str) -> str:
    bucket_idx = _bucket_index(overdue_bucket)
    if recovered_status == "已入库":
        return "bulk_clearance" if bucket_idx >= 4 else "retail_auction"
    if recovered_status == "已收回未入库":
        return "retail_auction"
    if bucket_idx <= 1:
        return "collection"
    if bucket_idx <= 3:
        return "litigation"
    return "debt_transfer"


def _asset_payload(row) -> dict:
    ead, vehicle_value = _row_financials(row)
    raw = {}
    if row.normalized_json:
        try:
            raw = json.loads(row.normalized_json)
        except json.JSONDecodeError:
            raw = {}
    return {
        "asset_identifier": row.asset_identifier or f"IMPORT-{row.id}",
        "contract_number": row.contract_number,
        "debtor_name": row.debtor_name,
        "car_description": row.car_description,
        "vin": row.vin,
        "license_plate": row.license_plate,
        "province": row.province,
        "city": row.city,
        "overdue_bucket": row.overdue_bucket or "M3(61-90天)",
        "overdue_days": row.overdue_days,
        "overdue_amount": round(_money(row.overdue_amount, ead), 2),
        "loan_principal": round(_money(row.loan_principal, ead), 2),
        "vehicle_value": round(vehicle_value, 2),
        "recovered_status": row.recovered_status or "未收回",
        "gps_last_seen": row.gps_last_seen,
        "raw": raw,
    }


def generate_portfolio_from_imports(session: Session, *, tenant_id: int) -> Optional[dict]:
    """Build portfolio analytics from active customer import batches."""
    batches = data_import_repo.list_active_batches_with_rows(
        session,
        tenant_id=tenant_id,
        import_type="asset_ledger",
    )
    if not batches:
        latest = data_import_repo.get_latest_batch_with_rows(
            session,
            tenant_id=tenant_id,
            import_type="asset_ledger",
        ) or data_import_repo.get_latest_batch_with_rows(session, tenant_id=tenant_id)
        batches = [latest] if latest else []
    if not batches:
        return None

    rows = [
        row
        for batch in batches
        for row in data_import_repo.list_valid_rows_for_batch(session, batch_id=batch.id)
        if _row_financials(row)[0] > 0
    ]
    if not rows:
        return None

    grouped: dict[tuple[str, str], dict] = {}
    total_ead = 0.0
    total_loss = 0.0
    total_cash_30 = 0.0
    total_cash_90 = 0.0
    total_cash_180 = 0.0

    for row in rows:
        overdue_bucket = row.overdue_bucket or "M3(61-90天)"
        recovered_status = row.recovered_status or "未收回"
        key = (overdue_bucket, recovered_status)
        if key not in grouped:
            grouped[key] = {
                "segment_name": f"{overdue_bucket} | {recovered_status}",
                "overdue_bucket": overdue_bucket,
                "recovered_status": recovered_status,
                "asset_count": 0,
                "total_ead": 0.0,
                "vehicle_value_sum": 0.0,
                "expected_loss_amount": 0.0,
                "recovery_days_weighted": 0.0,
                "cash_30d": 0.0,
                "cash_90d": 0.0,
                "cash_180d": 0.0,
                "assets": [],
            }
        seg = grouped[key]
        ead, vehicle_value = _row_financials(row)
        lgd = _row_lgd(row)
        recovery_days = _row_recovery_days(row)
        loss = ead * lgd
        net_rate = 1 - lgd
        if recovered_status == "已入库":
            c30, c90, c180 = net_rate * 0.50, net_rate * 0.80, net_rate * 0.95
        elif recovered_status == "已收回未入库":
            c30, c90, c180 = net_rate * 0.20, net_rate * 0.55, net_rate * 0.80
        else:
            c30, c90, c180 = net_rate * 0.05, net_rate * 0.20, net_rate * 0.50

        seg["asset_count"] += 1
        seg["total_ead"] += ead
        seg["vehicle_value_sum"] += vehicle_value
        seg["expected_loss_amount"] += loss
        seg["recovery_days_weighted"] += recovery_days * ead
        seg["cash_30d"] += ead * c30
        seg["cash_90d"] += ead * c90
        seg["cash_180d"] += ead * c180
        seg["assets"].append(_asset_payload(row))

        total_ead += ead
        total_loss += loss
        total_cash_30 += ead * c30
        total_cash_90 += ead * c90
        total_cash_180 += ead * c180

    segments = []
    for seg in grouped.values():
        total = seg["total_ead"]
        avg_vehicle_value = seg["vehicle_value_sum"] / seg["asset_count"] if seg["asset_count"] else 0
        expected_loss_rate = seg["expected_loss_amount"] / total if total else 0
        avg_recovery_days = seg["recovery_days_weighted"] / total if total else 0
        segments.append({
            "segment_name": seg["segment_name"],
            "overdue_bucket": seg["overdue_bucket"],
            "recovered_status": seg["recovered_status"],
            "asset_count": seg["asset_count"],
            "total_ead": round(total, 2),
            "avg_vehicle_value": round(avg_vehicle_value, 2),
            "avg_lgd": round(expected_loss_rate, 4),
            "avg_recovery_days": round(avg_recovery_days, 1),
            "expected_loss_amount": round(seg["expected_loss_amount"], 2),
            "expected_loss_rate": round(expected_loss_rate, 4),
            "cash_30d": round(seg["cash_30d"], 2),
            "cash_90d": round(seg["cash_90d"], 2),
            "cash_180d": round(seg["cash_180d"], 2),
            "recommended_strategy": _segment_strategy(
                seg["overdue_bucket"],
                seg["recovered_status"],
            ),
            "assets": seg["assets"],
        })

    segments.sort(
        key=lambda item: (
            _bucket_index(item["overdue_bucket"]),
            RECOVERED_STATUSES.index(item["recovered_status"])
            if item["recovered_status"] in RECOVERED_STATUSES
            else 99,
        )
    )

    recovered_count = sum(
        s["asset_count"] for s in segments if s["recovered_status"] != "未收回"
    )
    inventory_count = sum(
        s["asset_count"] for s in segments if s["recovered_status"] == "已入库"
    )
    high_risk = sum(1 for s in segments if s["expected_loss_rate"] > 0.60)
    avg_inventory_days = 0
    inventory_segments = [s for s in segments if s["recovered_status"] == "已入库"]
    if inventory_segments:
        inv_ead = sum(s["total_ead"] for s in inventory_segments)
        avg_inventory_days = sum(
            s["avg_recovery_days"] * s["total_ead"] for s in inventory_segments
        ) / inv_ead if inv_ead else 0

    overview = {
        "snapshot_date": date.today().isoformat(),
        "scenario_name": "customer_import",
        "data_source": "customer_import",
        "source_batch_id": batches[0].id,
        "source_batch_ids": [batch.id for batch in batches],
        "source_filename": batches[0].filename,
        "source_filenames": [batch.filename for batch in batches],
        "total_ead": round(total_ead, 2),
        "total_asset_count": len(rows),
        "total_expected_loss": round(total_loss, 2),
        "total_expected_loss_rate": round(total_loss / total_ead, 4) if total_ead else 0,
        "cash_30d": round(total_cash_30, 2),
        "cash_90d": round(total_cash_90, 2),
        "cash_180d": round(total_cash_180, 2),
        "recovered_rate": round(recovered_count / len(rows), 4) if rows else 0,
        "in_inventory_rate": round(inventory_count / len(rows), 4) if rows else 0,
        "avg_inventory_days": round(avg_inventory_days, 1),
        "high_risk_segment_count": high_risk,
        "provision_impact": round(total_loss * 0.015, 2),
        "capital_release_score": round(max(0, min(100, 100 - (total_loss / total_ead * 100 if total_ead else 0))), 1),
    }
    return {"overview": overview, "segments": segments}


def generate_empty_portfolio() -> dict:
    """Return an explicit empty state after customer data is cleared."""
    overview = {
        "snapshot_date": date.today().isoformat(),
        "scenario_name": "empty",
        "data_source": "empty",
        "source_batch_id": None,
        "source_batch_ids": [],
        "source_filename": None,
        "source_filenames": [],
        "total_ead": 0,
        "total_asset_count": 0,
        "total_expected_loss": 0,
        "total_expected_loss_rate": 0,
        "cash_30d": 0,
        "cash_90d": 0,
        "cash_180d": 0,
        "recovered_rate": 0,
        "in_inventory_rate": 0,
        "avg_inventory_days": 0,
        "high_risk_segment_count": 0,
        "provision_impact": 0,
        "capital_release_score": 0,
    }
    return {"overview": overview, "segments": []}


# ============ Mock组合生成 ============

def generate_mock_portfolio(org_id: str = "default") -> dict:
    """生成Mock公司级资产组合，返回 {overview, segments}"""
    random.seed(42)
    today = date.today()

    segments = []
    total_ead = 0
    total_count = 0
    total_loss = 0

    for bi, bucket in enumerate(OVERDUE_BUCKETS):
        for status in RECOVERED_STATUSES:
            count = max(2, 80 - bi * 12 - (0 if status == "未收回" else 15) + random.randint(-5, 5))
            avg_ead = random.uniform(60000, 180000)
            segment_ead = count * avg_ead

            dep_factor = 1 - bi * 0.06
            avg_vv = avg_ead * random.uniform(0.5, 0.8) * dep_factor

            base_lgd = 0.30 + bi * 0.08
            if status == "已入库":
                base_lgd -= 0.10
            elif status == "未收回":
                base_lgd += 0.10
            lgd = min(0.95, max(0.10, base_lgd + random.uniform(-0.05, 0.05)))

            loss_amount = segment_ead * lgd

            base_days = 30 + bi * 20
            if status == "已入库":
                base_days = max(7, base_days - 30)
            elif status == "未收回":
                base_days += 45
            recovery_days = base_days + random.randint(-10, 15)

            nr = 1 - lgd
            if status == "已入库":
                c30, c90, c180 = nr * 0.50, nr * 0.80, nr * 0.95
            elif status == "已收回未入库":
                c30, c90, c180 = nr * 0.20, nr * 0.55, nr * 0.80
            else:
                c30, c90, c180 = nr * 0.05, nr * 0.20, nr * 0.50

            if bi >= 4 and status == "已入库":
                rec = "bulk_clearance"
            elif status in ("已入库", "已收回未入库"):
                rec = "retail_auction"
            elif bi <= 1:
                rec = "collection"
            elif bi <= 3:
                rec = "litigation"
            else:
                rec = "debt_transfer"

            segments.append({
                "segment_name": f"{bucket} | {status}",
                "overdue_bucket": bucket,
                "recovered_status": status,
                "asset_count": count,
                "total_ead": round(segment_ead, 2),
                "avg_vehicle_value": round(avg_vv, 2),
                "avg_lgd": round(lgd, 4),
                "avg_recovery_days": recovery_days,
                "expected_loss_amount": round(loss_amount, 2),
                "expected_loss_rate": round(lgd, 4),
                "cash_30d": round(segment_ead * c30, 2),
                "cash_90d": round(segment_ead * c90, 2),
                "cash_180d": round(segment_ead * c180, 2),
                "recommended_strategy": rec,
            })
            total_ead += segment_ead
            total_count += count
            total_loss += loss_amount

    t_cash_30 = sum(s["cash_30d"] for s in segments)
    t_cash_90 = sum(s["cash_90d"] for s in segments)
    t_cash_180 = sum(s["cash_180d"] for s in segments)
    recovered = sum(s["asset_count"] for s in segments if s["recovered_status"] != "未收回")
    inv = sum(s["asset_count"] for s in segments if s["recovered_status"] == "已入库")
    hr = sum(1 for s in segments if s["expected_loss_rate"] > 0.60)

    overview = {
        "snapshot_date": today.isoformat(),
        "scenario_name": "baseline",
        "total_ead": round(total_ead, 2),
        "total_asset_count": total_count,
        "total_expected_loss": round(total_loss, 2),
        "total_expected_loss_rate": round(total_loss / total_ead, 4) if total_ead else 0,
        "cash_30d": round(t_cash_30, 2),
        "cash_90d": round(t_cash_90, 2),
        "cash_180d": round(t_cash_180, 2),
        "recovered_rate": round(recovered / total_count, 4) if total_count else 0,
        "in_inventory_rate": round(inv / total_count, 4) if total_count else 0,
        "avg_inventory_days": round(random.uniform(25, 55), 1),
        "high_risk_segment_count": hr,
        "provision_impact": round(total_loss * 0.015, 2),
        "capital_release_score": round(random.uniform(35, 65), 1),
    }
    return {"overview": overview, "segments": segments}


# ============ 路径模拟 ============

def compute_strategy_comparison(segment: dict, funding_rate: float = 0.08) -> list:
    """为一个分层计算所有处置路径对比"""
    ead = segment["total_ead"]
    count = segment["asset_count"]
    bi = _bucket_index(segment.get("overdue_bucket", "M3(61-90天)"))
    status = segment.get("recovered_status", "未收回")
    results = []

    for stype, sname in STRATEGY_TYPES.items():
        p = STRATEGY_PROFILES[stype]
        sr = p["success_rate_base"]
        nr = []
        if bi >= 4:
            sr *= 0.7
        if status == "已入库" and stype in ("retail_auction", "vehicle_transfer", "bulk_clearance"):
            sr = min(0.98, sr * 1.2)
        if status == "未收回" and stype in ("retail_auction", "vehicle_transfer"):
            sr *= 0.5
        if segment.get("debtor_dishonest_enforced") and stype == "collection":
            sr = 0.0
            nr.append("司法数据提示债务人为失信被执行人，继续催收等待还款路径被否决")

        rr = p["recovery_rate"] * (0.85 if bi >= 4 else 1.0)
        gross = ead * rr * sr

        towing = ead * 0.02 if stype in ("retail_auction", "vehicle_transfer", "bulk_clearance") and status == "未收回" else 0
        inv_cost = count * 30 * min(p["avg_recovery_days"], 90) if stype in ("retail_auction", "litigation") else 0
        legal = ead * 0.06 if stype in ("litigation", "special_procedure") else 0
        channel = gross * 0.05 if stype in ("retail_auction", "debt_transfer", "vehicle_transfer") else 0
        fund = ead * funding_rate * p["avg_recovery_days"] / 365
        mgmt = ead * 0.01
        total_cost = towing + inv_cost + legal + channel + fund + mgmt

        net = gross - total_cost
        loss_amt = ead - net
        lr = loss_amt / ead if ead else 0
        cap = max(0, min(100, (1 - lr) * 80 + (1 / max(p["avg_recovery_days"], 1)) * 2000))

        # —— 物权占有/入库门禁 ——
        # 未收回分层：没有占有，一切需要车在手的路径都不可行
        if status == "未收回":
            if stype in ("retail_auction", "vehicle_transfer", "bulk_clearance"):
                nr.append("车辆尚未收回，无法上架处置")
            if stype == "special_procedure":
                nr.append(
                    "实现担保物权特别程序要求债权人已取得担保物占有，车辆未收回不可用"
                )
        # 已收回但未入库：虽有事实占有，但缺少入库凭证/车辆定位/照片等证据链，
        # 法院立案时难以证明"已占有担保物"；业务实践是入库后再提交特别程序申请。
        # 因此此状态下仍屏蔽 special_procedure；
        # 批量出清/资产包转让同理（都需入库台账才能对外处置/交付）。
        elif status == "已收回未入库":
            if stype == "special_procedure":
                nr.append(
                    "实现担保物权特别程序需已入库备案以证明占有，"
                    "车辆已收回但未入库，请先完成入库登记后再申请"
                )
            if stype in ("vehicle_transfer", "bulk_clearance"):
                nr.append("现车转让/批量出清需完成入库登记后方可操作")
        if bi <= 1 and stype in ("debt_transfer", "bulk_clearance"):
            nr.append("逾期时间较短，催收仍有机会")
        if bi <= 1 and stype == "special_procedure":
            nr.append("实现担保物权特别程序仅适用于至少M3以上逾期资产，M1-M2阶段不应直接启动")
        if sr < 0.2:
            nr.append("成功概率过低")

        rn = []
        if p["avg_recovery_days"] > 180:
            rn.append("回款周期超180天，资金占用大")
        if lr > 0.7:
            rn.append("预计损失率超70%")

        results.append({
            "strategy_type": stype,
            "strategy_name": sname,
            "success_probability": round(sr, 4),
            "expected_recovery_gross": round(gross, 2),
            "total_cost": round(total_cost, 2),
            "net_recovery_pv": round(net, 2),
            "expected_loss_amount": round(loss_amt, 2),
            "expected_loss_rate": round(lr, 4),
            "expected_recovery_days": p["avg_recovery_days"],
            "capital_release_score": round(cap, 1),
            "cost_breakdown": {
                "towing": round(towing, 2),
                "inventory": round(inv_cost, 2),
                "legal": round(legal, 2),
                "channel_fee": round(channel, 2),
                "funding_cost": round(fund, 2),
                "management": round(mgmt, 2),
            },
            "risk_notes": rn,
            "not_recommended_reasons": nr,
        })

    # 2026-04-22 产品决策：不再对路径做"推荐"排序 —— 纯按净回收 PV 降序展示。
    # 被物权/入库等硬约束限制的路径依然在列表中，由前端通过 not_recommended_reasons
    # 显示"约束提示"，让使用者自己综合判断。
    results.sort(key=lambda x: x["net_recovery_pv"], reverse=True)
    return results


# ============ 现金回流 ============

def compute_cashflow_projection(segments: list, strategies_by_segment: Optional[dict] = None) -> dict:
    """计算现金回流投影"""
    if strategies_by_segment is None:
        strategies_by_segment = {}

    def scenario_band(cash_in: float, cash_out: float) -> dict:
        neutral = cash_in - cash_out
        pessimistic = cash_in * 0.82 - cash_out * 1.08
        optimistic = cash_in * 1.10 - cash_out * 0.95
        return {
            "pessimistic_net_cash_flow": round(pessimistic, 2),
            "neutral_net_cash_flow": round(neutral, 2),
            "optimistic_net_cash_flow": round(optimistic, 2),
        }

    bucket_days = [7, 30, 60, 90, 180, 360]
    by_strategy = {}
    by_segment_cf = []

    for seg in segments:
        sname = seg["segment_name"]
        stype = strategies_by_segment.get(sname, seg.get("recommended_strategy", "collection"))
        p = STRATEGY_PROFILES.get(stype, STRATEGY_PROFILES["collection"])

        ead = seg["total_ead"]
        total_rec = ead * p["recovery_rate"] * p["success_rate_base"]
        avg_d = p["avg_recovery_days"]

        buckets = []
        for bd in bucket_days:
            progress = min(1.0, bd / (avg_d * 1.5))
            cum_in = total_rec * progress
            cum_out = ead * p["cost_rate"] * min(1.0, bd / (avg_d * 0.8))
            buckets.append({
                "bucket_day": bd,
                "gross_cash_in": round(cum_in, 2),
                "gross_cash_out": round(cum_out, 2),
                "net_cash_flow": round(cum_in - cum_out, 2),
                **scenario_band(cum_in, cum_out),
            })

        by_segment_cf.append({
            "segment_name": sname,
            "buckets": buckets,
            "total_net_cash": round(total_rec - ead * p["cost_rate"], 2),
        })

        if stype not in by_strategy:
            by_strategy[stype] = {
                "strategy_type": stype,
                "strategy_name": STRATEGY_TYPES.get(stype, stype),
                "buckets": [
                    {
                        "bucket_day": bd,
                        "gross_cash_in": 0,
                        "gross_cash_out": 0,
                        "net_cash_flow": 0,
                        "pessimistic_net_cash_flow": 0,
                        "neutral_net_cash_flow": 0,
                        "optimistic_net_cash_flow": 0,
                    }
                    for bd in bucket_days
                ],
                "total_net_cash": 0,
            }
        for i in range(len(bucket_days)):
            by_strategy[stype]["buckets"][i]["gross_cash_in"] += buckets[i]["gross_cash_in"]
            by_strategy[stype]["buckets"][i]["gross_cash_out"] += buckets[i]["gross_cash_out"]
            by_strategy[stype]["buckets"][i]["net_cash_flow"] += buckets[i]["net_cash_flow"]
            by_strategy[stype]["buckets"][i]["pessimistic_net_cash_flow"] += buckets[i]["pessimistic_net_cash_flow"]
            by_strategy[stype]["buckets"][i]["neutral_net_cash_flow"] += buckets[i]["neutral_net_cash_flow"]
            by_strategy[stype]["buckets"][i]["optimistic_net_cash_flow"] += buckets[i]["optimistic_net_cash_flow"]
        by_strategy[stype]["total_net_cash"] += total_rec - ead * p["cost_rate"]

    # round strategy values
    for st in by_strategy.values():
        st["total_net_cash"] = round(st["total_net_cash"], 2)
        for b in st["buckets"]:
            for k in (
                "gross_cash_in",
                "gross_cash_out",
                "net_cash_flow",
                "pessimistic_net_cash_flow",
                "neutral_net_cash_flow",
                "optimistic_net_cash_flow",
            ):
                b[k] = round(b[k], 2)

    # total buckets
    total_buckets = []
    for i, bd in enumerate(bucket_days):
        ti = sum(s["buckets"][i]["gross_cash_in"] for s in by_segment_cf)
        to = sum(s["buckets"][i]["gross_cash_out"] for s in by_segment_cf)
        total_buckets.append({
            "bucket_day": bd,
            "gross_cash_in": round(ti, 2),
            "gross_cash_out": round(to, 2),
            "net_cash_flow": round(ti - to, 2),
            **scenario_band(ti, to),
        })

    total_ead = sum(s["total_ead"] for s in segments)
    cash_360 = total_buckets[5]["net_cash_flow"] if len(total_buckets) > 5 else 0
    long_tail = max(0, total_ead - cash_360)

    return {
        "total_buckets": total_buckets,
        "by_strategy": list(by_strategy.values()),
        "by_segment": by_segment_cf[:10],
        "total_long_tail": round(long_tail, 2),
        "cash_return_rate": round(cash_360 / total_ead, 4) if total_ead else 0,
    }


# ============ 角色建议 ============

def generate_role_recommendations(overview: dict, segments: list, role_level: str = "executive") -> list:
    """根据角色生成建议"""
    if not segments and overview.get("data_source") == "empty":
        return [
            {
                "role_level": role_level,
                "recommendation_title": "暂无活跃组合数据",
                "recommendation_text": "当前组合分析数据源已清空，请在数据接入中心上传新的资产/逾期台账后再查看分析建议。",
                "expected_impact": {},
                "feasibility_score": 1,
                "realism_score": 1,
                "priority": 1,
                "approval_needed": False,
            }
        ]

    recs = []
    lr = overview.get("total_expected_loss_rate", 0)
    loss_sorted = sorted(segments, key=lambda s: s["expected_loss_amount"], reverse=True)

    if role_level == "executive":
        if lr > 0.50:
            j, jt = "RED", "整体损失率超50%，经营压力极大，需立即启动应急处置方案"
        elif lr > 0.35:
            j, jt = "YELLOW", "整体损失率偏高，需加速处置并控制新增不良"
        else:
            j, jt = "GREEN", "整体损失率可控，保持当前处置节奏，关注高风险分层"

        recs.append({
            "role_level": "executive",
            "recommendation_title": f"本月经营判断: {j}",
            "recommendation_text": jt,
            "expected_impact": {"loss_reduction": "整体"},
            "feasibility_score": 0.9, "realism_score": 0.9,
            "priority": 1, "approval_needed": False,
        })

        if loss_sorted:
            top = loss_sorted[0]
            pct = top["expected_loss_amount"] / overview["total_expected_loss"] * 100 if overview["total_expected_loss"] else 0
            recs.append({
                "role_level": "executive",
                "recommendation_title": f"优先处置: {top['segment_name']}",
                "recommendation_text": f"该分层预计损失{top['expected_loss_amount']:,.0f}元，占总损失{pct:.1f}%，建议优先配置资源",
                "expected_impact": {"loss_reduction": f"{top['expected_loss_amount']:,.0f}元"},
                "feasibility_score": 0.8, "realism_score": 0.85,
                "priority": 2, "approval_needed": True,
            })

        inv_segs = [s for s in segments if s["recovered_status"] == "已入库"]
        if inv_segs:
            inv_ead = sum(s["total_ead"] for s in inv_segs)
            recs.append({
                "role_level": "executive",
                "recommendation_title": "加速库存出清",
                "recommendation_text": f"在库资产余额{inv_ead:,.0f}元，建议加速竞拍/零售出清，减少贬值和资金占用",
                "expected_impact": {"cashflow_boost": f"30天内回收{inv_ead*0.3:,.0f}元"},
                "feasibility_score": 0.85, "realism_score": 0.8,
                "priority": 2, "approval_needed": False,
            })

        m4p = [s for s in segments if any(x in s.get("overdue_bucket", "") for x in ("M4", "M5", "M6"))]
        if m4p:
            # 特别程序的物权前提是债权人已占有且有入库证据链，只对"已入库"分层提。
            # 已收回未入库：先催入库；未收回：先催收车/普通诉讼保全。
            m4p_inv = [s for s in m4p if s.get("recovered_status") == "已入库"]
            m4p_recovered_not_inv = [s for s in m4p if s.get("recovered_status") == "已收回未入库"]
            m4p_not_recovered = [s for s in m4p if s.get("recovered_status") == "未收回"]
            inv_count = sum(s["asset_count"] for s in m4p_inv)
            rec_not_inv_count = sum(s["asset_count"] for s in m4p_recovered_not_inv)
            not_rec_count = sum(s["asset_count"] for s in m4p_not_recovered)

            if inv_count:
                recs.append({
                    "role_level": "executive",
                    "recommendation_title": "评估法务资源配置（已入库部分）",
                    "recommendation_text": (
                        f"M4+已入库共{inv_count}笔，可直接走担保物权特别程序，"
                        f"需评估法务承载力以缩短回款周期"
                    ),
                    "expected_impact": {"recovery_days_reduction": "预计缩短60-120天"},
                    "feasibility_score": 0.7, "realism_score": 0.75,
                    "priority": 3, "approval_needed": True,
                })
            if rec_not_inv_count:
                recs.append({
                    "role_level": "executive",
                    "recommendation_title": "加速M4+已收回资产入库登记",
                    "recommendation_text": (
                        f"M4+已收回未入库共{rec_not_inv_count}笔，缺入库证据链"
                        f"不可直接走特别程序；建议优先完成入库登记后再申请"
                    ),
                    "expected_impact": {"recovery_days_reduction": "完成入库后可立即启动特别程序"},
                    "feasibility_score": 0.8, "realism_score": 0.8,
                    "priority": 3, "approval_needed": False,
                })
            if not_rec_count:
                recs.append({
                    "role_level": "executive",
                    "recommendation_title": "加速M4+未收回资产收车",
                    "recommendation_text": (
                        f"M4+未收回共{not_rec_count}笔，无物权占有前提，"
                        f"不可直接走特别程序；建议加大收车资源或启动普通诉讼保全"
                    ),
                    "expected_impact": {"recovery_rate": "提升收车率"},
                    "feasibility_score": 0.65, "realism_score": 0.7,
                    "priority": 3, "approval_needed": True,
                })

    elif role_level == "manager":
        recs.append({
            "role_level": "manager",
            "recommendation_title": "本月现金回流目标",
            "recommendation_text": f"建议目标: {overview['cash_30d']:,.0f}元，基于当前分层结构和处置能力测算",
            "expected_impact": {"cashflow": f"{overview['cash_30d']:,.0f}元"},
            "feasibility_score": 0.75, "realism_score": 0.8,
            "priority": 1, "approval_needed": False,
        })
        for seg in loss_sorted[:3]:
            sn = STRATEGY_TYPES.get(seg.get("recommended_strategy", "collection"), "催收")
            recs.append({
                "role_level": "manager",
                "recommendation_title": f"{seg['segment_name']}: {sn}",
                "recommendation_text": f"该分层{seg['asset_count']}笔，余额{seg['total_ead']:,.0f}元，建议采用{sn}策略",
                "expected_impact": {"loss_reduction": f"预计减损{seg['expected_loss_amount']*0.3:,.0f}元"},
                "feasibility_score": 0.7, "realism_score": 0.75,
                "priority": 2, "approval_needed": False,
            })

    elif role_level == "supervisor":
        for seg in [s for s in segments if s["recovered_status"] == "已入库"][:3]:
            recs.append({
                "role_level": "supervisor",
                "recommendation_title": f"本周推进: {seg['segment_name']}",
                "recommendation_text": f"在库{seg['asset_count']}台，建议本周完成定价和上架准备",
                "expected_impact": {"inventory_reduction": f"{seg['asset_count']}台"},
                "feasibility_score": 0.85, "realism_score": 0.9,
                "priority": 1, "approval_needed": False,
            })

    elif role_level == "operator":
        inv_total = sum(s["asset_count"] for s in segments if s["recovered_status"] == "已入库")
        recs.append({
            "role_level": "operator",
            "recommendation_title": "今日重点: 在库资产估值更新",
            "recommendation_text": f"当前在库{inv_total}台资产需更新估值，优先处理库龄>60天的车辆",
            "expected_impact": {},
            "feasibility_score": 0.95, "realism_score": 0.95,
            "priority": 1, "approval_needed": False,
        })
        m12 = [s for s in segments if ("M1" in s.get("overdue_bucket", "") or "M2" in s.get("overdue_bucket", "")) and s["recovered_status"] == "未收回"]
        if m12:
            recs.append({
                "role_level": "operator",
                "recommendation_title": "催收任务: M1-M2未收回客户跟进",
                "recommendation_text": f"共{sum(s['asset_count'] for s in m12)}笔早期逾期需电话跟进",
                "expected_impact": {},
                "feasibility_score": 0.9, "realism_score": 0.85,
                "priority": 2, "approval_needed": False,
            })

    return recs
