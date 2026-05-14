"""Legal feasibility scoring for sandbox litigation and special procedure paths."""

from __future__ import annotations

from models.simulation import LegalMaterialStatus, LegalPathAssessment, SandboxInput


MATERIAL_LABELS = {
    "loan_contract": "借款合同",
    "mortgage_contract": "抵押合同/担保合同",
    "mortgage_registration": "抵押登记证明",
    "overdue_statement": "逾期明细",
    "repayment_records": "还款流水",
    "debtor_identity": "债务人身份信息",
    "collection_records": "催收记录",
    "vehicle_location_records": "车辆定位记录",
    "inventory_certificate": "收车/入库证明",
    "vehicle_photos": "车辆照片",
    "valuation_report": "车辆估值报告",
    "debt_balance_sheet": "债权余额计算表",
    "guarantor_info": "担保人信息",
    "title_check": "查封/二押/过户核验结果",
    "jurisdiction_clause": "管辖约定",
}


def _overdue_rank(overdue_bucket: str) -> int:
    text = (overdue_bucket or "").strip().upper()
    for idx, prefix in enumerate(["M1", "M2", "M3", "M4", "M5", "M6"], start=1):
        if text.startswith(prefix):
            return idx
    return 3


def _level(score: int) -> str:
    if score >= 80:
        return "suitable"
    if score >= 60:
        return "review_needed"
    if score >= 40:
        return "high_risk"
    return "not_recommended"


def _missing(materials: LegalMaterialStatus, fields: list[str]) -> list[str]:
    gaps: list[str] = []
    for field in fields:
        if not bool(getattr(materials, field)):
            gaps.append(MATERIAL_LABELS[field])
    return gaps


def _recommendation(path: str, score: int, gaps: list[str], risk_tags: list[str]) -> str:
    if score >= 80:
        return "材料和执行条件较完整，可作为优先路径进入业务复核。"
    if score >= 60:
        return f"可尝试，但建议律师复核并补齐{len(gaps)}项材料。"
    if score >= 40:
        return "法律可行性风险较高，建议先补材料或改走更稳妥路径。"
    return "不建议作为当前优先路径，需先完成关键材料和权属核验。"


def assess_special_procedure(inp: SandboxInput) -> LegalPathAssessment:
    materials = inp.legal_materials
    score = 0
    risk_tags: list[str] = []
    gaps: list[str] = []

    if inp.vehicle_recovered:
        score += 15
    else:
        risk_tags.append("vehicle_not_recovered")
        gaps.append("车辆收回或占有证明")

    if inp.vehicle_in_inventory:
        score += 15
    else:
        risk_tags.append("vehicle_not_in_inventory")
        gaps.append("车辆入库证据链")

    if _overdue_rank(inp.overdue_bucket) >= 3:
        score += 10
    else:
        risk_tags.append("overdue_stage_before_m3")
        gaps.append("债权到期或逾期阶段证明")

    if materials.mortgage_registration:
        score += 15
    else:
        risk_tags.append("missing_mortgage_registration")
        gaps.append(MATERIAL_LABELS["mortgage_registration"])

    if materials.loan_contract and materials.mortgage_contract:
        score += 10
    else:
        risk_tags.append("missing_core_contracts")
        gaps.extend(_missing(materials, ["loan_contract", "mortgage_contract"]))

    if materials.debt_matured:
        score += 10
    else:
        risk_tags.append("debt_not_matured")
        gaps.append("债权到期证明")

    if materials.no_substantive_dispute:
        score += 15
    else:
        risk_tags.append("substantive_dispute_risk")

    if materials.no_title_abnormality and materials.title_check:
        score += 10
    else:
        risk_tags.append("title_abnormality_or_unchecked")
        if not materials.title_check:
            gaps.append(MATERIAL_LABELS["title_check"])

    gaps.extend(_missing(materials, ["overdue_statement", "valuation_report", "vehicle_photos"]))
    score = max(0, min(score, 100))
    gaps = list(dict.fromkeys(gaps))
    risk_tags = list(dict.fromkeys(risk_tags))
    return LegalPathAssessment(
        path="special_procedure",
        score=score,
        level=_level(score),
        risk_tags=risk_tags,
        material_gaps=gaps,
        recommendation=_recommendation("special_procedure", score, gaps, risk_tags),
    )


def assess_litigation(inp: SandboxInput) -> LegalPathAssessment:
    materials = inp.legal_materials
    score = 0
    risk_tags: list[str] = []

    if materials.loan_contract:
        score += 15
    if materials.overdue_statement and materials.repayment_records:
        score += 15
    if materials.debtor_identity:
        score += 10
    if materials.mortgage_contract and materials.mortgage_registration:
        score += 15
    if inp.vehicle_recovered or materials.vehicle_location_records:
        score += 10
    if materials.jurisdiction_clause:
        score += 5
    if materials.no_substantive_dispute and materials.no_title_abnormality:
        score += 15
    if materials.collection_records:
        score += 10
    if materials.valuation_report:
        score += 5

    required = [
        "loan_contract",
        "overdue_statement",
        "repayment_records",
        "debtor_identity",
        "mortgage_contract",
        "mortgage_registration",
        "collection_records",
        "valuation_report",
        "debt_balance_sheet",
    ]
    gaps = _missing(materials, required)
    if not (inp.vehicle_recovered or materials.vehicle_location_records):
        risk_tags.append("vehicle_control_uncertain")
        gaps.append(MATERIAL_LABELS["vehicle_location_records"])
    if not materials.jurisdiction_clause:
        risk_tags.append("jurisdiction_clause_missing")
    if not materials.no_substantive_dispute:
        risk_tags.append("substantive_dispute_risk")
    if not materials.no_title_abnormality or not materials.title_check:
        risk_tags.append("title_abnormality_or_unchecked")
        if not materials.title_check:
            gaps.append(MATERIAL_LABELS["title_check"])

    score = max(0, min(score, 100))
    gaps = list(dict.fromkeys(gaps))
    risk_tags = list(dict.fromkeys(risk_tags))
    return LegalPathAssessment(
        path="litigation",
        score=score,
        level=_level(score),
        risk_tags=risk_tags,
        material_gaps=gaps,
        recommendation=_recommendation("litigation", score, gaps, risk_tags),
    )


def assess_legal_paths(inp: SandboxInput) -> tuple[LegalPathAssessment, LegalPathAssessment]:
    return assess_litigation(inp), assess_special_procedure(inp)
