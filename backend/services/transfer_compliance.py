"""Asset package transfer compliance checklist scoring."""

from __future__ import annotations

from models.asset import TransferComplianceChecklist, TransferComplianceResult

ITEM_LABELS = {
    "asset_scope_confirmed": "是否符合本机构可转让资产范围",
    "internal_approval_completed": "是否完成内部审批",
    "asset_authenticity_verified": "是否完成资产真实性核验",
    "transfer_restriction_checked": "是否存在禁止转让对象或限制转让情形",
    "pricing_basis_archived": "是否形成估值和定价依据",
    "inquiry_process_recorded": "是否保留询价/竞价过程记录",
    "debtor_notification_arranged": "是否完成债务人通知安排",
    "no_hidden_repurchase_commitment": "是否不存在抽屉协议、回购承诺或隐性兜底风险",
    "archive_completed": "是否完成资料归档",
    "watermark_export_completed": "是否完成导出和报告水印",
}

CRITICAL_ITEMS = {
    "asset_scope_confirmed",
    "internal_approval_completed",
    "asset_authenticity_verified",
    "transfer_restriction_checked",
    "pricing_basis_archived",
    "no_hidden_repurchase_commitment",
}

ARCHIVE_REQUIREMENTS = [
    "资产清单与债权余额表",
    "车300估值与定价计算底稿",
    "询价/竞价过程记录",
    "内部审批记录",
    "债务人通知安排或豁免说明",
    "导出报告水印版本",
]


def assess_transfer_compliance(checklist: TransferComplianceChecklist) -> TransferComplianceResult:
    values = checklist.model_dump()
    missing = [ITEM_LABELS[key] for key, value in values.items() if value is not True]
    completed = len(values) - len(missing)
    score = int(round(completed / len(values) * 100)) if values else 0
    critical_missing = [ITEM_LABELS[key] for key in CRITICAL_ITEMS if values.get(key) is not True]

    if score >= 90 and not critical_missing:
        level = "A"
    elif score >= 75 and len(critical_missing) <= 1:
        level = "B"
    elif score >= 60:
        level = "C"
    else:
        level = "D"

    warnings: list[str] = []
    if critical_missing:
        warnings.append(f"关键合规项未完成：{'、'.join(critical_missing[:3])}")
    if not values.get("watermark_export_completed"):
        warnings.append("导出报告需带租户、用户和时间水印")
    if not values.get("no_hidden_repurchase_commitment"):
        warnings.append("需确认不存在抽屉协议、回购承诺或隐性兜底")

    summary = "合规资料已满足出让归档要求" if level in {"A", "B"} else "合规资料待完善，正式出让前需补齐关键项"

    return TransferComplianceResult(
        compliance_score=max(0, min(score, 100)),
        compliance_level=level,
        checklist=checklist,
        missing_items=missing,
        risk_warnings=warnings,
        archive_requirements=ARCHIVE_REQUIREMENTS,
        summary=summary,
    )
