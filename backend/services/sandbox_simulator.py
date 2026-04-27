"""库存决策沙盘 — 五路径模拟引擎

路径A：继续等待赎车
路径B：常规诉讼（一拍80%/二拍56%）
路径C：立即上架竞拍
路径D：实现担保物权特别程序
路径E：分期重组/和解
"""

import math
from typing import Optional

from sqlalchemy.orm import Session

from models.simulation import (
    SandboxInput, SandboxResult,
    PathAResult, TimePoint,
    PathBResult, LitigationScenario, LegalCostDetail, AuctionRound,
    PathCResult,
    PathDResult,
    PathEResult,
)
from services.decision_model import (
    adjusted_duration_days,
    adjusted_towing_cost,
    dynamic_success_probability,
    estimate_depreciation_rate,
    resolve_brand_profile,
    resolve_region_coefficient,
)
from services.model_feedback_service import get_applied_success_adjustment


# ============================================================
# 1. 差异化贬值模型 — 按车辆类型和车龄
# ============================================================

# 月贬值率基准表（来源：二手车市场统计均值）
DEPRECIATION_PROFILES = {
    # vehicle_type: { age_bucket: monthly_rate }
    "luxury": {     # BBA/保时捷/路虎等
        "0-3": 0.025,    # 新车前3年贬值快
        "3-5": 0.018,
        "5-8": 0.012,
        "8+":  0.008,
    },
    "japanese": {   # 丰田/本田/日产等（保值率高）
        "0-3": 0.012,
        "3-5": 0.010,
        "5-8": 0.008,
        "8+":  0.005,
    },
    "german": {     # 大众/斯柯达等非豪华德系
        "0-3": 0.018,
        "3-5": 0.014,
        "5-8": 0.010,
        "8+":  0.007,
    },
    "domestic": {   # 国产品牌
        "0-3": 0.020,
        "3-5": 0.016,
        "5-8": 0.012,
        "8+":  0.008,
    },
    "new_energy": { # 新能源（贬值不均匀，前期快）
        "0-3": 0.028,
        "3-5": 0.022,
        "5-8": 0.015,
        "8+":  0.010,
    },
}

# 从车型描述中推断车辆类型的关键词
VEHICLE_TYPE_KEYWORDS = {
    "luxury": ["宝马", "奔驰", "奥迪", "BMW", "Benz", "Audi", "保时捷", "路虎",
               "捷豹", "雷克萨斯", "凯迪拉克", "林肯", "沃尔沃", "英菲尼迪"],
    "japanese": ["丰田", "本田", "日产", "马自达", "铃木", "斯巴鲁", "三菱",
                 "Toyota", "Honda", "Nissan"],
    "german": ["大众", "斯柯达", "Volkswagen"],
    "new_energy": ["特斯拉", "Tesla", "比亚迪", "BYD", "蔚来", "NIO", "小鹏",
                   "理想", "零跑", "哪吒", "极氪", "EV", "纯电", "插混", "PHEV"],
}

OVERDUE_BUCKET_ORDER = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M6": 6,
}


def _detect_vehicle_type(description: str) -> str:
    """从车型描述自动识别车辆类型"""
    for vtype, keywords in VEHICLE_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in description:
                return vtype
    return "domestic"


def _sunk_cost_excluded(inp: SandboxInput) -> float:
    return max(inp.sunk_collection_cost, 0) + max(inp.sunk_legal_cost, 0)


def _get_age_bucket(age_years: float) -> str:
    if age_years < 3:
        return "0-3"
    elif age_years < 5:
        return "3-5"
    elif age_years < 8:
        return "5-8"
    else:
        return "8+"


def _overdue_stage_rank(overdue_bucket: str) -> int:
    normalized = (overdue_bucket or "").strip().upper()
    for prefix, rank in OVERDUE_BUCKET_ORDER.items():
        if normalized.startswith(prefix):
            return rank
    # 未传或无法识别时保持历史默认：按 M3 处理，避免旧调用被误伤。
    return 3


def _is_m3_or_later(overdue_bucket: str) -> bool:
    return _overdue_stage_rank(overdue_bucket) >= 3


def _special_procedure_block_reasons(inp: SandboxInput) -> list[str]:
    reasons: list[str] = []
    if not inp.vehicle_recovered:
        reasons.append(
            "实现担保物权特别程序要求债权人已取得担保物占有；当前车辆尚未收回，"
            "请先完成收车或改走普通诉讼/保全路径。"
        )
    elif not inp.vehicle_in_inventory:
        reasons.append(
            "实现担保物权特别程序需车辆已入库并形成入库证据链；当前车辆已收回但未入库，"
            "请先完成入库登记后再申请。"
        )
    if not _is_m3_or_later(inp.overdue_bucket):
        reasons.append(
            "实现担保物权特别程序仅适用于至少 M3 以上逾期资产；当前逾期阶段较早，"
            "请优先催收、重组或常规诉讼评估。"
        )
    return reasons


def _collection_block_reasons(inp: SandboxInput) -> list[str]:
    if inp.debtor_dishonest_enforced:
        return [
            "外部司法数据提示债务人为失信被执行人，继续等待赎车路径被系统否决；"
            "建议优先评估诉讼、保全、收车处置或债权转让。"
        ]
    return []


def estimate_depreciation(days: int, vehicle_type: str, vehicle_age_years: float) -> float:
    """计算指定天数后的贬值率（累计）

    Returns: 累计贬值率(0~1)，例如0.05表示贬值5%
    """
    profile = resolve_brand_profile(vehicle_type=vehicle_type)
    return estimate_depreciation_rate(
        days=days,
        vehicle_age_years=vehicle_age_years,
        profile=profile,
    )


# ============================================================
# 2. 法律费用计算器 — 按现行标准
# ============================================================

def calc_court_fee(amount: float) -> float:
    """诉讼费 — 依据《诉讼费用交纳办法》(2007) 财产案件"""
    if amount <= 10000:
        return 50
    elif amount <= 100000:
        return amount * 0.025 - 200
    elif amount <= 200000:
        return amount * 0.02 + 300
    elif amount <= 500000:
        return amount * 0.015 + 1300
    elif amount <= 1000000:
        return amount * 0.01 + 3800
    elif amount <= 2000000:
        return amount * 0.009 + 4800
    elif amount <= 5000000:
        return amount * 0.008 + 6800
    elif amount <= 10000000:
        return amount * 0.007 + 11800
    elif amount <= 20000000:
        return amount * 0.006 + 21800
    else:
        return amount * 0.005 + 41800


def calc_execution_fee(amount: float) -> float:
    """执行费 — 依据《诉讼费用交纳办法》"""
    if amount <= 10000:
        return 50
    elif amount <= 500000:
        return amount * 0.015 - 100
    elif amount <= 5000000:
        return amount * 0.01 + 2400
    elif amount <= 10000000:
        return amount * 0.005 + 27400
    else:
        return amount * 0.001 + 67400


def calc_preservation_fee(amount: float) -> float:
    """保全费 — 依据《诉讼费用交纳办法》"""
    if amount <= 1000:
        return 30
    elif amount <= 100000:
        return amount * 0.01 + 20
    elif amount <= 200000:
        return amount * 0.005 + 520
    else:
        return min(amount * 0.001 + 1320, 5000)


def calc_special_procedure_fee() -> float:
    """实现担保物权特别程序申请费 — 非财产案件标准"""
    return 500


def build_legal_cost(
    amount: float,
    lawyer_fee_fixed: float,
    has_recovery_fee: bool,
    recovery_fee_rate: float,
    expected_recovery: float,
    is_special_procedure: bool = False,
) -> LegalCostDetail:
    """构建法律费用明细"""
    if is_special_procedure:
        court_fee = calc_special_procedure_fee()
        execution_fee = calc_execution_fee(amount)
        preservation_fee = 0  # 特别程序一般不需保全
    else:
        court_fee = calc_court_fee(amount)
        execution_fee = calc_execution_fee(amount)
        preservation_fee = calc_preservation_fee(amount)

    recovery_lawyer = expected_recovery * recovery_fee_rate if has_recovery_fee else 0

    total = court_fee + execution_fee + preservation_fee + lawyer_fee_fixed + recovery_lawyer

    return LegalCostDetail(
        court_fee=round(court_fee, 2),
        execution_fee=round(execution_fee, 2),
        preservation_fee=round(preservation_fee, 2),
        lawyer_fee_fixed=round(lawyer_fee_fixed, 2),
        lawyer_fee_recovery=round(recovery_lawyer, 2),
        total_legal_cost=round(total, 2),
    )


# ============================================================
# 3. 路径A：继续等待赎车（15/30/60/90天）
# ============================================================

def simulate_path_a(
    inp: SandboxInput,
    session: Optional[Session] = None,
    learning_adjustment: float = 0.0,
) -> PathAResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    profile = resolve_brand_profile(
        session=session,
        vehicle_type=vtype,
        car_description=inp.car_description,
    )
    region = resolve_region_coefficient(
        session=session, province=inp.province, city=inp.city
    )
    sunk = _sunk_cost_excluded(inp)
    collection_block_reasons = _collection_block_reasons(inp)
    timepoints = []

    for days in [15, 30, 60, 90]:
        parking = inp.daily_parking * days
        interest = inp.overdue_amount * (inp.annual_interest_rate / 100) * (days / 365)
        dep_rate = estimate_depreciation_rate(
            days=days,
            vehicle_age_years=inp.vehicle_age_years,
            profile=profile,
        )
        depreciated = inp.che300_value * (1 - dep_rate)
        dep_amount = inp.che300_value - depreciated
        holding_cost = parking + interest + inp.recovery_cost
        shrinkage = holding_cost + dep_amount
        net_pos = depreciated - inp.overdue_amount - holding_cost
        success_probability = dynamic_success_probability(
            base_probability=0.25,
            vehicle_age_years=inp.vehicle_age_years,
            overdue_amount=inp.overdue_amount,
            vehicle_value=inp.che300_value,
            profile=profile,
            region=region,
            path_type="collection",
            vehicle_recovered=inp.vehicle_recovered,
            vehicle_in_inventory=inp.vehicle_in_inventory,
            learning_adjustment=learning_adjustment,
        )
        if collection_block_reasons:
            success_probability = 0

        timepoints.append(TimePoint(
            days=days,
            accumulated_parking=round(parking, 2),
            accumulated_interest=round(interest, 2),
            depreciated_value=round(depreciated, 2),
            depreciation_amount=round(dep_amount, 2),
            total_holding_cost=round(holding_cost, 2),
            total_shrinkage=round(shrinkage, 2),
            net_position=round(net_pos, 2),
            success_probability=success_probability,
            future_marginal_net_benefit=round(net_pos, 2),
            sunk_cost_excluded=round(sunk, 2),
        ))

    best = max(timepoints, key=lambda tp: tp.future_marginal_net_benefit)
    result = PathAResult(
        timepoints=timepoints,
        success_probability=best.success_probability,
        learning_success_adjustment=round(learning_adjustment, 4),
        learning_adjustment_applied=not collection_block_reasons and abs(learning_adjustment) > 0,
        future_marginal_net_benefit=best.future_marginal_net_benefit,
        sunk_cost_excluded=round(sunk, 2),
    )
    if collection_block_reasons:
        result.available = False
        result.unavailable_reason = " ".join(collection_block_reasons)
    return result


# ============================================================
# 4. 路径B：常规诉讼（一拍80%/二拍56%）
# ============================================================

def simulate_path_b(
    inp: SandboxInput,
    session: Optional[Session] = None,
    learning_adjustment: float = 0.0,
) -> PathBResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    profile = resolve_brand_profile(
        session=session,
        vehicle_type=vtype,
        car_description=inp.car_description,
    )
    region = resolve_region_coefficient(
        session=session, province=inp.province, city=inp.city
    )
    sunk = _sunk_cost_excluded(inp)

    # 常规诉讼时间线：立案→审理→判决→执行→拍卖
    # 最优6个月，预期9个月，最差14个月
    scenario_configs = [
        ("最优情况(一拍成交)", 6, 0.80, 0.70),     # 一拍成交，成功率70%
        ("预期情况(二拍成交)", 9, 0.56, 0.85),     # 二拍成交，累计成功率85%
        ("最差情况(流拍后协商)", 14, 0.45, 0.50),   # 流拍后协商处置，成功率50%
    ]

    scenarios = []

    # 先算法律费用（固定部分）
    # 回款比例律师费在每个情景中根据实际回款额计算
    base_legal = build_legal_cost(
        amount=inp.overdue_amount,
        lawyer_fee_fixed=inp.litigation_lawyer_fee,
        has_recovery_fee=False,  # 先不算回款比例
        recovery_fee_rate=0,
        expected_recovery=0,
        is_special_procedure=False,
    )

    for label, months, auction_discount, base_success_prob in scenario_configs:
        days = adjusted_duration_days(
            months * 30,
            region=region,
            path_type="litigation",
        )
        duration_months = max(1, math.ceil(days / 30))
        parking = inp.daily_parking * days
        interest = inp.overdue_amount * (inp.annual_interest_rate / 100) * (days / 365)
        dep_rate = estimate_depreciation_rate(
            days=days,
            vehicle_age_years=inp.vehicle_age_years,
            profile=profile,
        )
        depreciated = inp.che300_value * (1 - dep_rate)
        success_prob = dynamic_success_probability(
            base_probability=base_success_prob,
            vehicle_age_years=inp.vehicle_age_years,
            overdue_amount=inp.overdue_amount,
            vehicle_value=inp.che300_value,
            profile=profile,
            region=region,
            path_type="litigation",
            vehicle_recovered=inp.vehicle_recovered,
            vehicle_in_inventory=inp.vehicle_in_inventory,
            learning_adjustment=learning_adjustment,
        )

        # 期望拍卖回收 = 贬值后估值 × 拍卖折扣 × 动态成功概率
        auction_price = depreciated * auction_discount * success_prob

        # 回款比例律师费
        recovery_lawyer_fee = auction_price * inp.litigation_recovery_fee_rate if inp.litigation_has_recovery_fee else 0

        legal_cost = LegalCostDetail(
            court_fee=base_legal.court_fee,
            execution_fee=base_legal.execution_fee,
            preservation_fee=base_legal.preservation_fee,
            lawyer_fee_fixed=base_legal.lawyer_fee_fixed,
            lawyer_fee_recovery=round(recovery_lawyer_fee, 2),
            total_legal_cost=round(
                base_legal.court_fee + base_legal.execution_fee +
                base_legal.preservation_fee + base_legal.lawyer_fee_fixed +
                recovery_lawyer_fee, 2
            ),
        )

        # 拍卖轮次明细
        rounds = []
        if auction_discount >= 0.80:
            rounds.append(AuctionRound(
                round_name="一拍", discount_rate=0.80,
                auction_price=round(depreciated * 0.80, 2),
                success_probability=success_prob,
            ))
        if auction_discount <= 0.56 or duration_months >= 9:
            rounds.append(AuctionRound(
                round_name="一拍", discount_rate=0.80,
                auction_price=round(depreciated * 0.80, 2),
                success_probability=min(0.98, round(success_prob * 0.85, 4)),
            ))
            rounds.append(AuctionRound(
                round_name="二拍", discount_rate=0.56,
                auction_price=round(depreciated * 0.56, 2),
                success_probability=success_prob,
            ))

        recovery_cost = adjusted_towing_cost(inp.recovery_cost, region)
        total_cost = legal_cost.total_legal_cost + parking + interest + recovery_cost
        net = auction_price - total_cost

        scenarios.append(LitigationScenario(
            label=label,
            duration_months=duration_months,
            duration_days=days,
            legal_cost=legal_cost,
            parking_cost=round(parking, 2),
            interest_cost=round(interest, 2),
            recovery_cost=round(recovery_cost, 2),
            auction_rounds=rounds,
            expected_auction_price=round(auction_price, 2),
            total_cost=round(total_cost, 2),
            net_recovery=round(net, 2),
            success_probability=success_prob,
            future_marginal_net_benefit=round(net, 2),
            sunk_cost_excluded=round(sunk, 2),
        ))

    expected = scenarios[1] if len(scenarios) > 1 else scenarios[0]
    return PathBResult(
        legal_cost=base_legal,
        scenarios=scenarios,
        success_probability=expected.success_probability,
        learning_success_adjustment=round(learning_adjustment, 4),
        learning_adjustment_applied=abs(learning_adjustment) > 0,
        future_marginal_net_benefit=expected.future_marginal_net_benefit,
        sunk_cost_excluded=round(sunk, 2),
    )


# ============================================================
# 5. 路径C：立即上架竞拍
# ============================================================

def simulate_path_c(
    inp: SandboxInput,
    session: Optional[Session] = None,
    learning_adjustment: float = 0.0,
) -> PathCResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    profile = resolve_brand_profile(
        session=session,
        vehicle_type=vtype,
        car_description=inp.car_description,
    )
    region = resolve_region_coefficient(
        session=session, province=inp.province, city=inp.city
    )
    sunk = _sunk_cost_excluded(inp)

    sale_days = adjusted_duration_days(
        inp.expected_sale_days,
        region=region,
        path_type="retail_auction",
    )
    dep_rate = estimate_depreciation_rate(
        days=sale_days,
        vehicle_age_years=inp.vehicle_age_years,
        profile=profile,
    )
    sale_price = inp.che300_value * (1 - dep_rate) * 0.90  # 竞拍成交约市价90%
    success_probability = dynamic_success_probability(
        base_probability=0.80,
        vehicle_age_years=inp.vehicle_age_years,
        overdue_amount=inp.overdue_amount,
        vehicle_value=inp.che300_value,
        profile=profile,
        region=region,
        path_type="retail_auction",
        vehicle_recovered=inp.vehicle_recovered,
        vehicle_in_inventory=inp.vehicle_in_inventory,
        learning_adjustment=learning_adjustment,
    )
    expected_sale_recovery = sale_price * success_probability
    commission = expected_sale_recovery * inp.commission_rate
    parking = inp.daily_parking * sale_days
    recovery_cost = adjusted_towing_cost(inp.recovery_cost, region)
    net = expected_sale_recovery - commission - parking - recovery_cost

    result = PathCResult(
        expected_sale_days=sale_days,
        sale_price=round(sale_price, 2),
        commission=round(commission, 2),
        parking_during_sale=round(parking, 2),
        recovery_cost=round(recovery_cost, 2),
        net_recovery=round(net, 2),
        success_probability=success_probability,
        learning_success_adjustment=round(learning_adjustment, 4),
        learning_adjustment_applied=inp.vehicle_recovered and abs(learning_adjustment) > 0,
        future_marginal_net_benefit=round(net, 2),
        sunk_cost_excluded=round(sunk, 2),
    )

    if not inp.vehicle_recovered:
        result.available = False
        result.unavailable_reason = "车辆尚未回收，无法上架竞拍。请先完成收车再评估此路径。"

    return result


# ============================================================
# 6. 路径D：实现担保物权特别程序
# ============================================================

def simulate_path_d(
    inp: SandboxInput,
    session: Optional[Session] = None,
    learning_adjustment: float = 0.0,
) -> PathDResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    profile = resolve_brand_profile(
        session=session,
        vehicle_type=vtype,
        car_description=inp.car_description,
    )
    region = resolve_region_coefficient(
        session=session, province=inp.province, city=inp.city
    )
    sunk = _sunk_cost_excluded(inp)
    d_block_reasons = _special_procedure_block_reasons(inp)

    # 特别程序：通常2-3个月完成，此处取3个月
    days = adjusted_duration_days(90, region=region, path_type="special_procedure")
    duration_months = max(1, math.ceil(days / 30))
    parking = inp.daily_parking * days
    interest = inp.overdue_amount * (inp.annual_interest_rate / 100) * (days / 365)
    dep_rate = estimate_depreciation_rate(
        days=days,
        vehicle_age_years=inp.vehicle_age_years,
        profile=profile,
    )
    depreciated = inp.che300_value * (1 - dep_rate)

    # 拍卖：同样一拍80%/二拍56%
    # 特别程序效率更高，多数一拍成交
    round1_price = depreciated * 0.80
    round2_price = depreciated * 0.56
    round1_success = dynamic_success_probability(
        base_probability=0.70,
        vehicle_age_years=inp.vehicle_age_years,
        overdue_amount=inp.overdue_amount,
        vehicle_value=inp.che300_value,
        profile=profile,
        region=region,
        path_type="special_procedure",
        vehicle_recovered=inp.vehicle_recovered,
        vehicle_in_inventory=inp.vehicle_in_inventory,
        learning_adjustment=learning_adjustment,
    )
    round2_success = dynamic_success_probability(
        base_probability=0.85,
        vehicle_age_years=inp.vehicle_age_years,
        overdue_amount=inp.overdue_amount,
        vehicle_value=inp.che300_value,
        profile=profile,
        region=region,
        path_type="special_procedure",
        vehicle_recovered=inp.vehicle_recovered,
        vehicle_in_inventory=inp.vehicle_in_inventory,
        learning_adjustment=learning_adjustment,
    )
    if d_block_reasons:
        round1_success = 0
        round2_success = 0

    expected_price = (
        round1_price * round1_success
        + round2_price * (1 - round1_success) * round2_success
    )
    combined_success = round(
        round1_success + (1 - round1_success) * round2_success,
        4,
    )

    legal_cost = build_legal_cost(
        amount=inp.overdue_amount,
        lawyer_fee_fixed=inp.special_lawyer_fee,
        has_recovery_fee=inp.special_has_recovery_fee,
        recovery_fee_rate=inp.special_recovery_fee_rate,
        expected_recovery=expected_price,
        is_special_procedure=True,
    )

    rounds = [
        AuctionRound(
            round_name="一拍", discount_rate=0.80,
            auction_price=round(round1_price, 2),
            success_probability=round1_success,
        ),
        AuctionRound(
            round_name="二拍", discount_rate=0.56,
            auction_price=round(round2_price, 2),
            success_probability=round2_success,
        ),
    ]

    recovery_cost = adjusted_towing_cost(inp.recovery_cost, region)
    total_cost = legal_cost.total_legal_cost + parking + interest + recovery_cost
    net = expected_price - total_cost

    result = PathDResult(
        duration_months=duration_months,
        duration_days=days,
        legal_cost=legal_cost,
        parking_cost=round(parking, 2),
        interest_cost=round(interest, 2),
        recovery_cost=round(recovery_cost, 2),
        auction_rounds=rounds,
        expected_auction_price=round(expected_price, 2),
        total_cost=round(total_cost, 2),
        net_recovery=round(net, 2),
        success_probability=combined_success,
        learning_success_adjustment=round(learning_adjustment, 4),
        learning_adjustment_applied=not d_block_reasons and abs(learning_adjustment) > 0,
        future_marginal_net_benefit=round(net, 2),
        sunk_cost_excluded=round(sunk, 2),
    )

    if d_block_reasons:
        result.available = False
        result.unavailable_reason = " ".join(d_block_reasons)
        result.success_probability = 0

    return result


# ============================================================
# 7. 路径E：分期重组/和解
# ============================================================

def simulate_path_e(
    inp: SandboxInput,
    session: Optional[Session] = None,
    learning_adjustment: float = 0.0,
) -> PathEResult:
    monthly = inp.restructure_monthly_payment
    months = inp.restructure_months
    redefault = inp.restructure_redefault_rate
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    profile = resolve_brand_profile(
        session=session,
        vehicle_type=vtype,
        car_description=inp.car_description,
    )
    region = resolve_region_coefficient(
        session=session, province=inp.province, city=inp.city
    )
    sunk = _sunk_cost_excluded(inp)

    if monthly <= 0:
        # 如果用户没填重组方案，默认按逾期金额/12测算
        monthly = inp.overdue_amount / 12

    total_recovery = monthly * months
    # 风险调整：考虑再违约率
    # 假设违约发生在平均一半时间点
    risk_adjusted = total_recovery * (1 - redefault) + (monthly * months * 0.5) * redefault
    # 持有成本：重组期间无停车费（车在客户手中），但有管理成本
    management_cost = months * 200  # 月均管理成本200元
    holding_cost = management_cost
    net = risk_adjusted - holding_cost
    success_probability = dynamic_success_probability(
        base_probability=max(0, 1 - redefault),
        vehicle_age_years=inp.vehicle_age_years,
        overdue_amount=inp.overdue_amount,
        vehicle_value=inp.che300_value,
        profile=profile,
        region=region,
        path_type="restructure",
        vehicle_recovered=inp.vehicle_recovered,
        vehicle_in_inventory=inp.vehicle_in_inventory,
        learning_adjustment=learning_adjustment,
    )

    return PathEResult(
        monthly_payment=round(monthly, 2),
        total_months=months,
        total_expected_recovery=round(total_recovery, 2),
        redefault_rate=redefault,
        risk_adjusted_recovery=round(risk_adjusted, 2),
        holding_cost=round(holding_cost, 2),
        net_recovery=round(net, 2),
        success_probability=success_probability,
        learning_success_adjustment=round(learning_adjustment, 4),
        learning_adjustment_applied=abs(learning_adjustment) > 0,
        future_marginal_net_benefit=round(net, 2),
        sunk_cost_excluded=round(sunk, 2),
    )


# ============================================================
# 8. 综合决策
# ============================================================

def run_simulation(
    inp: SandboxInput,
    session: Optional[Session] = None,
    tenant_id: Optional[int] = None,
) -> SandboxResult:
    """运行完整五路径模拟"""
    # 自动检测车辆类型
    if inp.vehicle_type == "auto":
        inp.vehicle_type = _detect_vehicle_type(inp.car_description)

    def learning_adjustment_for(path_type: str) -> float:
        return get_applied_success_adjustment(
            session,
            tenant_id=tenant_id,
            strategy_path=path_type,
        )

    path_a = simulate_path_a(
        inp,
        session=session,
        learning_adjustment=learning_adjustment_for("collection"),
    )
    path_b = simulate_path_b(
        inp,
        session=session,
        learning_adjustment=learning_adjustment_for("litigation"),
    )
    path_c = simulate_path_c(
        inp,
        session=session,
        learning_adjustment=learning_adjustment_for("retail_auction"),
    )
    path_d = simulate_path_d(
        inp,
        session=session,
        learning_adjustment=learning_adjustment_for("special_procedure"),
    )
    path_e = simulate_path_e(
        inp,
        session=session,
        learning_adjustment=learning_adjustment_for("restructure"),
    )

    # ---- 决策对比 ----
    # A: 取15/30/60/90天中最优的净头寸
    a_values = {tp.days: tp.future_marginal_net_benefit for tp in path_a.timepoints}
    a_best_days = max(a_values, key=a_values.get)
    a_best = a_values[a_best_days]

    # B: 取预期情况（二拍成交）
    b_value = path_b.future_marginal_net_benefit

    # C: 直接竞拍
    c_value = path_c.future_marginal_net_benefit

    # D: 特别程序
    d_value = path_d.future_marginal_net_benefit

    # E: 重组
    e_value = path_e.future_marginal_net_benefit

    # 构建候选路径集合；不满足硬前提的路径不能进入推荐候选。
    candidate_paths: dict[str, float] = {
        "B": b_value,
        "E": e_value,
    }
    if path_a.available:
        candidate_paths["A"] = a_best
    if path_c.available:
        candidate_paths["C"] = c_value
    if path_d.available:
        candidate_paths["D"] = d_value

    # 保留所有路径数值用于对比展示
    paths = {"A": a_best, "B": b_value, "C": c_value, "D": d_value, "E": e_value}
    best_path = max(candidate_paths, key=candidate_paths.get)
    best_value = candidate_paths[best_path]

    # 生成建议文本
    path_names = {
        "A": "继续等待赎车",
        "B": "常规诉讼",
        "C": "立即上架竞拍",
        "D": "实现担保物权特别程序",
        "E": "分期重组/和解",
    }

    unavailable_notes = []
    if not path_a.available:
        unavailable_notes.append(f"路径 A 不可选：{path_a.unavailable_reason}")
    if not path_c.available:
        unavailable_notes.append(f"路径 C 不可选：{path_c.unavailable_reason}")
    if not path_d.available:
        unavailable_notes.append(f"路径 D 不可选：{path_d.unavailable_reason}")
    header = ""
    if unavailable_notes:
        header = "（" + "；".join(unavailable_notes) + " 已从决策候选中自动排除。）\n"
    lines = [
        header
        + f"综合对比可用路径，推荐【{path_names[best_path]}】"
        + f"（未来边际净收益¥{best_value:,.0f}）。\n"
    ]

    if best_path == "C":
        lines.append(
            f"立即竞拍可在{path_c.expected_sale_days}天内回款，"
            f"成交价¥{path_c.sale_price:,.0f}，扣除佣金和停车费后"
            f"未来边际净收益¥{c_value:,.0f}。"
        )
        if path_d.available and d_value > b_value:
            lines.append(
                f"若竞拍不可行，次优选择为担保物权特别程序"
                f"（未来边际净收益¥{d_value:,.0f}，约{path_d.duration_months}个月）。"
            )
    elif best_path == "D":
        lines.append(
            f"特别程序约3个月完成，预计拍卖回收¥{path_d.expected_auction_price:,.0f}，"
            f"扣除法律费用¥{path_d.legal_cost.total_legal_cost:,.0f}等成本后"
            f"未来边际净收益¥{d_value:,.0f}。"
        )
        lines.append(f"相比常规诉讼（未来边际净收益¥{b_value:,.0f}）缩短周期6个月以上。")
    elif best_path == "B":
        lines.append(
            f"常规诉讼预期情况下未来边际净收益¥{b_value:,.0f}，"
            f"但周期约9个月且不确定性较大。"
        )
        if path_d.available and d_value > 0:
            lines.append(
                f"建议评估是否可走担保物权特别程序"
                f"（未来边际净收益¥{d_value:,.0f}，约{path_d.duration_months}个月）。"
            )
    elif best_path == "A":
        lines.append(
            f"在{a_best_days}天等待窗口内未来边际净收益最优（¥{a_best:,.0f}），"
            f"但需密切关注贬值，超过{a_best_days}天建议转为处置。"
        )
    elif best_path == "E":
        lines.append(
            f"重组方案月还¥{path_e.monthly_payment:,.0f}×{path_e.total_months}期，"
            f"考虑{path_e.redefault_rate:.0%}再违约率后未来边际净收益¥{e_value:,.0f}。"
        )
        lines.append("需评估借款人还款意愿和能力，再违约风险不可忽视。")

    # 对比摘要
    lines.append("\n各路径对比：")
    sorted_paths = sorted(paths.items(), key=lambda x: x[1], reverse=True)
    for i, (p, v) in enumerate(sorted_paths):
        marker = " <-- 推荐" if p == best_path else ""
        lines.append(f"  {path_names[p]}：¥{v:,.0f}{marker}")

    recommendation = "\n".join(lines)

    return SandboxResult(
        input=inp,
        path_a=path_a,
        path_b=path_b,
        path_c=path_c,
        path_d=path_d,
        path_e=path_e,
        recommendation=recommendation,
        best_path=best_path,
    )
