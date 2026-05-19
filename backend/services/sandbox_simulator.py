"""库存决策沙盘 — 五路径模拟引擎

路径A：继续等待赎车
路径B：常规诉讼（一拍80%/二拍56%）
路径C：立即上架竞拍
路径D：实现担保物权特别程序
路径E：分期重组/和解
"""

import math
from datetime import date, timedelta
from models.asset import Asset
from models.simulation import (
    SandboxInput, SandboxResult,
    PathAResult, TimePoint,
    PathBResult, LitigationScenario, LegalCostDetail, AuctionRound,
    PathCResult,
    PathDResult,
    PathEResult,
    PathDecisionScore,
)
from services.legal_path_assessment import assess_legal_paths
from services.market_liquidity import calculate_market_liquidity


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


def _sandbox_asset_for_liquidity(inp: SandboxInput) -> Asset:
    first_registration = date.today() - timedelta(days=int(max(inp.vehicle_age_years, 0) * 365.25))
    return Asset(
        row_number=0,
        car_description=inp.car_description,
        first_registration=first_registration,
        loan_principal=inp.overdue_amount,
        energy_type=inp.energy_type,
        battery_health_score=inp.battery_health_score,
        battery_warranty_valid=inp.battery_warranty_valid,
        operating_vehicle=inp.operating_vehicle,
        ride_hailing_vehicle=inp.ride_hailing_vehicle,
        battery_replacement_history=inp.battery_replacement_history,
        range_km=inp.range_km,
    )


def _sandbox_liquidity(inp: SandboxInput):
    return calculate_market_liquidity(
        _sandbox_asset_for_liquidity(inp),
        valuation_price=inp.che300_value,
        base_expected_sale_days=inp.expected_sale_days,
    )


def _legal_path_duration_multiplier(level: str) -> float:
    if level == "high":
        return 0.95
    if level == "low":
        return 1.08
    if level == "very_low":
        return 1.15
    return 1.0


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


def estimate_depreciation(days: int, vehicle_type: str, vehicle_age_years: float) -> float:
    """计算指定天数后的贬值率（累计）

    Returns: 累计贬值率(0~1)，例如0.05表示贬值5%
    """
    profile = DEPRECIATION_PROFILES.get(vehicle_type, DEPRECIATION_PROFILES["domestic"])
    bucket = _get_age_bucket(vehicle_age_years)
    monthly_rate = profile.get(bucket, 0.015)

    months = days / 30.0
    # 复利贬值
    cumulative = 1 - (1 - monthly_rate) ** months
    return min(cumulative, 0.80)  # 最高贬值80%（残值底线）


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

def simulate_path_a(inp: SandboxInput) -> PathAResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    timepoints = []

    for days in [15, 30, 60, 90]:
        parking = inp.daily_parking * days
        interest = inp.overdue_amount * (inp.annual_interest_rate / 100) * (days / 365)
        dep_rate = estimate_depreciation(days, vtype, inp.vehicle_age_years)
        depreciated = inp.che300_value * (1 - dep_rate)
        dep_amount = inp.che300_value - depreciated
        holding_cost = parking + interest + inp.recovery_cost
        shrinkage = holding_cost + dep_amount
        net_pos = depreciated - inp.overdue_amount - holding_cost

        timepoints.append(TimePoint(
            days=days,
            accumulated_parking=round(parking, 2),
            accumulated_interest=round(interest, 2),
            depreciated_value=round(depreciated, 2),
            depreciation_amount=round(dep_amount, 2),
            total_holding_cost=round(holding_cost, 2),
            total_shrinkage=round(shrinkage, 2),
            net_position=round(net_pos, 2),
        ))

    return PathAResult(timepoints=timepoints)


# ============================================================
# 4. 路径B：常规诉讼（一拍80%/二拍56%）
# ============================================================

def simulate_path_b(inp: SandboxInput) -> PathBResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    liquidity = _sandbox_liquidity(inp)
    duration_multiplier = _legal_path_duration_multiplier(liquidity.level)

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

    for label, months, auction_discount, success_prob in scenario_configs:
        days = int(round(months * 30 * duration_multiplier))
        parking = inp.daily_parking * days
        interest = inp.overdue_amount * (inp.annual_interest_rate / 100) * (days / 365)
        dep_rate = estimate_depreciation(days, vtype, inp.vehicle_age_years)
        depreciated = inp.che300_value * (1 - dep_rate)

        # 拍卖价 = 贬值后估值 × 拍卖折扣
        auction_price = depreciated * auction_discount * (1 + liquidity.adjustment)

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
                auction_price=round(depreciated * 0.80 * (1 + liquidity.adjustment), 2),
                success_probability=0.70,
            ))
        if auction_discount <= 0.56 or months >= 9:
            rounds.append(AuctionRound(
                round_name="一拍", discount_rate=0.80,
                auction_price=round(depreciated * 0.80 * (1 + liquidity.adjustment), 2),
                success_probability=0.70,
            ))
            rounds.append(AuctionRound(
                round_name="二拍", discount_rate=0.56,
                auction_price=round(depreciated * 0.56 * (1 + liquidity.adjustment), 2),
                success_probability=0.85,
            ))

        total_cost = legal_cost.total_legal_cost + parking + interest + inp.recovery_cost
        net = auction_price - total_cost

        scenarios.append(LitigationScenario(
            label=label,
            duration_months=max(1, int(round(days / 30))),
            duration_days=days,
            legal_cost=legal_cost,
            parking_cost=round(parking, 2),
            interest_cost=round(interest, 2),
            recovery_cost=round(inp.recovery_cost, 2),
            auction_rounds=rounds,
            expected_auction_price=round(auction_price, 2),
            total_cost=round(total_cost, 2),
            net_recovery=round(net, 2),
        ))

    return PathBResult(legal_cost=base_legal, scenarios=scenarios)


# ============================================================
# 5. 路径C：立即上架竞拍
# ============================================================

def simulate_path_c(inp: SandboxInput) -> PathCResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    liquidity = _sandbox_liquidity(inp)

    sale_days = liquidity.expected_sale_days_adjusted
    dep_rate = estimate_depreciation(sale_days, vtype, inp.vehicle_age_years)
    sale_price = inp.che300_value * (1 - dep_rate) * 0.90 * (1 + liquidity.adjustment)
    commission = sale_price * inp.commission_rate
    parking = inp.daily_parking * sale_days
    net = sale_price - commission - parking - inp.recovery_cost

    result = PathCResult(
        expected_sale_days=sale_days,
        sale_price=round(sale_price, 2),
        commission=round(commission, 2),
        parking_during_sale=round(parking, 2),
        recovery_cost=round(inp.recovery_cost, 2),
        net_recovery=round(net, 2),
        market_liquidity_score=liquidity.score,
        market_liquidity_level=liquidity.level,
        market_liquidity_adjustment=liquidity.adjustment,
        liquidity_risk_tags=liquidity.liquidity_risk_tags,
        new_energy_risk_tags=liquidity.new_energy_risk_tags,
    )

    if not inp.vehicle_recovered:
        result.available = False
        result.unavailable_reason = "车辆尚未回收，无法上架竞拍。请先完成收车再评估此路径。"

    return result


# ============================================================
# 6. 路径D：实现担保物权特别程序
# ============================================================

def simulate_path_d(inp: SandboxInput) -> PathDResult:
    vtype = inp.vehicle_type if inp.vehicle_type != "auto" else _detect_vehicle_type(inp.car_description)
    liquidity = _sandbox_liquidity(inp)
    duration_multiplier = _legal_path_duration_multiplier(liquidity.level)

    # 特别程序：通常2-3个月完成，此处取3个月
    days = int(round(3 * 30 * duration_multiplier))
    duration_months = max(1, int(round(days / 30)))
    parking = inp.daily_parking * days
    interest = inp.overdue_amount * (inp.annual_interest_rate / 100) * (days / 365)
    dep_rate = estimate_depreciation(days, vtype, inp.vehicle_age_years)
    depreciated = inp.che300_value * (1 - dep_rate)

    # 拍卖：同样一拍80%/二拍56%
    # 特别程序效率更高，多数一拍成交
    round1_price = depreciated * 0.80 * (1 + liquidity.adjustment)
    round2_price = depreciated * 0.56 * (1 + liquidity.adjustment)
    # 加权期望价格：一拍成交率70%，二拍成交率85%
    expected_price = round1_price * 0.70 + round2_price * (1 - 0.70) * 0.85 + 0 * (1 - 0.70) * (1 - 0.85)

    recovery_lawyer_fee = expected_price * inp.special_recovery_fee_rate if inp.special_has_recovery_fee else 0

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
            success_probability=0.70,
        ),
        AuctionRound(
            round_name="二拍", discount_rate=0.56,
            auction_price=round(round2_price, 2),
            success_probability=0.85,
        ),
    ]

    total_cost = legal_cost.total_legal_cost + parking + interest + inp.recovery_cost
    net = expected_price - total_cost

    result = PathDResult(
        duration_months=duration_months,
        duration_days=days,
        legal_cost=legal_cost,
        parking_cost=round(parking, 2),
        interest_cost=round(interest, 2),
        recovery_cost=round(inp.recovery_cost, 2),
        auction_rounds=rounds,
        expected_auction_price=round(expected_price, 2),
        total_cost=round(total_cost, 2),
        net_recovery=round(net, 2),
    )

    d_block_reasons = _special_procedure_block_reasons(inp)
    if d_block_reasons:
        result.available = False
        result.unavailable_reason = " ".join(d_block_reasons)

    return result


# ============================================================
# 7. 路径E：分期重组/和解
# ============================================================

def simulate_path_e(inp: SandboxInput) -> PathEResult:
    monthly = inp.restructure_monthly_payment
    months = inp.restructure_months
    redefault = inp.restructure_redefault_rate

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

    return PathEResult(
        monthly_payment=round(monthly, 2),
        total_months=months,
        total_expected_recovery=round(total_recovery, 2),
        redefault_rate=redefault,
        risk_adjusted_recovery=round(risk_adjusted, 2),
        holding_cost=round(holding_cost, 2),
        net_recovery=round(net, 2),
    )


def _normalize_scores(values: dict[str, float], *, higher_is_better: bool = True) -> dict[str, float]:
    available_values = list(values.values())
    if not available_values:
        return {}
    low = min(available_values)
    high = max(available_values)
    if math.isclose(low, high):
        return {key: 100.0 for key in values}
    scores: dict[str, float] = {}
    for key, value in values.items():
        raw = (value - low) / (high - low) * 100
        scores[key] = raw if higher_is_better else 100 - raw
    return scores


def _decision_weights(preference: str) -> dict[str, float]:
    if preference == "accelerate_cashflow":
        return {"net": 0.30, "time": 0.30, "legal": 0.15, "execution": 0.10, "cashflow": 0.15}
    if preference == "reduce_legal_risk":
        return {"net": 0.30, "time": 0.15, "legal": 0.35, "execution": 0.10, "cashflow": 0.10}
    if preference == "reduce_execution_complexity":
        return {"net": 0.30, "time": 0.15, "legal": 0.20, "execution": 0.25, "cashflow": 0.10}
    return {"net": 0.40, "time": 0.20, "legal": 0.20, "execution": 0.10, "cashflow": 0.10}


def _build_path_decision_scores(
    inp: SandboxInput,
    *,
    path_values: dict[str, float],
    path_days: dict[str, int],
    path_available: dict[str, bool],
    path_unavailable_reasons: dict[str, str],
    litigation_score: int,
    special_score: int,
) -> list[PathDecisionScore]:
    weights = _decision_weights(inp.strategy_preference)
    available_values = {
        key: value for key, value in path_values.items() if path_available.get(key, True)
    }
    available_days = {
        key: value for key, value in path_days.items() if path_available.get(key, True)
    }
    net_scores = _normalize_scores(available_values, higher_is_better=True)
    time_scores = _normalize_scores(available_days, higher_is_better=False)

    legal_scores = {
        "A": 70.0,
        "B": float(litigation_score),
        "C": 85.0 if inp.vehicle_recovered else 0.0,
        "D": float(special_score),
        "E": 75.0,
    }
    execution_scores = {
        "A": 75.0,
        "B": 45.0,
        "C": 85.0 if inp.vehicle_recovered else 0.0,
        "D": 60.0 if inp.vehicle_recovered and inp.vehicle_in_inventory else 0.0,
        "E": 70.0,
    }

    scores: list[PathDecisionScore] = []
    for path in ["A", "B", "C", "D", "E"]:
        available = path_available.get(path, True)
        net = net_scores.get(path, 0.0) if available else 0.0
        time = time_scores.get(path, 0.0) if available else 0.0
        legal = legal_scores[path] if available else 0.0
        execution = execution_scores[path] if available else 0.0
        cashflow = time
        total = (
            net * weights["net"]
            + time * weights["time"]
            + legal * weights["legal"]
            + execution * weights["execution"]
            + cashflow * weights["cashflow"]
        ) if available else 0.0
        scores.append(
            PathDecisionScore(
                path=path,
                score=round(total, 2),
                net_recovery_score=round(net, 2),
                time_score=round(time, 2),
                legal_feasibility_score=round(legal, 2),
                execution_difficulty_score=round(execution, 2),
                cashflow_urgency_score=round(cashflow, 2),
                available=available,
                reason=path_unavailable_reasons.get(path, ""),
            )
        )
    return scores


# ============================================================
# 8. 综合决策
# ============================================================

def run_simulation(inp: SandboxInput) -> SandboxResult:
    """运行完整五路径模拟"""
    # 自动检测车辆类型
    if inp.vehicle_type == "auto":
        inp.vehicle_type = _detect_vehicle_type(inp.car_description)

    path_a = simulate_path_a(inp)
    path_b = simulate_path_b(inp)
    path_c = simulate_path_c(inp)
    path_d = simulate_path_d(inp)
    path_e = simulate_path_e(inp)
    litigation_assessment, special_assessment = assess_legal_paths(inp)
    path_b.legal_assessment = litigation_assessment
    path_d.legal_assessment = special_assessment

    # ---- 决策对比 ----
    # A: 取15/30/60/90天中最优的净头寸
    a_values = {tp.days: tp.net_position for tp in path_a.timepoints}
    a_best_days = max(a_values, key=a_values.get)
    a_best = a_values[a_best_days]

    # B: 取预期情况（二拍成交）
    b_value = path_b.scenarios[1].net_recovery if len(path_b.scenarios) > 1 else 0

    # C: 直接竞拍
    c_value = path_c.net_recovery

    # D: 特别程序
    d_value = path_d.net_recovery

    # E: 重组
    e_value = path_e.net_recovery

    # 保留所有路径数值用于对比展示
    paths = {"A": a_best, "B": b_value, "C": c_value, "D": d_value, "E": e_value}
    path_days = {
        "A": a_best_days,
        "B": path_b.scenarios[1].duration_days if len(path_b.scenarios) > 1 else 270,
        "C": path_c.expected_sale_days,
        "D": path_d.duration_days,
        "E": path_e.total_months * 30,
    }
    path_available = {
        "A": True,
        "B": True,
        "C": path_c.available,
        "D": path_d.available and special_assessment.score >= 40,
        "E": True,
    }
    path_unavailable_reasons = {
        "C": path_c.unavailable_reason if not path_c.available else "",
        "D": (
            path_d.unavailable_reason
            if not path_d.available
            else (
                "特别程序法律材料或权属条件不足，未进入推荐候选。"
                if special_assessment.score < 40
                else ""
            )
        ),
    }
    path_scores = _build_path_decision_scores(
        inp,
        path_values=paths,
        path_days=path_days,
        path_available=path_available,
        path_unavailable_reasons=path_unavailable_reasons,
        litigation_score=litigation_assessment.score,
        special_score=special_assessment.score,
    )
    available_scores = [row for row in path_scores if row.available]
    best_score = max(available_scores, key=lambda row: row.score)
    best_path = best_score.path
    best_value = paths[best_path]
    net_best_path = max(
        {p: v for p, v in paths.items() if path_available.get(p, True)},
        key=lambda p: paths[p],
    )

    # 生成建议文本
    path_names = {
        "A": "继续等待赎车",
        "B": "常规诉讼",
        "C": "立即上架竞拍",
        "D": "实现担保物权特别程序",
        "E": "分期重组/和解",
    }

    unavailable_notes = []
    if not path_c.available:
        unavailable_notes.append(f"路径 C 不可选：{path_c.unavailable_reason}")
    if not path_available["D"]:
        unavailable_notes.append(f"路径 D 不可选：{path_unavailable_reasons['D']}")
    header = ""
    if unavailable_notes:
        header = "（" + "；".join(unavailable_notes) + " 已从决策候选中自动排除。）\n"
    lines = [
        header
        + f"综合对比可用路径，推荐【{path_names[best_path]}】"
        + f"（综合评分{best_score.score:.1f}，预计净回收¥{best_value:,.0f}）。\n"
    ]
    if best_path != net_best_path:
        lines.append(
            f"净回收最高路径为【{path_names[net_best_path]}】，但本次综合评分同时考虑回款时间、"
            "法律可行性、执行难度和现金流紧迫度，因此未直接选择净回收最高路径。"
        )

    if best_path == "C":
        lines.append(
            f"立即竞拍可在{path_c.expected_sale_days}天内回款，"
            f"成交价¥{path_c.sale_price:,.0f}，扣除佣金和停车费后净回收¥{c_value:,.0f}。"
        )
        if path_c.market_liquidity_level in {"low", "very_low"}:
            lines.append(
                f"市场流动性评分{path_c.market_liquidity_score}分，已按低流动性拉长成交周期并下调成交价。"
            )
        if path_d.available and d_value > b_value:
            lines.append(f"若竞拍不可行，次优选择为担保物权特别程序（净回收¥{d_value:,.0f}，约3个月）。")
    elif best_path == "D":
        lines.append(
            f"特别程序约3个月完成，预计拍卖回收¥{path_d.expected_auction_price:,.0f}，"
            f"扣除法律费用¥{path_d.legal_cost.total_legal_cost:,.0f}等成本后净回收¥{d_value:,.0f}。"
        )
        lines.append(f"法律可行性评分{special_assessment.score}分：{special_assessment.recommendation}")
        lines.append(f"相比常规诉讼（净回收¥{b_value:,.0f}）缩短周期6个月以上。")
    elif best_path == "B":
        lines.append(
            f"常规诉讼预期情况下净回收¥{b_value:,.0f}，"
            f"但周期约9个月且不确定性较大。"
        )
        lines.append(f"常规诉讼法律可行性评分{litigation_assessment.score}分：{litigation_assessment.recommendation}")
        if path_d.available and d_value > 0:
            lines.append(f"建议评估是否可走担保物权特别程序（净回收¥{d_value:,.0f}，仅需3个月）。")
    elif best_path == "A":
        lines.append(
            f"在{a_best_days}天等待窗口内净头寸最优（¥{a_best:,.0f}），"
            f"但需密切关注贬值，超过{a_best_days}天建议转为处置。"
        )
    elif best_path == "E":
        lines.append(
            f"重组方案月还¥{path_e.monthly_payment:,.0f}×{path_e.total_months}期，"
            f"考虑{path_e.redefault_rate:.0%}再违约率后预计净回收¥{e_value:,.0f}。"
        )
        lines.append("需评估借款人还款意愿和能力，再违约风险不可忽视。")

    # 对比摘要
    lines.append("\n各路径对比：")
    sorted_paths = sorted(paths.items(), key=lambda x: x[1], reverse=True)
    for i, (p, v) in enumerate(sorted_paths):
        score_row = next(row for row in path_scores if row.path == p)
        marker = " <-- 推荐" if p == best_path else ""
        unavailable = "（不可选）" if not score_row.available else ""
        lines.append(f"  {path_names[p]}：¥{v:,.0f}，综合评分{score_row.score:.1f}{unavailable}{marker}")

    recommendation = "\n".join(lines)

    return SandboxResult(
        input=inp,
        path_a=path_a,
        path_b=path_b,
        path_c=path_c,
        path_d=path_d,
        path_e=path_e,
        path_scores=path_scores,
        recommendation=recommendation,
        best_path=best_path,
    )
