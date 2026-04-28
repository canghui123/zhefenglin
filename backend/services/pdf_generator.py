"""PDF报告生成 — 使用Jinja2 HTML模板（五路径版）"""

import os
from datetime import date

from jinja2 import Environment, FileSystemLoader

from models.simulation import SandboxResult
from services.llm_client import chat_completion

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

VEHICLE_TYPE_LABELS = {
    "luxury": "豪华品牌(BBA/保时捷等)",
    "japanese": "日系(丰田/本田等)",
    "german": "德系非豪华(大众等)",
    "domestic": "国产品牌",
    "new_energy": "新能源",
    "auto": "自动识别",
}


def _get_template_env():
    return Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


async def generate_report_html(result: SandboxResult) -> str:
    """生成报告HTML内容"""
    analysis = await _generate_analysis(result)

    env = _get_template_env()
    template = env.get_template("vehicle_report.html")

    # 路径A最优净头寸
    a_values = {tp.days: tp.net_position for tp in result.path_a.timepoints}
    path_a_best_value = max(a_values.values()) if a_values else 0

    # 路径B预期值（二拍成交）
    path_b_expected_value = (
        result.path_b.scenarios[1].net_recovery
        if len(result.path_b.scenarios) > 1
        else 0
    )

    html = template.render(
        report_date=date.today().strftime("%Y年%m月%d日"),
        car_description=result.input.car_description,
        entry_date=result.input.entry_date,
        overdue_bucket=result.input.overdue_bucket,
        overdue_amount=f"{result.input.overdue_amount:,.0f}",
        che300_value=f"{result.input.che300_value:,.0f}",
        vehicle_type_label=VEHICLE_TYPE_LABELS.get(
            result.input.vehicle_type, result.input.vehicle_type
        ),
        vehicle_age_years=result.input.vehicle_age_years,
        vehicle_recovered_status="已收回" if result.input.vehicle_recovered else "未收回",
        vehicle_inventory_status="已入库" if result.input.vehicle_in_inventory else "未入库",
        recovery_cost=f"{result.input.recovery_cost:,.0f}",
        auction_discount_rate=result.path_c.auction_discount_rate,
        path_a=result.path_a,
        path_a_best_value=path_a_best_value,
        path_b=result.path_b,
        path_b_expected_value=path_b_expected_value,
        path_c=result.path_c,
        path_d=result.path_d,
        path_e=result.path_e,
        best_path=result.best_path,
        recommendation=result.recommendation,
        analysis=analysis,
    )
    return html


async def _generate_analysis(result: SandboxResult) -> str:
    """调用LLM生成专业分析文本"""
    system = (
        "你是一位汽车金融不良资产处置专家。请根据以下量化分析数据，"
        "撰写一份专业、有说服力的分析摘要（2-3段，约300字）。"
        "语气专业但易懂，结论明确。"
    )

    path_a_90 = next(
        (tp for tp in result.path_a.timepoints if tp.days == 90), None
    )
    path_b_exp = (
        result.path_b.scenarios[1] if len(result.path_b.scenarios) > 1 else None
    )

    user = f"""车辆信息：{result.input.car_description}
入库日期：{result.input.entry_date}
逾期金额：{result.input.overdue_amount:.0f}元
当前车300估值：{result.input.che300_value:.0f}元
车辆类型：{VEHICLE_TYPE_LABELS.get(result.input.vehicle_type, result.input.vehicle_type)}
车龄：{result.input.vehicle_age_years}年

五条路径分析结果：
路径A（等待赎车90天）：净头寸{path_a_90.net_position:.0f}元，资产缩水{path_a_90.total_shrinkage:.0f}元
路径B（常规诉讼预期9个月）：净回收{path_b_exp.net_recovery:.0f}元，法律费用{path_b_exp.legal_cost.total_legal_cost:.0f}元
路径C（立即竞拍{result.path_c.expected_sale_days}天）：净回款{result.path_c.net_recovery:.0f}元
路径D（担保物权特别程序约3个月）：净回收{result.path_d.net_recovery:.0f}元，法律费用{result.path_d.legal_cost.total_legal_cost:.0f}元
路径E（分期重组{result.path_e.total_months}期）：净回收{result.path_e.net_recovery:.0f}元，再违约率{result.path_e.redefault_rate:.0%}

系统推荐：路径{result.best_path}

请撰写专业分析摘要。"""

    return await chat_completion(system, user, temperature=0.5, max_tokens=800)
