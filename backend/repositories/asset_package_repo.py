"""Repository for asset_packages and assets tables.

Every read/write here is scoped to a `tenant_id`. The API layer pulls
the tenant from `services.tenant_context.get_current_tenant_id` and
passes it down so the SQL filter is enforced in exactly one place.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.asset_package import AssetPackage, Asset


def create_package(
    session: Session,
    *,
    tenant_id: int,
    name: str,
    upload_filename: str = "",
    total_assets: int = 0,
    created_by: Optional[int] = None,
) -> AssetPackage:
    pkg = AssetPackage(
        tenant_id=tenant_id,
        created_by=created_by,
        name=name,
        upload_filename=upload_filename,
        total_assets=total_assets,
    )
    session.add(pkg)
    session.flush()  # populate pkg.id
    return pkg


def get_package_by_id(
    session: Session, package_id: int, *, tenant_id: int
) -> Optional[AssetPackage]:
    stmt = (
        select(AssetPackage)
        .where(AssetPackage.id == package_id)
        .where(AssetPackage.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_packages(session: Session, *, tenant_id: int) -> List[AssetPackage]:
    stmt = (
        select(AssetPackage)
        .where(AssetPackage.tenant_id == tenant_id)
        .order_by(AssetPackage.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def update_package_upload(
    session: Session,
    package_id: int,
    *,
    tenant_id: int,
    upload_filename: str,
    total_assets: int,
    storage_key: Optional[str] = None,
) -> None:
    pkg = get_package_by_id(session, package_id, tenant_id=tenant_id)
    if pkg is None:
        return
    pkg.upload_filename = upload_filename
    pkg.total_assets = total_assets
    if storage_key is not None:
        pkg.storage_key = storage_key


def delete_package(session: Session, package_id: int, *, tenant_id: int) -> None:
    pkg = get_package_by_id(session, package_id, tenant_id=tenant_id)
    if pkg is not None:
        session.delete(pkg)


def save_package_result(
    session: Session,
    package_id: int,
    *,
    tenant_id: int,
    parameters_json: str,
    results_json: str,
) -> None:
    pkg = get_package_by_id(session, package_id, tenant_id=tenant_id)
    if pkg is None:
        return
    pkg.parameters_json = parameters_json
    pkg.results_json = results_json
