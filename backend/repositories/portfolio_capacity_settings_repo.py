"""Repository helpers for tenant capacity settings."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.portfolio_capacity import PortfolioCapacitySetting
from models.portfolio import PortfolioCapacitySettings


SETTINGS_FIELDS = (
    "monthly_towing_capacity",
    "monthly_litigation_capacity",
    "monthly_auction_capacity",
    "monthly_collection_capacity",
    "inventory_yard_capacity",
    "monthly_disposal_budget",
    "legal_team_capacity",
    "external_vendor_capacity",
)


def get_capacity_settings_row(
    session: Session,
    *,
    tenant_id: Optional[int],
) -> Optional[PortfolioCapacitySetting]:
    stmt = select(PortfolioCapacitySetting)
    if tenant_id is None:
        stmt = stmt.where(PortfolioCapacitySetting.tenant_id.is_(None))
    else:
        stmt = stmt.where(PortfolioCapacitySetting.tenant_id == tenant_id)
    stmt = stmt.limit(1)
    return session.scalars(stmt).first()


def to_settings(row: PortfolioCapacitySetting) -> PortfolioCapacitySettings:
    return PortfolioCapacitySettings(
        **{field: getattr(row, field) for field in SETTINGS_FIELDS}
    )


def upsert_capacity_settings(
    session: Session,
    *,
    tenant_id: Optional[int],
    settings: PortfolioCapacitySettings,
    updated_by: Optional[int],
) -> PortfolioCapacitySetting:
    row = get_capacity_settings_row(session, tenant_id=tenant_id)
    values = settings.model_dump()
    if row is None:
        row = PortfolioCapacitySetting(
            tenant_id=tenant_id,
            created_by=updated_by,
            updated_by=updated_by,
            **values,
        )
        session.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)
        row.updated_by = updated_by
    session.flush()
    return row
