"""Market liquidity and new-energy risk scoring.

The rules are deterministic by design: LLM reports may explain these values, but
price, cycle and risk tags are calculated here.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from models.asset import Asset, MarketLiquidityResult

EnergyType = Literal["fuel", "bev", "phev", "erev", "hybrid", "unknown"]

MAINSTREAM_FUEL_KEYWORDS = (
    "凯美瑞",
    "雅阁",
    "卡罗拉",
    "雷凌",
    "轩逸",
    "朗逸",
    "速腾",
    "帕萨特",
    "迈腾",
    "CR-V",
    "RAV4",
    "汉兰达",
    "丰田",
    "本田",
    "大众",
)
MAINSTREAM_NEW_ENERGY_KEYWORDS = ("特斯拉", "Tesla", "比亚迪", "BYD", "理想", "问界", "极氪")
COLD_NEW_ENERGY_KEYWORDS = ("哪吒", "威马", "高合", "爱驰", "云度", "天际")
COLD_LUXURY_KEYWORDS = ("玛莎拉蒂", "捷豹", "路虎", "林肯", "英菲尼迪", "阿尔法罗密欧")
ACCIDENT_KEYWORDS = ("事故", "水泡", "泡水", "火烧", "重大维修")
OPERATING_KEYWORDS = ("营运", "运营", "网约", "出租", "租赁", "营转非")
BEV_KEYWORDS = ("纯电", "BEV", "EV", "特斯拉", "Tesla", "蔚来", "小鹏", "极氪", "哪吒", "威马", "高合")
PHEV_KEYWORDS = ("插混", "PHEV", "DM-i", "DM", "混动")
EREV_KEYWORDS = ("增程", "EREV", "理想", "问界")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def detect_energy_type(description: str, explicit: EnergyType = "unknown") -> EnergyType:
    if explicit and explicit != "unknown":
        return explicit
    text = description or ""
    if _contains_any(text, EREV_KEYWORDS):
        return "erev"
    if _contains_any(text, PHEV_KEYWORDS):
        return "phev"
    if _contains_any(text, BEV_KEYWORDS):
        return "bev"
    if "新能源" in text:
        return "bev"
    return "fuel"


def _vehicle_age_years(first_registration: Optional[date]) -> Optional[float]:
    if first_registration is None:
        return None
    return max((date.today() - first_registration).days / 365.25, 0)


def _level(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    if score >= 35:
        return "low"
    return "very_low"


def _sale_day_multiplier(level: str) -> float:
    if level == "high":
        return 0.8
    if level == "low":
        return 1.3
    if level == "very_low":
        return 1.6
    return 1.0


def calculate_market_liquidity(
    asset: Asset,
    *,
    valuation_price: Optional[float],
    base_expected_sale_days: int,
) -> MarketLiquidityResult:
    """Calculate market liquidity adjustment for one asset.

    `adjustment` is a discount-rate adjustment. Negative values lower the
    recommended transfer price; positive values raise it for highly liquid cars.
    """
    text = asset.car_description or ""
    energy_type = detect_energy_type(text, asset.energy_type)
    age_years = _vehicle_age_years(asset.first_registration)

    adjustment = 0.0
    tags: list[str] = []
    new_energy_tags: list[str] = []
    new_energy_adjustment = 0.0

    if energy_type == "fuel" and _contains_any(text, MAINSTREAM_FUEL_KEYWORDS):
        adjustment += 0.02
        tags.append("mainstream_fuel_model")
    if _contains_any(text, ("丰田", "本田", "大众", "奔驰", "宝马", "奥迪")):
        adjustment += 0.01

    if _contains_any(text, COLD_LUXURY_KEYWORDS):
        adjustment -= 0.03
        tags.append("cold_luxury_model")

    operating = bool(asset.operating_vehicle) or _contains_any(text, OPERATING_KEYWORDS)
    ride_hailing = bool(asset.ride_hailing_vehicle) or "网约" in text
    if operating:
        adjustment -= 0.05
        tags.append("operating_vehicle")
    if ride_hailing:
        adjustment -= 0.05
        tags.append("ride_hailing_usage")
    if "营转非" in text:
        adjustment -= 0.06
        tags.append("commercial_to_private_title")

    if _contains_any(text, ACCIDENT_KEYWORDS):
        adjustment -= 0.08
        tags.append("accident_or_flood_fire_risk")

    if energy_type in {"bev", "phev", "erev", "hybrid"}:
        tags.append("new_energy_vehicle")
        if _contains_any(text, MAINSTREAM_NEW_ENERGY_KEYWORDS):
            adjustment += 0.01
            new_energy_adjustment += 0.01
        if _contains_any(text, COLD_NEW_ENERGY_KEYWORDS):
            adjustment -= 0.06
            new_energy_adjustment -= 0.04
            new_energy_tags.append("cold_brand_liquidity_risk")
        if energy_type == "bev" and age_years is not None and age_years >= 3:
            new_energy_adjustment -= 0.03
            new_energy_tags.append("high_depreciation_stage")
        if operating or ride_hailing:
            new_energy_adjustment -= 0.05
            new_energy_tags.append("ride_hailing_usage")
        if asset.battery_warranty_valid is False:
            new_energy_adjustment -= 0.03
            new_energy_tags.append("warranty_expired")
        if asset.battery_health_score is None:
            new_energy_adjustment -= 0.02
            new_energy_tags.append("battery_health_missing")
        elif asset.battery_health_score < 75:
            new_energy_adjustment -= 0.03
            new_energy_tags.append("battery_health_low")
        if asset.range_km is not None and asset.range_km < 350:
            new_energy_adjustment -= 0.02
            new_energy_tags.append("range_version_outdated")
        if asset.battery_replacement_history:
            new_energy_adjustment -= 0.01
            new_energy_tags.append("battery_replacement_history")

    adjustment += new_energy_adjustment
    adjustment = round(max(min(adjustment, 0.06), -0.22), 4)

    score = int(round(70 + adjustment * 300))
    if valuation_price is None or valuation_price <= 0:
        score -= 8
    if age_years is not None and age_years > 8:
        score -= 8
        tags.append("old_vehicle_liquidity_decay")
    score = max(0, min(score, 100))
    level = _level(score)

    expected_days = max(
        1,
        int(round(max(base_expected_sale_days, 1) * _sale_day_multiplier(level))),
    )
    return MarketLiquidityResult(
        score=score,
        level=level,
        adjustment=adjustment,
        expected_sale_days_adjusted=expected_days,
        liquidity_risk_tags=list(dict.fromkeys(tags)),
        energy_type=energy_type,
        new_energy_risk_tags=list(dict.fromkeys(new_energy_tags)),
        new_energy_adjustment=round(new_energy_adjustment, 4),
    )
