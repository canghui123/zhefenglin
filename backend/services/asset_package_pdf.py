"""Asset package PDF rendering helpers."""

from __future__ import annotations

from io import BytesIO
from textwrap import wrap

from models.asset import PackageCalculationResult


def _money(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}"


def _percent(value: float | int | None, *, already_percent: bool = False) -> str:
    if value is None:
        return "-"
    shown = value if already_percent else value * 100
    return f"{shown:.1f}%"


def _paragraph_lines(text: str, *, width: int = 54) -> list[str]:
    lines: list[str] = []
    for raw_line in (text or "").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            lines.append("")
            continue
        lines.extend(wrap(raw_line, width=width) or [""])
    return lines


def generate_asset_package_pdf(result: PackageCalculationResult) -> bytes:
    """Render the latest asset package analysis as a real PDF byte stream.

    The project intentionally avoids adding browser automation to the backend.
    ReportLab's built-in CJK CID font keeps the output Chinese-readable without
    shipping font files in the repository.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:  # pragma: no cover - exercised in deployed image
        raise RuntimeError("PDF依赖未安装，请安装 reportlab 后重试") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="资产包出让定价分析报告",
    )
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "CN",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
    )
    title = ParagraphStyle(
        "CNTitle",
        parent=base,
        fontSize=18,
        leading=24,
        spaceAfter=8,
    )
    heading = ParagraphStyle(
        "CNHeading",
        parent=base,
        fontSize=13,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )

    story = [
        Paragraph("资产包出让定价分析报告", title),
        Paragraph(
            "本报告基于上传台账、车300估值、资产包类型和补录字段生成，供出让方沟通与复核使用。",
            base,
        ),
        Spacer(1, 6),
    ]

    summary = result.summary
    summary_rows = [
        ["资产数量", str(summary.total_assets), "资产包类型", summary.asset_package_type],
        ["本金合计", _money(summary.total_principal), "车300估值合计", _money(summary.total_vehicle_valuation)],
        ["交易适配度", f"{summary.tradeability_level} / {summary.tradeability_score}分", "估值数据覆盖率", _percent(summary.valuation_coverage_rate, already_percent=True)],
        [
            "推荐出让价",
            f"{_money(summary.recommended_transfer_price_low)} - {_money(summary.recommended_transfer_price_high)}",
            "中位折扣",
            _percent(summary.recommended_discount_mid),
        ],
        [
            "本金中位回收率",
            _percent(summary.principal_recovery_rate_mid),
            "抵押物价值覆盖率",
            _percent(summary.collateral_coverage_ratio),
        ],
    ]
    table = Table(summary_rows, colWidths=[28 * mm, 55 * mm, 30 * mm, 55 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f3f4f6")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([table, Spacer(1, 8)])

    if summary.risk_alerts:
        story.append(Paragraph("风险预警", heading))
        for alert in summary.risk_alerts:
            story.append(Paragraph(f"- {alert}", base))

    if summary.tradeability_summary:
        story.append(Paragraph("交易适配度", heading))
        story.append(
            Paragraph(
                f"{summary.tradeability_level}级 / {summary.tradeability_score}分：{summary.tradeability_summary}",
                base,
            )
        )
        for item in summary.tradeability_recommendations:
            story.append(Paragraph(f"- {item}", base))

    if summary.buyer_offer_analysis:
        offer = summary.buyer_offer_analysis
        story.append(Paragraph("买方报价对比与谈判建议", heading))
        gap_rate = _percent(offer.buyer_offer_gap_rate) if offer.buyer_offer_gap_rate is not None else "-"
        discount = _percent(offer.buyer_offer_discount) if offer.buyer_offer_discount is not None else "-"
        story.append(
            Paragraph(
                f"买方报价：{_money(offer.buyer_offer_price)}；差距：{_money(offer.buyer_offer_gap)} / {gap_rate}；报价折扣：{discount}。",
                base,
            )
        )
        story.append(Paragraph(f"判断：{offer.buyer_offer_assessment}", base))
        for suggestion in offer.negotiation_suggestions:
            story.append(Paragraph(f"- {suggestion}", base))

    story.append(Paragraph("分析报告正文", heading))
    for line in _paragraph_lines(summary.analysis_report):
        story.append(Paragraph(line or "&nbsp;", base))

    story.extend([PageBreak(), Paragraph("逐车定价明细", heading)])
    detail_rows = [["行号", "车型", "本金", "估值", "可信度", "推荐出让价区间", "风险标签"]]
    for asset in result.assets:
        detail_rows.append(
            [
                str(asset.row_number),
                asset.car_description[:32],
                _money(asset.loan_principal),
                _money(asset.che300_valuation),
                f"{asset.valuation_confidence_level}/{asset.valuation_confidence_score}",
                f"{_money(asset.recommended_transfer_price_low)} - {_money(asset.recommended_transfer_price_high)}",
                "；".join(asset.risk_flags)[:42],
            ]
        )

    detail_table = Table(
        detail_rows,
        repeatRows=1,
        colWidths=[12 * mm, 38 * mm, 23 * mm, 23 * mm, 20 * mm, 36 * mm, 34 * mm],
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(detail_table)

    doc.build(story)
    return buffer.getvalue()
