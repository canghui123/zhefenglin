"""角色建议引擎 — 基于规则为不同角色生成建议"""

import hashlib
import random
from datetime import date, timedelta
from typing import Optional

from services.portfolio_engine import (
    generate_role_recommendations,
    STRATEGY_TYPES,
)


def get_executive_dashboard(overview: dict, segments: list) -> dict:
    """生成高管驾驶页数据"""
    recommendations = generate_role_recommendations(overview, segments, "executive")
    if not segments and overview.get("data_source") == "empty":
        return {
            "overview": overview,
            "loss_contribution_by_segment": [],
            "resource_suggestions": ["请先在数据接入中心上传新的资产/逾期台账"],
            "approval_items": [],
            "recommendations": recommendations,
        }

    loss_sorted = sorted(segments, key=lambda s: s["expected_loss_amount"], reverse=True)
    loss_contribution = []
    for seg in loss_sorted[:10]:
        pct = seg["expected_loss_amount"] / overview["total_expected_loss"] * 100 if overview["total_expected_loss"] else 0
        loss_contribution.append({
            "segment_name": seg["segment_name"],
            "loss_amount": round(seg["expected_loss_amount"], 2),
            "loss_rate": round(seg["expected_loss_rate"], 4),
            "contribution_pct": round(pct, 2),
            "cash_30d": round(seg["cash_30d"], 2),
        })

    inv_count = sum(s["asset_count"] for s in segments if s["recovered_status"] == "已入库")
    not_rec = sum(s["asset_count"] for s in segments if s["recovered_status"] == "未收回")

    resource_suggestions = []
    if not_rec > inv_count * 2:
        resource_suggestions.append("建议增配收车团队资源，未收回车辆是已入库的2倍以上")
    m4p = [s for s in segments if any(x in s.get("overdue_bucket", "") for x in ("M4", "M5", "M6"))]
    if sum(s["asset_count"] for s in m4p) > 50:
        resource_suggestions.append("建议增加法务预算，M4+资产超50笔需加速法务推进")
    if inv_count > 30:
        resource_suggestions.append("建议优先出清长库龄库存，减少贬值和资金占用")
    resource_suggestions.append("建议评估竞拍渠道承接能力，确保出清节奏匹配")

    approval_items = []
    if overview.get("total_expected_loss", 0) > 5000000:
        approval_items.append("预计总损失超500万，建议启动专项处置方案审批")
    if len(m4p) > 5:
        approval_items.append("M4+分层数量较多，建议审批批量法务推进方案")

    return {
        "overview": overview,
        "loss_contribution_by_segment": loss_contribution,
        "resource_suggestions": resource_suggestions,
        "approval_items": approval_items,
        "recommendations": recommendations,
    }


def get_manager_playbook(overview: dict, segments: list) -> dict:
    """生成经理作战手册"""
    recommendations = generate_role_recommendations(overview, segments, "manager")
    if not segments and overview.get("data_source") == "empty":
        return {
            "recommendations": recommendations,
            "kpis": [],
            "weekly_rhythm": [],
        }

    kpis = [
        {
            "name": "现金回流目标",
            "recommended_value": round(overview["cash_30d"], 2),
            "unit": "元/月",
            "historical_avg": round(overview["cash_30d"] * 0.85, 2),
            "achievable_value": round(overview["cash_30d"] * 0.95, 2),
            "risk_note": "需确保竞拍渠道畅通",
        },
        {
            "name": "收车率目标",
            "recommended_value": round(overview.get("recovered_rate", 0) + 0.05, 4),
            "unit": "%",
            "historical_avg": round(overview.get("recovered_rate", 0), 4),
            "achievable_value": round(overview.get("recovered_rate", 0) + 0.03, 4),
            "risk_note": "GPS离线车辆拖回难度大",
        },
        {
            "name": "库存压降目标",
            "recommended_value": 15,
            "unit": "台/月",
            "historical_avg": 10,
            "achievable_value": 12,
            "risk_note": "需评估渠道承接能力",
        },
    ]

    weekly_rhythm = [
        {"week": 1, "focus": "筛选与启动", "actions": ["完成分层分析", "确定处置优先级", "分配任务"]},
        {"week": 2, "focus": "重点推进", "actions": ["推进高优先级收车", "法务资料准备", "在库资产定价"]},
        {"week": 3, "focus": "法务/竞拍/出清", "actions": ["法务案件提交", "竞拍上架", "长库龄出清"]},
        {"week": 4, "focus": "冲刺/纠偏/复盘", "actions": ["目标冲刺", "偏差分析", "下月计划"]},
    ]

    return {
        "recommendations": recommendations,
        "kpis": kpis,
        "weekly_rhythm": weekly_rhythm,
    }


def get_supervisor_console(overview: dict, segments: list) -> dict:
    """生成主管执行控制台"""
    recommendations = generate_role_recommendations(overview, segments, "supervisor")
    if not segments and overview.get("data_source") == "empty":
        return {
            "recommendations": recommendations,
            "high_priority_pool": [],
        }

    high_priority_pool = []
    for seg in sorted(segments, key=lambda s: s["expected_loss_amount"], reverse=True)[:5]:
        high_priority_pool.append({
            "segment_name": seg["segment_name"],
            "status": seg["recovered_status"],
            "next_action": STRATEGY_TYPES.get(seg.get("recommended_strategy", "collection"), "催收"),
            "urgency": "高" if seg["expected_loss_rate"] > 0.5 else "中",
            "loss_impact": round(seg["expected_loss_amount"], 2),
            "cash_impact": round(seg["cash_30d"], 2),
        })

    return {
        "recommendations": recommendations,
        "high_priority_pool": high_priority_pool,
    }


def get_action_center(overview: dict, segments: list) -> dict:
    """生成动作中心（执行层）"""
    recommendations = generate_role_recommendations(overview, segments, "operator")
    if not segments and overview.get("data_source") == "empty":
        return {
            "recommendations": recommendations,
            "auction_ready": [],
            "recovery_tasks": [],
        }

    inv_segs = [s for s in segments if s["recovered_status"] == "已入库"]
    auction_ready = []
    for seg in inv_segs[:5]:
        auction_ready.append({
            "segment_name": seg["segment_name"],
            "count": seg["asset_count"],
            "estimated_value": round(seg["avg_vehicle_value"] * seg["asset_count"], 2),
            "recommended_floor_price": round(seg["avg_vehicle_value"] * 0.85, 2),
            "risk_tags": ["库龄偏长"] if seg.get("avg_recovery_days", 0) > 60 else [],
        })

    recovery_segs = [s for s in segments if s["recovered_status"] == "未收回"]
    recovery_tasks = []
    for seg in recovery_segs[:5]:
        recovery_tasks.append({
            "segment_name": seg["segment_name"],
            "count": seg["asset_count"],
            "overdue_bucket": seg["overdue_bucket"],
            "total_ead": round(seg["total_ead"], 2),
        })

    return {
        "recommendations": recommendations,
        "auction_ready": auction_ready,
        "recovery_tasks": recovery_tasks,
    }


def _seed_for_segment(segment_name: str, order_type: str) -> int:
    raw = f"{segment_name}:{order_type}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:12], 16)


def _overdue_day_floor(overdue_bucket: str) -> int:
    if overdue_bucket.startswith("M1"):
        return 1
    if overdue_bucket.startswith("M2"):
        return 31
    if overdue_bucket.startswith("M3"):
        return 61
    if overdue_bucket.startswith("M4"):
        return 91
    if overdue_bucket.startswith("M5"):
        return 121
    return 151


def _default_work_order_days(overdue_bucket: str) -> int:
    if overdue_bucket.startswith(("M5", "M6")):
        return 5
    if overdue_bucket.startswith("M4"):
        return 7
    return 10


def find_segment_by_name(segments: list[dict], segment_name: str) -> Optional[dict]:
    return next((seg for seg in segments if seg["segment_name"] == segment_name), None)


def build_action_work_order_candidates(
    segment: dict,
    *,
    order_type: str,
) -> dict:
    """Build deterministic asset-level candidates for action-center work orders.

    当前组合驾驶舱仍由分层级数据驱动；这里先把分层展开为稳定的候选资产清单，
    保持前端和工单 payload 契约，后续可无缝替换为真实资产台账查询。
    """
    count = max(int(segment.get("asset_count", 0)), 0)
    overdue_bucket = segment.get("overdue_bucket", "M3(61-90天)")
    recovered_status = segment.get("recovered_status", "未收回")
    per_ead = segment.get("total_ead", 0) / count if count else 0
    avg_vehicle_value = segment.get("avg_vehicle_value", 0)
    today = date.today()
    imported_assets = segment.get("assets") or []
    if imported_assets:
        candidates = []
        for idx, asset in enumerate(imported_assets):
            vehicle_value = max(20_000, float(asset.get("vehicle_value") or avg_vehicle_value or 0))
            overdue_amount = max(5_000, float(asset.get("loan_principal") or asset.get("overdue_amount") or per_ead or 0))
            overdue_days = int(asset.get("overdue_days") or _overdue_day_floor(overdue_bucket))
            risk_tags = []
            if overdue_days >= 120:
                risk_tags.append("高逾期")
            if recovered_status == "未收回":
                risk_tags.append("待收车")
            if segment.get("avg_recovery_days", 0) > 60:
                risk_tags.append("长周期")
            if not asset.get("gps_last_seen") and recovered_status == "未收回":
                risk_tags.append("缺GPS")

            candidates.append(
                {
                    "asset_identifier": asset.get("asset_identifier") or f"IMPORT-{idx + 1:04d}",
                    "contract_number": asset.get("contract_number") or "",
                    "debtor_name": asset.get("debtor_name") or "",
                    "car_description": asset.get("car_description") or "未命名车辆",
                    "license_plate": asset.get("license_plate") or "",
                    "vin": asset.get("vin") or "",
                    "province": asset.get("province") or "",
                    "city": asset.get("city") or "",
                    "overdue_bucket": overdue_bucket,
                    "overdue_days": overdue_days,
                    "overdue_amount": round(overdue_amount, 2),
                    "vehicle_value": round(vehicle_value, 2),
                    "recovered_status": recovered_status,
                    "gps_last_seen": asset.get("gps_last_seen") or "",
                    "risk_tags": risk_tags,
                    "default_towing_commission": round(max(1200, min(6000, vehicle_value * 0.025)), 2),
                    "default_work_order_days": _default_work_order_days(overdue_bucket),
                    "default_starting_price": round(vehicle_value * 0.85, 2),
                    "default_reserve_price": round(vehicle_value * 0.78, 2),
                    "default_auction_start_at": (today + timedelta(days=1)).isoformat(),
                    "default_auction_end_at": (today + timedelta(days=8)).isoformat(),
                }
            )
        return {
            "order_type": order_type,
            "segment_name": segment["segment_name"],
            "segment_count": count,
            "total_ead": round(segment.get("total_ead", 0), 2),
            "candidates": candidates,
        }

    rng = random.Random(_seed_for_segment(segment["segment_name"], order_type))
    overdue_floor = _overdue_day_floor(overdue_bucket)
    provinces = [("江苏省", "南京市"), ("浙江省", "杭州市"), ("广东省", "广州市"), ("四川省", "成都市")]
    vehicle_models = [
        "丰田 凯美瑞 2021款",
        "大众 迈腾 2020款",
        "比亚迪 汉EV 2022款",
        "宝马 3系 2020款",
        "本田 雅阁 2021款",
        "特斯拉 Model 3 2021款",
    ]

    candidates = []
    for idx in range(count):
        province, city = provinces[idx % len(provinces)]
        vehicle_value = max(20_000, avg_vehicle_value * rng.uniform(0.82, 1.18))
        overdue_amount = max(5_000, per_ead * rng.uniform(0.75, 1.25))
        overdue_days = overdue_floor + rng.randint(0, 28)
        gps_days = rng.randint(1, 18)
        risk_tags = []
        if overdue_days >= 120:
            risk_tags.append("高逾期")
        if recovered_status == "未收回":
            risk_tags.append("待收车")
        if segment.get("avg_recovery_days", 0) > 60:
            risk_tags.append("长周期")

        candidates.append(
            {
                "asset_identifier": f"AF-{overdue_bucket[:2]}-{idx + 1:04d}",
                "contract_number": f"HT{today:%Y%m}{idx + 1001}",
                "debtor_name": f"客户{idx + 1:03d}",
                "car_description": vehicle_models[idx % len(vehicle_models)],
                "license_plate": f"苏A{rng.randint(10000, 99999)}",
                "vin": f"LFP{rng.randint(10**12, 10**13 - 1)}",
                "province": province,
                "city": city,
                "overdue_bucket": overdue_bucket,
                "overdue_days": overdue_days,
                "overdue_amount": round(overdue_amount, 2),
                "vehicle_value": round(vehicle_value, 2),
                "recovered_status": recovered_status,
                "gps_last_seen": (today - timedelta(days=gps_days)).isoformat(),
                "risk_tags": risk_tags,
                "default_towing_commission": round(max(1200, min(6000, vehicle_value * 0.025)), 2),
                "default_work_order_days": _default_work_order_days(overdue_bucket),
                "default_starting_price": round(vehicle_value * 0.85, 2),
                "default_reserve_price": round(vehicle_value * 0.78, 2),
                "default_auction_start_at": (today + timedelta(days=1)).isoformat(),
                "default_auction_end_at": (today + timedelta(days=8)).isoformat(),
            }
        )

    return {
        "order_type": order_type,
        "segment_name": segment["segment_name"],
        "segment_count": count,
        "total_ead": round(segment.get("total_ead", 0), 2),
        "candidates": candidates,
    }
