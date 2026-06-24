"""P2 任务市场 —— 发布方 API(web 系统,tenant 用户)。

发布/管理拖车订单与拍卖标的。所有查询 tenant 隔离,operator 及以上可操作。
状态推进的接单方动作(accept/bid 等)在 api/marketplace_worker.py。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from errors import BusinessError
from repositories import marketplace_repo
from services import audit_service, marketplace_service, rate_limit_service
from services.tenant_context import get_current_tenant_id
from config import settings

router = APIRouter(prefix="/api/marketplace", tags=["task-marketplace"])


class TowOrderNotFound(BusinessError):
    def __init__(self):
        super().__init__("TOW_ORDER_NOT_FOUND", "拖车订单不存在", 404)


class AuctionNotFound(BusinessError):
    def __init__(self):
        super().__init__("AUCTION_NOT_FOUND", "拍卖标的不存在", 404)


# ─────────────────────────── 拖车订单 ───────────────────────────

class TowOrderCreate(BaseModel):
    vehicle_desc: str = Field(..., min_length=1, max_length=255)
    plate_no: Optional[str] = Field(None, max_length=16)
    vin: Optional[str] = Field(None, max_length=17)
    drivable: Optional[bool] = None
    has_keys: Optional[bool] = None
    condition_notes: Optional[str] = None
    pickup_province: Optional[str] = None
    pickup_city: str = Field(..., min_length=1, max_length=64)
    pickup_district: Optional[str] = None
    pickup_address: str = Field(..., min_length=1, max_length=512)
    pickup_contact_name: Optional[str] = None
    pickup_contact_phone: Optional[str] = None
    dropoff_address: str = Field(..., min_length=1, max_length=512)
    dropoff_contact_name: Optional[str] = None
    dropoff_contact_phone: Optional[str] = None
    distance_km: Optional[float] = Field(None, ge=0)
    deadline_at: Optional[datetime] = None
    special_requirements: Optional[str] = None
    reward_amount: float = Field(..., gt=0)
    asset_package_id: Optional[int] = None


@router.post("/tow-orders", dependencies=[Depends(require_role("operator"))])
def create_tow_order(
    body: TowOrderCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rate_limit_service.enforce_request_limit(
        request, scope="marketplace.tow_create", limit=settings.rate_limit_write_max_requests
    )
    order = marketplace_repo.create_tow_order(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        status="published",
        **body.model_dump(),
    )
    marketplace_repo.add_tow_event(
        session, order_id=order.id, actor_type="publisher", actor_id=user.id,
        event_type="status_change", payload_json='{"to": "published"}',
    )
    audit_service.record(
        session, request, action="tow_order_create", tenant_id=tenant_id,
        user_id=user.id, resource_type="tow_order", resource_id=order.id,
    )
    return marketplace_service.tow_order_owner_dict(order)


@router.get("/tow-orders", dependencies=[Depends(require_role("operator"))])
def list_tow_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = marketplace_repo.list_tow_orders_for_tenant(
        session, tenant_id=tenant_id, status=status_filter
    )
    return [marketplace_service.tow_order_owner_dict(o) for o in rows]


@router.get("/tow-orders/{order_id}", dependencies=[Depends(require_role("operator"))])
def get_tow_order(
    order_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    order = marketplace_repo.get_tow_order(session, order_id, tenant_id=tenant_id)
    if not order:
        raise TowOrderNotFound()
    data = marketplace_service.tow_order_owner_dict(order)
    data["events"] = [
        {
            "event_type": e.event_type, "actor_type": e.actor_type,
            "payload_json": e.payload_json, "photo_storage_key": e.photo_storage_key,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in marketplace_repo.list_tow_events(session, order_id=order.id)
    ]
    return data


def _advance_tow(session, request, tenant_id, user, order_id, target, ts_field, action):
    order = marketplace_repo.get_tow_order(session, order_id, tenant_id=tenant_id)
    if not order:
        raise TowOrderNotFound()
    marketplace_service.assert_tow_transition(order.status, target)
    order.status = target
    setattr(order, ts_field, datetime.utcnow())
    marketplace_repo.add_tow_event(
        session, order_id=order.id, actor_type="publisher", actor_id=user.id,
        event_type="status_change", payload_json=f'{{"to": "{target}"}}',
    )
    audit_service.record(
        session, request, action=action, tenant_id=tenant_id, user_id=user.id,
        resource_type="tow_order", resource_id=order.id,
    )
    return marketplace_service.tow_order_owner_dict(order)


@router.post("/tow-orders/{order_id}/confirm", dependencies=[Depends(require_role("operator"))])
def confirm_tow_order(
    order_id: int, request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return _advance_tow(session, request, tenant_id, user, order_id, "confirmed", "confirmed_at", "tow_order_confirm")


class SettleBody(BaseModel):
    settlement_note: Optional[str] = None


@router.post("/tow-orders/{order_id}/settle", dependencies=[Depends(require_role("operator"))])
def settle_tow_order(
    order_id: int, request: Request, body: SettleBody = SettleBody(),
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    order = marketplace_repo.get_tow_order(session, order_id, tenant_id=tenant_id)
    if not order:
        raise TowOrderNotFound()
    marketplace_service.assert_tow_transition(order.status, "settled")
    order.status = "settled"
    order.settled_at = datetime.utcnow()
    order.settlement_note = body.settlement_note
    audit_service.record(
        session, request, action="tow_order_settle", tenant_id=tenant_id,
        user_id=user.id, resource_type="tow_order", resource_id=order.id,
    )
    return marketplace_service.tow_order_owner_dict(order)


class CancelBody(BaseModel):
    reason: Optional[str] = None


@router.post("/tow-orders/{order_id}/cancel", dependencies=[Depends(require_role("operator"))])
def cancel_tow_order(
    order_id: int, request: Request, body: CancelBody = CancelBody(),
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    order = marketplace_repo.get_tow_order(session, order_id, tenant_id=tenant_id)
    if not order:
        raise TowOrderNotFound()
    marketplace_service.assert_tow_transition(order.status, "cancelled")
    order.status = "cancelled"
    order.cancelled_at = datetime.utcnow()
    order.cancel_reason = body.reason
    audit_service.record(
        session, request, action="tow_order_cancel", tenant_id=tenant_id,
        user_id=user.id, resource_type="tow_order", resource_id=order.id,
    )
    return marketplace_service.tow_order_owner_dict(order)


# ─────────────────────────── 拍卖标的 ───────────────────────────

class AuctionCreate(BaseModel):
    vehicle_desc: str = Field(..., min_length=1, max_length=255)
    model_year: Optional[int] = None
    first_registration: Optional[str] = None
    mileage_km: Optional[float] = Field(None, ge=0)
    emission_standard: Optional[str] = None
    key_count: Optional[int] = None
    transfer_count: Optional[int] = None
    has_registration_cert: Optional[bool] = None
    has_driving_license: Optional[bool] = None
    mortgage_status: Optional[str] = None
    violation_status: Optional[str] = None
    vin: Optional[str] = Field(None, max_length=17)
    accident_level: Optional[str] = None
    exterior_score: Optional[int] = None
    interior_score: Optional[int] = None
    mechanical_score: Optional[int] = None
    photos_json: Optional[str] = None
    location_city: str = Field(..., min_length=1, max_length=64)
    viewing_start: Optional[datetime] = None
    viewing_end: Optional[datetime] = None
    viewing_contact: Optional[str] = None
    start_price: float = Field(..., gt=0)
    deposit_amount: float = Field(0, ge=0)
    min_increment: float = Field(1000, gt=0)
    starts_at: datetime
    ends_at: datetime
    asset_package_id: Optional[int] = None


@router.post("/auctions", dependencies=[Depends(require_role("operator"))])
def create_auction(
    body: AuctionCreate, request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rate_limit_service.enforce_request_limit(
        request, scope="marketplace.auction_create", limit=settings.rate_limit_write_max_requests
    )
    if body.ends_at <= body.starts_at:
        raise BusinessError("INVALID_AUCTION_WINDOW", "竞拍结束时间必须晚于开始时间", 400)
    listing = marketplace_repo.create_auction(
        session, tenant_id=tenant_id, created_by=user.id,
        status="upcoming", current_price=body.start_price, **body.model_dump(),
    )
    audit_service.record(
        session, request, action="auction_create", tenant_id=tenant_id,
        user_id=user.id, resource_type="auction_listing", resource_id=listing.id,
    )
    return marketplace_service.auction_detail_dict(listing, reveal_vin=True)


@router.get("/auctions", dependencies=[Depends(require_role("operator"))])
def list_auctions(
    status_filter: Optional[str] = Query(None, alias="status"),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = marketplace_repo.list_auctions_for_tenant(
        session, tenant_id=tenant_id, status=status_filter
    )
    return [marketplace_service.auction_detail_dict(a, reveal_vin=True) for a in rows]


@router.get("/auctions/{listing_id}", dependencies=[Depends(require_role("operator"))])
def get_auction(
    listing_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    listing = marketplace_repo.get_auction(session, listing_id, tenant_id=tenant_id)
    if not listing:
        raise AuctionNotFound()
    data = marketplace_service.auction_detail_dict(listing, reveal_vin=True)
    data["bids"] = [
        {"worker_id": b.worker_id, "amount": b.amount,
         "created_at": b.created_at.isoformat() if b.created_at else None}
        for b in marketplace_repo.list_bids(session, listing_id=listing.id)
    ]
    return data


@router.post("/auctions/{listing_id}/go-live", dependencies=[Depends(require_role("operator"))])
def go_live_auction(
    listing_id: int, request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    listing = marketplace_repo.get_auction(session, listing_id, tenant_id=tenant_id)
    if not listing:
        raise AuctionNotFound()
    marketplace_service.assert_auction_transition(listing.status, "live")
    listing.status = "live"
    audit_service.record(
        session, request, action="auction_go_live", tenant_id=tenant_id,
        user_id=user.id, resource_type="auction_listing", resource_id=listing.id,
    )
    return marketplace_service.auction_detail_dict(listing, reveal_vin=True)


@router.post("/auctions/{listing_id}/end", dependencies=[Depends(require_role("operator"))])
def end_auction(
    listing_id: int, request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    listing = marketplace_repo.get_auction(session, listing_id, tenant_id=tenant_id)
    if not listing:
        raise AuctionNotFound()
    bids = marketplace_repo.list_bids(session, listing_id=listing.id)
    target = "ended_sold" if bids else "ended_unsold"
    marketplace_service.assert_auction_transition(listing.status, target)
    listing.status = target
    if bids:
        listing.winner_worker_id = bids[0].worker_id
        listing.current_price = bids[0].amount
    audit_service.record(
        session, request, action="auction_end", tenant_id=tenant_id,
        user_id=user.id, resource_type="auction_listing", resource_id=listing.id,
    )
    return marketplace_service.auction_detail_dict(listing, reveal_vin=True)


@router.post("/auctions/{listing_id}/settle", dependencies=[Depends(require_role("operator"))])
def settle_auction(
    listing_id: int, request: Request, body: SettleBody = SettleBody(),
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    listing = marketplace_repo.get_auction(session, listing_id, tenant_id=tenant_id)
    if not listing:
        raise AuctionNotFound()
    marketplace_service.assert_auction_transition(listing.status, "settled")
    listing.status = "settled"
    listing.settled_at = datetime.utcnow()
    listing.settlement_note = body.settlement_note
    audit_service.record(
        session, request, action="auction_settle", tenant_id=tenant_id,
        user_id=user.id, resource_type="auction_listing", resource_id=listing.id,
    )
    return marketplace_service.auction_detail_dict(listing, reveal_vin=True)
