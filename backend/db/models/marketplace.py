"""P2 任务市场 ORM:拖车订单 + 拍卖标的 + 接单方(小程序)用户池。

发布方 = 现有 tenant 用户(web 系统);接单方 = 独立微信 openid 用户池,
不进 tenant 体系。敏感字段(车牌/VIN/取车地址/联系电话)全量入库,
对公开 feed 的脱敏在 service 层做(services/marketplace_service.py)。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class MarketplaceWorker(Base):
    """接单方:拖车师傅 / 车商。微信小程序登录(openid)。"""

    __tablename__ = "marketplace_workers"
    __table_args__ = (
        UniqueConstraint("wechat_openid", name="uq_marketplace_workers_openid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wechat_openid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    wechat_unionid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # tow_driver / dealer / both
    worker_type: Mapped[str] = mapped_column(String(32), nullable=False, default="tow_driver")
    service_city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class TowOrder(Base):
    """拖车订单。状态机:
    published -> accepted -> in_transit -> delivered -> confirmed -> settled
    published/accepted -> cancelled
    """

    __tablename__ = "tow_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    order_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    asset_package_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("asset_packages.id", ondelete="SET NULL"), nullable=True
    )

    # ---- 车辆 ----
    vehicle_desc: Mapped[str] = mapped_column(String(255), nullable=False)
    plate_no: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    drivable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_keys: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    condition_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- 取车点(详细地址 + 联系人接单后可见) ----
    pickup_province: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pickup_city: Mapped[str] = mapped_column(String(64), nullable=False)
    pickup_district: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pickup_address: Mapped[str] = mapped_column(String(512), nullable=False)
    pickup_contact_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pickup_contact_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ---- 交付点 ----
    dropoff_address: Mapped[str] = mapped_column(String(512), nullable=False)
    dropoff_contact_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    dropoff_contact_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ---- 任务 ----
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 自由文本/JSON:地库 / 平板车 / 无钥匙拖车 等
    special_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reward_amount: Mapped[float] = mapped_column(Float, nullable=False)

    # ---- 状态机 ----
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="published", index=True
    )
    accepted_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("marketplace_workers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # v1 结算 = 平台记账 + 线下转账,备注里记转账凭证说明
    settlement_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TowOrderEvent(Base):
    """拖车订单事件链:状态流转 / 取证照片 / 备注。"""

    __tablename__ = "tow_order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tow_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # publisher / worker / system
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # status_change / photo / note
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_storage_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class AuctionListing(Base):
    """拍卖标的。状态机:
    upcoming -> live -> ended_sold / ended_unsold -> settled
    upcoming/live(无出价) -> cancelled
    """

    __tablename__ = "auction_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    listing_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    asset_package_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("asset_packages.id", ondelete="SET NULL"), nullable=True
    )

    # ---- 标的车辆 ----
    vehicle_desc: Mapped[str] = mapped_column(String(255), nullable=False)
    model_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    first_registration: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    mileage_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    emission_standard: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    key_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transfer_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_registration_cert: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_driving_license: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    mortgage_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    violation_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)

    # ---- 车况 ----
    accident_level: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    exterior_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    interior_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mechanical_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    photos_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- 看车 ----
    location_city: Mapped[str] = mapped_column(String(64), nullable=False)
    viewing_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    viewing_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    viewing_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ---- 竞拍 ----
    start_price: Mapped[float] = mapped_column(Float, nullable=False)
    deposit_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    min_increment: Mapped[float] = mapped_column(Float, nullable=False, default=1000)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # ---- 状态/成交(反规范化字段,出价时同步更新) ----
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="upcoming", index=True
    )
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    winner_worker_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("marketplace_workers.id", ondelete="SET NULL"), nullable=True
    )
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    settlement_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuctionBid(Base):
    __tablename__ = "auction_bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("auction_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("marketplace_workers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
