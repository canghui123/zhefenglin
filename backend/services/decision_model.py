"""Shared decision-model helpers for disposal simulations and pricing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.decision_model_config import (
    BrandRetentionProfile,
    RegionDisposalCoefficient,
)


@dataclass(frozen=True)
class BrandProfile:
    code: str
    name: str
    vehicle_type: str
    match_keywords: tuple[str, ...]
    retention_factor: float
    base_monthly_depreciation: float
    age_decay_factor: float
    new_energy_tech_discount: float = 0.0
    is_new_energy: bool = False


@dataclass(frozen=True)
class RegionCoefficient:
    region_code: str
    province: str
    city: Optional[str]
    liquidity_speed_factor: float
    legal_efficiency_factor: float
    towing_cost_factor: float


DEFAULT_BRAND_PROFILES: dict[str, BrandProfile] = {
    "luxury": BrandProfile(
        "luxury", "豪华品牌", "luxury",
        ("宝马", "奔驰", "奥迪", "BMW", "Benz", "Audi", "保时捷", "路虎", "雷克萨斯"),
        0.92, 0.020, 0.020,
    ),
    "japanese": BrandProfile(
        "japanese", "日系高保值", "japanese",
        ("丰田", "本田", "日产", "马自达", "Toyota", "Honda", "Nissan"),
        1.12, 0.010, 0.010,
    ),
    "german": BrandProfile(
        "german", "德系非豪华", "german",
        ("大众", "斯柯达", "Volkswagen"),
        1.00, 0.014, 0.014,
    ),
    "domestic": BrandProfile(
        "domestic", "国产燃油", "domestic",
        ("吉利", "长安", "奇瑞", "哈弗", "红旗", "传祺", "荣威"),
        0.88, 0.018, 0.018,
    ),
    "new_energy": BrandProfile(
        "new_energy", "新能源", "new_energy",
        ("特斯拉", "Tesla", "比亚迪", "BYD", "蔚来", "NIO", "小鹏", "理想", "零跑", "哪吒", "极氪", "EV", "纯电", "插混", "PHEV"),
        0.78, 0.026, 0.030, 0.08, True,
    ),
}

DEFAULT_REGION = RegionCoefficient("CN_DEFAULT", "全国", None, 1.0, 1.0, 1.0)
DEFAULT_REGION_COEFFICIENTS: tuple[RegionCoefficient, ...] = (
    DEFAULT_REGION,
    RegionCoefficient("JS", "江苏省", None, 1.08, 1.05, 0.96),
    RegionCoefficient("JS_NJ", "江苏省", "南京市", 1.12, 1.06, 0.95),
    RegionCoefficient("GD", "广东省", None, 1.12, 1.02, 1.02),
    RegionCoefficient("SC", "四川省", None, 0.92, 0.90, 1.12),
)


def _profile_from_row(row: BrandRetentionProfile) -> BrandProfile:
    keywords = tuple(
        item.strip() for item in (row.match_keywords or "").split(",") if item.strip()
    )
    return BrandProfile(
        code=row.code,
        name=row.name,
        vehicle_type=row.vehicle_type,
        match_keywords=keywords,
        retention_factor=row.retention_factor,
        base_monthly_depreciation=row.base_monthly_depreciation,
        age_decay_factor=row.age_decay_factor,
        new_energy_tech_discount=row.new_energy_tech_discount,
        is_new_energy=row.is_new_energy,
    )


def _region_from_row(row: RegionDisposalCoefficient) -> RegionCoefficient:
    return RegionCoefficient(
        region_code=row.region_code,
        province=row.province,
        city=row.city,
        liquidity_speed_factor=row.liquidity_speed_factor,
        legal_efficiency_factor=row.legal_efficiency_factor,
        towing_cost_factor=row.towing_cost_factor,
    )


def _load_profiles(session: Optional[Session]) -> list[BrandProfile]:
    if session is None:
        return list(DEFAULT_BRAND_PROFILES.values())
    rows = session.scalars(
        select(BrandRetentionProfile)
        .where(BrandRetentionProfile.is_active.is_(True))
        .order_by(BrandRetentionProfile.id)
    ).all()
    return [_profile_from_row(row) for row in rows] or list(DEFAULT_BRAND_PROFILES.values())


def resolve_brand_profile(
    *,
    session: Optional[Session] = None,
    vehicle_type: Optional[str] = None,
    car_description: str = "",
) -> BrandProfile:
    profiles = _load_profiles(session)
    normalized_type = (vehicle_type or "").strip()
    if normalized_type and normalized_type != "auto":
        for profile in profiles:
            if profile.vehicle_type == normalized_type or profile.code == normalized_type:
                return profile

    for profile in profiles:
        if any(keyword and keyword in car_description for keyword in profile.match_keywords):
            return profile
    return DEFAULT_BRAND_PROFILES["domestic"]


def resolve_region_coefficient(
    *,
    session: Optional[Session] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
) -> RegionCoefficient:
    province = (province or "").strip()
    city = (city or "").strip()
    fallback = DEFAULT_REGION
    if province:
        if city:
            for region in DEFAULT_REGION_COEFFICIENTS:
                if region.province == province and region.city == city:
                    fallback = region
                    break
        if fallback is DEFAULT_REGION:
            for region in DEFAULT_REGION_COEFFICIENTS:
                if region.province == province and region.city is None:
                    fallback = region
                    break
    if session is not None and province:
        if city:
            row = session.scalars(
                select(RegionDisposalCoefficient)
                .where(RegionDisposalCoefficient.is_active.is_(True))
                .where(RegionDisposalCoefficient.province == province)
                .where(RegionDisposalCoefficient.city == city)
                .limit(1)
            ).first()
            if row is not None:
                return _region_from_row(row)
        row = session.scalars(
            select(RegionDisposalCoefficient)
            .where(RegionDisposalCoefficient.is_active.is_(True))
            .where(RegionDisposalCoefficient.province == province)
            .where(RegionDisposalCoefficient.city.is_(None))
            .limit(1)
        ).first()
        if row is not None:
            return _region_from_row(row)
    return fallback


def estimate_depreciation_rate(
    *,
    days: int,
    vehicle_age_years: float,
    profile: BrandProfile,
) -> float:
    months = max(days, 0) / 30.0
    age_factor = min(0.035, max(vehicle_age_years, 0) * profile.age_decay_factor * 0.10)
    monthly_rate = profile.base_monthly_depreciation + age_factor
    cumulative = 1 - (1 - monthly_rate) ** months
    if profile.is_new_energy:
        cumulative += profile.new_energy_tech_discount * min(1.0, months / 12.0)
    return min(max(cumulative, 0.0), 0.85)


def adjusted_towing_cost(base_cost: float, region: RegionCoefficient) -> float:
    return base_cost * region.towing_cost_factor


def adjusted_duration_days(
    base_days: int,
    *,
    region: RegionCoefficient,
    path_type: str,
) -> int:
    if path_type in {"litigation", "special_procedure"}:
        factor = region.legal_efficiency_factor
    else:
        factor = region.liquidity_speed_factor
    return max(1, round(base_days / max(factor, 0.20)))


def dynamic_success_probability(
    *,
    base_probability: float,
    vehicle_age_years: float,
    overdue_amount: float,
    vehicle_value: float,
    profile: BrandProfile,
    region: RegionCoefficient,
    path_type: str,
    vehicle_recovered: bool = True,
    vehicle_in_inventory: bool = True,
    learning_adjustment: float = 0.0,
) -> float:
    age_penalty = min(0.35, max(vehicle_age_years - 2, 0) * 0.025)
    overdue_ratio = overdue_amount / vehicle_value if vehicle_value > 0 else 1.0
    overdue_penalty = min(0.30, max(overdue_ratio - 0.60, 0) * 0.22)
    retention_adjustment = (profile.retention_factor - 1.0) * 0.18

    if path_type in {"litigation", "special_procedure"}:
        region_adjustment = (region.legal_efficiency_factor - 1.0) * 0.12
    else:
        region_adjustment = (region.liquidity_speed_factor - 1.0) * 0.14

    status_penalty = 0.0
    if path_type in {"retail_auction", "vehicle_transfer", "bulk_clearance"} and not vehicle_recovered:
        status_penalty += 0.35
    if path_type == "special_procedure" and (not vehicle_recovered or not vehicle_in_inventory):
        return 0.0

    probability = (
        base_probability
        - age_penalty
        - overdue_penalty
        - status_penalty
        + retention_adjustment
        + region_adjustment
        + learning_adjustment
    )
    return round(min(0.98, max(0.0, probability)), 4)
