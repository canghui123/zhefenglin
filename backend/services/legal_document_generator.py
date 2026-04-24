"""Rule-based legal document generator.

The first commercial-ready version intentionally keeps generation template
driven. It gives operators a fast draft while preserving a clear human-review
boundary for legal use.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models.legal_document import LegalDocumentGenerateRequest, LegalDocumentResult


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"

DOCUMENT_META = {
    "civil_complaint": {
        "title": "民事起诉状",
        "template": "legal_civil_complaint.html",
    },
    "preservation_application": {
        "title": "财产保全申请书",
        "template": "legal_preservation_application.html",
    },
    "special_procedure_application": {
        "title": "实现担保物权特别程序申请书",
        "template": "legal_special_procedure_application.html",
    },
}

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True),
)


def _format_money(value: float | None) -> str:
    if value is None:
        return "待核定"
    return f"{value:,.2f}"


def _default_claims(req: LegalDocumentGenerateRequest) -> list[str]:
    overdue_amount = _format_money(req.overdue_amount)
    vehicle_value = _format_money(req.vehicle_value)
    if req.document_type == "civil_complaint":
        return [
            f"请求判令被告偿还逾期债务人民币 {overdue_amount} 元及相应违约金、实现债权费用。",
            "请求确认原告就涉案车辆处置价款在担保范围内享有优先受偿权。",
            "请求判令被告承担本案诉讼费、保全费及其他合理维权费用。",
        ]
    if req.document_type == "preservation_application":
        return [
            f"请求依法查封、扣押或冻结被申请人名下涉案车辆或等值财产，保全金额以人民币 {overdue_amount} 元为限。",
            "请求允许申请人或受托机构协助完成车辆控制、保管和后续价值维护工作。",
        ]
    return [
        f"请求裁定准许拍卖、变卖涉案车辆，并就处置价款在人民币 {overdue_amount} 元债权范围内优先受偿。",
        f"涉案车辆当前参考价值为人民币 {vehicle_value} 元，具体以评估或实际处置结果为准。",
    ]


def _default_facts(req: LegalDocumentGenerateRequest) -> str:
    contract = f"合同编号为 {req.contract_number}。" if req.contract_number else "双方签署了汽车金融相关合同。"
    return (
        f"{req.creditor_name}与{req.debtor_name}存在汽车金融债权债务关系，"
        f"{contract} 债务人未按约履行还款义务，当前逾期金额为人民币 {_format_money(req.overdue_amount)} 元。"
        f"涉案车辆为：{req.car_description}。申请材料由系统根据业务字段生成，提交前需由法务人员复核。"
    )


def _to_plain_text(html: str) -> str:
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def generate_legal_document(req: LegalDocumentGenerateRequest) -> LegalDocumentResult:
    meta = DOCUMENT_META[req.document_type]
    generated_at = datetime.now()
    claims = req.claims or _default_claims(req)
    facts = req.facts.strip() if req.facts else _default_facts(req)
    html = env.get_template(meta["template"]).render(
        title=meta["title"],
        req=req,
        claims=claims,
        facts=facts,
        generated_at=generated_at,
        overdue_amount_text=_format_money(req.overdue_amount),
        vehicle_value_text=_format_money(req.vehicle_value),
    )
    return LegalDocumentResult(
        document_type=req.document_type,
        title=meta["title"],
        html=html,
        plain_text=_to_plain_text(html),
        generated_at=generated_at,
        work_order_id=req.work_order_id,
    )
