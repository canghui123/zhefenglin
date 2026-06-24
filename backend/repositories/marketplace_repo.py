"""P2 任务市场数据访问层。

发布方查询一律带 tenant_id 过滤(租户隔离);接单方(worker)查询走
公开 feed(仅 published/live 状态)或 worker 自己接的单。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.marketplace import (
    AuctionBid,
    AuctionListing,
    MarketplaceWorker,
    TowOrder,
    TowOrderEvent,
)


# ---------- worker ----------

def get_worker_by_openid(session: Session, openid: str) -> Optional[MarketplaceWorker]:
    return session.scalars(
        select(MarketplaceWorker).where(MarketplaceWorker.wechat_openid == openid)
    ).first()


def create_worker(session: Session, **fields) -> MarketplaceWorker:
    worker = MarketplaceWorker(**fields)
    session.add(worker)
    session.flush()
    return worker


# ---------- tow orders (publisher side, tenant-scoped) ----------

def create_tow_order(session: Session, **fields) -> TowOrder:
    order = TowOrder(**fields)
    session.add(order)
    session.flush()
    return order


def get_tow_order(session: Session, order_id: int, *, tenant_id: int) -> Optional[TowOrder]:
    return session.scalars(
        select(TowOrder).where(TowOrder.id == order_id, TowOrder.tenant_id == tenant_id)
    ).first()


def get_tow_order_any_tenant(session: Session, order_id: int) -> Optional[TowOrder]:
    """worker 侧按 id 取(不限租户),可见性由 status / accepted_by 判定。"""
    return session.get(TowOrder, order_id)


def list_tow_orders_for_tenant(
    session: Session, *, tenant_id: int, status: Optional[str] = None
) -> List[TowOrder]:
    stmt = select(TowOrder).where(TowOrder.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(TowOrder.status == status)
    return list(session.scalars(stmt.order_by(TowOrder.id.desc())))


def list_published_tow_orders(
    session: Session, *, city: Optional[str] = None, limit: int = 50
) -> List[TowOrder]:
    stmt = select(TowOrder).where(TowOrder.status == "published")
    if city:
        stmt = stmt.where(TowOrder.pickup_city == city)
    return list(session.scalars(stmt.order_by(TowOrder.id.desc()).limit(limit)))


def list_tow_orders_for_worker(session: Session, *, worker_id: int) -> List[TowOrder]:
    return list(
        session.scalars(
            select(TowOrder)
            .where(TowOrder.accepted_by == worker_id)
            .order_by(TowOrder.id.desc())
        )
    )


def add_tow_event(session: Session, **fields) -> TowOrderEvent:
    event = TowOrderEvent(**fields)
    session.add(event)
    session.flush()
    return event


def list_tow_events(session: Session, *, order_id: int) -> List[TowOrderEvent]:
    return list(
        session.scalars(
            select(TowOrderEvent)
            .where(TowOrderEvent.order_id == order_id)
            .order_by(TowOrderEvent.id.asc())
        )
    )


# ---------- auctions ----------

def create_auction(session: Session, **fields) -> AuctionListing:
    listing = AuctionListing(**fields)
    session.add(listing)
    session.flush()
    return listing


def get_auction(session: Session, listing_id: int, *, tenant_id: int) -> Optional[AuctionListing]:
    return session.scalars(
        select(AuctionListing).where(
            AuctionListing.id == listing_id, AuctionListing.tenant_id == tenant_id
        )
    ).first()


def get_auction_any_tenant(session: Session, listing_id: int) -> Optional[AuctionListing]:
    return session.get(AuctionListing, listing_id)


def list_auctions_for_tenant(
    session: Session, *, tenant_id: int, status: Optional[str] = None
) -> List[AuctionListing]:
    stmt = select(AuctionListing).where(AuctionListing.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(AuctionListing.status == status)
    return list(session.scalars(stmt.order_by(AuctionListing.id.desc())))


def list_live_auctions(
    session: Session, *, city: Optional[str] = None, limit: int = 50
) -> List[AuctionListing]:
    stmt = select(AuctionListing).where(AuctionListing.status == "live")
    if city:
        stmt = stmt.where(AuctionListing.location_city == city)
    return list(session.scalars(stmt.order_by(AuctionListing.ends_at.asc()).limit(limit)))


def create_bid(session: Session, **fields) -> AuctionBid:
    bid = AuctionBid(**fields)
    session.add(bid)
    session.flush()
    return bid


def list_bids(session: Session, *, listing_id: int) -> List[AuctionBid]:
    return list(
        session.scalars(
            select(AuctionBid)
            .where(AuctionBid.listing_id == listing_id)
            .order_by(AuctionBid.amount.desc(), AuctionBid.id.desc())
        )
    )
