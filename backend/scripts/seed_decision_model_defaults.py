"""Seed default decision-model configuration.

The values are conservative business defaults for MVP calculations. They are
intended to be adjusted later from an admin UI or model feedback loop.
"""
from sqlalchemy.orm import Session

from db.models.decision_model_config import (
    BrandRetentionProfile,
    RegionDisposalCoefficient,
)
from db.session import get_db_session


BRAND_PROFILE_DEFAULTS = [
    {
        "code": "luxury",
        "name": "豪华品牌",
        "vehicle_type": "luxury",
        "match_keywords": "宝马,奔驰,奥迪,BMW,Benz,Audi,保时捷,路虎,捷豹,雷克萨斯",
        "retention_factor": 0.92,
        "base_monthly_depreciation": 0.020,
        "age_decay_factor": 0.020,
        "new_energy_tech_discount": 0.0,
        "is_new_energy": False,
    },
    {
        "code": "japanese",
        "name": "日系高保值",
        "vehicle_type": "japanese",
        "match_keywords": "丰田,本田,日产,马自达,Toyota,Honda,Nissan",
        "retention_factor": 1.12,
        "base_monthly_depreciation": 0.010,
        "age_decay_factor": 0.010,
        "new_energy_tech_discount": 0.0,
        "is_new_energy": False,
    },
    {
        "code": "german",
        "name": "德系非豪华",
        "vehicle_type": "german",
        "match_keywords": "大众,斯柯达,Volkswagen",
        "retention_factor": 1.00,
        "base_monthly_depreciation": 0.014,
        "age_decay_factor": 0.014,
        "new_energy_tech_discount": 0.0,
        "is_new_energy": False,
    },
    {
        "code": "domestic",
        "name": "国产燃油",
        "vehicle_type": "domestic",
        "match_keywords": "吉利,长安,奇瑞,哈弗,红旗,传祺,荣威",
        "retention_factor": 0.88,
        "base_monthly_depreciation": 0.018,
        "age_decay_factor": 0.018,
        "new_energy_tech_discount": 0.0,
        "is_new_energy": False,
    },
    {
        "code": "new_energy",
        "name": "新能源",
        "vehicle_type": "new_energy",
        "match_keywords": "特斯拉,Tesla,比亚迪,BYD,蔚来,NIO,小鹏,理想,零跑,哪吒,极氪,EV,纯电,插混,PHEV",
        "retention_factor": 0.78,
        "base_monthly_depreciation": 0.026,
        "age_decay_factor": 0.030,
        "new_energy_tech_discount": 0.08,
        "is_new_energy": True,
    },
]


REGION_COEFFICIENT_DEFAULTS = [
    {
        "region_code": "CN_DEFAULT",
        "province": "全国",
        "city": None,
        "liquidity_speed_factor": 1.0,
        "legal_efficiency_factor": 1.0,
        "towing_cost_factor": 1.0,
    },
    {
        "region_code": "JS",
        "province": "江苏省",
        "city": None,
        "liquidity_speed_factor": 1.08,
        "legal_efficiency_factor": 1.06,
        "towing_cost_factor": 0.95,
    },
    {
        "region_code": "JS_NJ",
        "province": "江苏省",
        "city": "南京市",
        "liquidity_speed_factor": 1.12,
        "legal_efficiency_factor": 1.08,
        "towing_cost_factor": 0.92,
    },
    {
        "region_code": "GD",
        "province": "广东省",
        "city": None,
        "liquidity_speed_factor": 1.15,
        "legal_efficiency_factor": 1.03,
        "towing_cost_factor": 1.03,
    },
    {
        "region_code": "SC",
        "province": "四川省",
        "city": None,
        "liquidity_speed_factor": 0.96,
        "legal_efficiency_factor": 0.95,
        "towing_cost_factor": 1.10,
    },
]


def _upsert(session: Session, model, key_name: str, row: dict) -> None:
    existing = (
        session.query(model)
        .filter(getattr(model, key_name) == row[key_name])
        .first()
    )
    if existing is None:
        session.add(model(**row, is_active=True))
        return
    for key, value in row.items():
        setattr(existing, key, value)
    existing.is_active = True


def seed_decision_model_defaults(session: Session) -> dict[str, int]:
    for row in BRAND_PROFILE_DEFAULTS:
        _upsert(session, BrandRetentionProfile, "code", row)
    for row in REGION_COEFFICIENT_DEFAULTS:
        _upsert(session, RegionDisposalCoefficient, "region_code", row)
    session.commit()
    return {
        "brand_profiles": len(BRAND_PROFILE_DEFAULTS),
        "region_coefficients": len(REGION_COEFFICIENT_DEFAULTS),
    }


def main() -> None:
    gen = get_db_session()
    session = next(gen)
    try:
        seed_decision_model_defaults(session)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
