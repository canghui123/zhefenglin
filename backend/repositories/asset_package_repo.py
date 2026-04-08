"""Repository for asset_packages and assets tables."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.asset_package import AssetPackage, Asset


def create_package(
    session: Session,
    name: str,
    upload_filename: str = "",
    total_assets: int = 0,
) -> AssetPackage:
    pkg = AssetPackage(
        name=name,
        upload_filename=upload_filename,
        total_assets=total_assets,
    )
    session.add(pkg)
    session.flush()  # populate pkg.id
    return pkg


def get_package_by_id(session: Session, package_id: int) -> Optional[AssetPackage]:
    return session.get(AssetPackage, package_id)


def list_packages(session: Session) -> List[AssetPackage]:
    stmt = select(AssetPackage).order_by(AssetPackage.created_at.desc())
    return list(session.scalars(stmt).all())


def update_package_upload(
    session: Session,
    package_id: int,
    upload_filename: str,
    total_assets: int,
) -> None:
    pkg = session.get(AssetPackage, package_id)
    if pkg is None:
        return
    pkg.upload_filename = upload_filename
    pkg.total_assets = total_assets


def delete_package(session: Session, package_id: int) -> None:
    pkg = session.get(AssetPackage, package_id)
    if pkg is not None:
        session.delete(pkg)


def save_package_result(
    session: Session,
    package_id: int,
    parameters_json: str,
    results_json: str,
) -> None:
    pkg = session.get(AssetPackage, package_id)
    if pkg is None:
        return
    pkg.parameters_json = parameters_json
    pkg.results_json = results_json
