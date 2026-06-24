"""P2 任务市场 —— 接单方 API(微信小程序 worker)。

前缀 /api/m。登录走微信 code2session(mock/real),其余接口用 worker JWT。
与发布方(tenant 用户)体系完全隔离:worker 不在 users 表。

可见性规则:
- 公开大厅只列 published 拖车单 / live 拍卖(脱敏)
- 拖车单联系方式仅向接单本人披露
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models.marketplace import MarketplaceWorker
from db.session import get_db_session
from dependencies.worker_auth import get_current_worker, issue_worker_token
from errors import BusinessError
from repositories import marketplace_repo
from services import audit_service, marketplace_service, rate_limit_service
from services.wechat_service import WeChatError, code_to_session
from config import settings

router = APIRouter(prefix="/api/m", tags=["task-marketplace-worker"])


class TowOrderNotFound(BusinessError):
    def __init__(self):
        super().__init__("TOW_ORDER_NOT_FOUND", "拖车订单不存在", 404)


class AuctionNotFound(BusinessError):
    def __init__(self):
        super().__init__("AUCTION_NOT_FOUND", "拍卖标的不存在", 404)


class BidTooLow(BusinessError):
    def __init__(self, detail: str):
        super().__init__("BID_TOO_LOW", detail, 409)


class AuctionNotBiddable(BusinessError):
    def __init__(self, detail: str = "当前不在竞拍时段"):
        super().__init__("AUCTION_NOT_BIDDABLE", detail, 409)


# ─────────────────────────── 登录 ───────────────────────────

class WorkerLogin(BaseModel):
    code: str = Field(..., min_length=1)
    display_name: Optional[str] = None
    phone: Optional[str] = None
    worker_type: Optional[str] = None
    service_city: Optional[str] = None


@router.post("/auth/login")
def worker_login(
    body: WorkerLogin, request: Request,
    session: Session = Depends(get_db_session),
):
    rate_limit_service.enforce_request_limit(
        request, scope="marketplace.worker_login", limit=settings.rate_limit_login_max_requests
    )
    try:
        sess = code_to_session(body.code)
    except WeChatError as exc:
        raise BusinessError("WECHAT_LOGIN_FAILED", str(exc), 400)

    worker = marketplace_repo.get_worker_by_openid(session, sess["openid"])
    if worker is None:
        worker = marketplace_repo.create_worker(
            session,
            wechat_openid=sess["openid"],
            wechat_unionid=sess.get("unionid"),
            display_name=body.display_name,
            phone=body.phone,
            worker_type=body.worker_type or "tow_driver",
            service_city=body.service_city,
            last_login_at=datetime.utcnow(),
        )
    else:
        worker.last_login_at = datetime.utcnow()
        # 允许登录时补全资料(不覆盖已有值为 None)
        if body.display_name:
            worker.display_name = body.display_name
        if body.phone:
            worker.phone = body.phone
        if body.service_city:
            worker.service_city = body.service_city
    session.flush()

    return {
        "token": issue_worker_token(worker),
        "worker": {
            "id": worker.id, "display_name": worker.display_name,
            "worker_type": worker.worker_type, "service_city": worker.service_city,
            "is_verified": worker.is_verified,
        },
    }


@router.get("/me")
def worker_me(worker: MarketplaceWorker = Depends(get_current_worker)):
    return {
        "id": worker.id, "display_name": worker.display_name, "phone": worker.phone,
        "worker_type": worker.worker_type, "service_city": worker.service_city,
        "is_verified": worker.is_verified,
    }


# ─────────────────────────── 拖车大厅 ───────────────────────────

@router.get("/tow-orders")
def feed_tow_orders(
    city: Optional[str] = Query(None),
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    rows = marketplace_repo.list_published_tow_orders(session, city=city)
    return [marketplace_service.tow_order_feed_dict(o) for o in rows]


@router.get("/tow-orders/{order_id}")
def worker_tow_detail(
    order_id: int,
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    order = marketplace_repo.get_tow_order_any_tenant(session, order_id)
    # 仅 published(任何人可看)或本人已接的单可见
    if not order or (order.status != "published" and order.accepted_by != worker.id):
        raise TowOrderNotFound()
    reveal = order.accepted_by == worker.id
    return marketplace_service.tow_order_detail_dict(order, reveal_contact=reveal)


def _worker_advance_tow(session, request, worker, order_id, expect, target, ts_field, action):
    order = marketplace_repo.get_tow_order_any_tenant(session, order_id)
    if not order:
        raise TowOrderNotFound()
    if expect == "published":
        # accept:必须仍是 published
        if order.status != "published":
            raise marketplace_service.InvalidStateTransition("订单已被接走或已取消")
    else:
        # pickup/deliver:必须是本人接的单
        if order.accepted_by != worker.id:
            raise TowOrderNotFound()
    marketplace_service.assert_tow_transition(order.status, target)
    order.status = target
    setattr(order, ts_field, datetime.utcnow())
    if target == "accepted":
        order.accepted_by = worker.id
    marketplace_repo.add_tow_event(
        session, order_id=order.id, actor_type="worker", actor_id=worker.id,
        event_type="status_change", payload_json=f'{{"to": "{target}"}}',
    )
    audit_service.record(
        session, request, action=action, tenant_id=order.tenant_id, user_id=None,
        resource_type="tow_order", resource_id=order.id,
        after={"worker_id": worker.id, "status": target},
    )
    return marketplace_service.tow_order_detail_dict(order, reveal_contact=True)


@router.post("/tow-orders/{order_id}/accept")
def accept_tow_order(
    order_id: int, request: Request,
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    rate_limit_service.enforce_request_limit(
        request, scope="marketplace.worker_accept", limit=settings.rate_limit_write_max_requests
    )
    return _worker_advance_tow(
        session, request, worker, order_id, "published", "accepted", "accepted_at", "tow_order_accept"
    )


@router.post("/tow-orders/{order_id}/pickup")
def pickup_tow_order(
    order_id: int, request: Request,
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    return _worker_advance_tow(
        session, request, worker, order_id, "owned", "in_transit", "picked_up_at", "tow_order_pickup"
    )


@router.post("/tow-orders/{order_id}/deliver")
def deliver_tow_order(
    order_id: int, request: Request,
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    return _worker_advance_tow(
        session, request, worker, order_id, "owned", "delivered", "delivered_at", "tow_order_deliver"
    )


@router.get("/my/tow-orders")
def my_tow_orders(
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    rows = marketplace_repo.list_tow_orders_for_worker(session, worker_id=worker.id)
    return [marketplace_service.tow_order_detail_dict(o, reveal_contact=True) for o in rows]


# ─────────────────────────── 拍卖大厅 ───────────────────────────

@router.get("/auctions")
def feed_auctions(
    city: Optional[str] = Query(None),
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    rows = marketplace_repo.list_live_auctions(session, city=city)
    return [marketplace_service.auction_feed_dict(a) for a in rows]


@router.get("/auctions/{listing_id}")
def worker_auction_detail(
    listing_id: int,
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    listing = marketplace_repo.get_auction_any_tenant(session, listing_id)
    if not listing or listing.status not in ("live", "ended_sold", "ended_unsold", "settled"):
        raise AuctionNotFound()
    return marketplace_service.auction_detail_dict(listing, reveal_vin=False)


class BidBody(BaseModel):
    amount: float = Field(..., gt=0)


@router.post("/auctions/{listing_id}/bid")
def place_bid(
    listing_id: int, body: BidBody, request: Request,
    worker: MarketplaceWorker = Depends(get_current_worker),
    session: Session = Depends(get_db_session),
):
    rate_limit_service.enforce_request_limit(
        request, scope="marketplace.worker_bid", limit=settings.rate_limit_write_max_requests
    )
    listing = marketplace_repo.get_auction_any_tenant(session, listing_id)
    if not listing or listing.status != "live":
        raise AuctionNotFound()

    now = datetime.utcnow()
    if listing.starts_at and now < listing.starts_at:
        raise AuctionNotBiddable("竞拍尚未开始")
    if listing.ends_at and now > listing.ends_at:
        raise AuctionNotBiddable("竞拍已结束")

    floor = listing.current_price or listing.start_price
    min_acceptable = floor + listing.min_increment
    if body.amount < min_acceptable:
        raise BidTooLow(f"出价需 ≥ {min_acceptable:.0f}(当前 {floor:.0f} + 加价幅度 {listing.min_increment:.0f})")

    marketplace_repo.create_bid(
        session, listing_id=listing.id, worker_id=worker.id, amount=body.amount
    )
    listing.current_price = body.amount
    listing.bid_count = (listing.bid_count or 0) + 1
    audit_service.record(
        session, request, action="auction_bid", tenant_id=listing.tenant_id, user_id=None,
        resource_type="auction_listing", resource_id=listing.id,
        after={"worker_id": worker.id, "amount": body.amount},
    )
    return {
        "listing_id": listing.id, "current_price": listing.current_price,
        "bid_count": listing.bid_count, "your_amount": body.amount,
    }
