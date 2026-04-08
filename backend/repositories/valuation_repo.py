"""Repository for valuation_cache and depreciation_cache tables."""
import json
from datetime import datetime, timedelta, date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.valuation import ValuationCache, DepreciationCache


def get_fresh_valuation(
    session: Session,
    cache_key: str,
    within_days: int = 7,
) -> Optional[ValuationCache]:
    """Return the most recent valuation cache row if within the freshness window."""
    cutoff = datetime.utcnow() - timedelta(days=within_days)
    stmt = (
        select(ValuationCache)
        .where(ValuationCache.che300_model_id == cache_key)
        .where(ValuationCache.created_at > cutoff)
        .order_by(ValuationCache.created_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def save_valuation(
    session: Session,
    *,
    cache_key: str,
    city_code: str,
    excellent_price: Optional[float],
    good_price: Optional[float],
    medium_price: Optional[float],
    fair_price: Optional[float],
    dealer_buy_price: Optional[float],
    dealer_sell_price: Optional[float],
    raw_response: str,
) -> None:
    """Insert (or replace) a valuation cache row for today's query date."""
    today = date.today().isoformat()
    existing = session.scalars(
        select(ValuationCache).where(
            ValuationCache.che300_model_id == cache_key,
            ValuationCache.registration_date == today,
            ValuationCache.query_date == today,
            ValuationCache.city_code == city_code,
        )
    ).first()

    if existing is not None:
        existing.excellent_price = excellent_price
        existing.good_price = good_price
        existing.medium_price = medium_price
        existing.fair_price = fair_price
        existing.dealer_buy_price = dealer_buy_price
        existing.dealer_sell_price = dealer_sell_price
        existing.raw_response = raw_response
        existing.created_at = datetime.utcnow()
        return

    row = ValuationCache(
        che300_model_id=cache_key,
        registration_date=today,
        query_date=today,
        city_code=city_code,
        excellent_price=excellent_price,
        good_price=good_price,
        medium_price=medium_price,
        fair_price=fair_price,
        dealer_buy_price=dealer_buy_price,
        dealer_sell_price=dealer_sell_price,
        raw_response=raw_response,
    )
    session.add(row)


def get_fresh_depreciation(
    session: Session,
    model_name: str,
    within_days: int = 30,
) -> Optional[dict]:
    cutoff = datetime.utcnow() - timedelta(days=within_days)
    stmt = (
        select(DepreciationCache)
        .where(DepreciationCache.model_name == model_name)
        .where(DepreciationCache.created_at > cutoff)
        .order_by(DepreciationCache.created_at.desc())
        .limit(1)
    )
    row = session.scalars(stmt).first()
    if row is None:
        return None
    try:
        return json.loads(row.prediction_json)
    except (ValueError, TypeError):
        return None


def save_depreciation(
    session: Session,
    model_name: str,
    valuation: float,
    prediction: dict,
) -> None:
    row = DepreciationCache(
        model_name=model_name,
        valuation=valuation,
        prediction_json=json.dumps(prediction, ensure_ascii=False),
    )
    session.add(row)
