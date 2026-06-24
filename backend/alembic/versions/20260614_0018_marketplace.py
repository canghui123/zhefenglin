"""P2 task marketplace: tow orders, auction listings, worker pool.

发布方(tenant 用户)发布拖车/拍卖任务,接单方(微信小程序 worker)接单/出价。
- marketplace_workers: 独立微信 openid 用户池(不进 tenant 体系)
- tow_orders + tow_order_events: 拖车订单 + 事件链(状态流转/取证照片)
- auction_listings + auction_bids: 拍卖标的 + 出价

Revision ID: 20260614_0018
Revises: 20260604_0017
Create Date: 2026-06-14
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260614_0018"
down_revision: Union[str, None] = "20260604_0017"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "marketplace_workers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("wechat_openid", sa.String(length=128), nullable=False),
        sa.Column("wechat_unionid", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("worker_type", sa.String(length=32), nullable=False, server_default="tow_driver"),
        sa.Column("service_city", sa.String(length=64), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("wechat_openid", name="uq_marketplace_workers_openid"),
    )
    op.create_index(
        op.f("ix_marketplace_workers_wechat_openid"),
        "marketplace_workers",
        ["wechat_openid"],
    )

    op.create_table(
        "tow_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_no", sa.String(length=32), nullable=True),
        sa.Column("asset_package_id", sa.Integer(), sa.ForeignKey("asset_packages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("vehicle_desc", sa.String(length=255), nullable=False),
        sa.Column("plate_no", sa.String(length=16), nullable=True),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("drivable", sa.Boolean(), nullable=True),
        sa.Column("has_keys", sa.Boolean(), nullable=True),
        sa.Column("condition_notes", sa.Text(), nullable=True),
        sa.Column("pickup_province", sa.String(length=32), nullable=True),
        sa.Column("pickup_city", sa.String(length=64), nullable=False),
        sa.Column("pickup_district", sa.String(length=64), nullable=True),
        sa.Column("pickup_address", sa.String(length=512), nullable=False),
        sa.Column("pickup_contact_name", sa.String(length=64), nullable=True),
        sa.Column("pickup_contact_phone", sa.String(length=32), nullable=True),
        sa.Column("dropoff_address", sa.String(length=512), nullable=False),
        sa.Column("dropoff_contact_name", sa.String(length=64), nullable=True),
        sa.Column("dropoff_contact_phone", sa.String(length=32), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(), nullable=True),
        sa.Column("special_requirements", sa.Text(), nullable=True),
        sa.Column("reward_amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="published"),
        sa.Column("accepted_by", sa.Integer(), sa.ForeignKey("marketplace_workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("settlement_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_tow_orders_tenant_id"), "tow_orders", ["tenant_id"])
    op.create_index(op.f("ix_tow_orders_order_no"), "tow_orders", ["order_no"])
    op.create_index(op.f("ix_tow_orders_status"), "tow_orders", ["status"])
    op.create_index(op.f("ix_tow_orders_accepted_by"), "tow_orders", ["accepted_by"])

    op.create_table(
        "tow_order_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("tow_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("photo_storage_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_tow_order_events_order_id"), "tow_order_events", ["order_id"])

    op.create_table(
        "auction_listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("listing_no", sa.String(length=32), nullable=True),
        sa.Column("asset_package_id", sa.Integer(), sa.ForeignKey("asset_packages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("vehicle_desc", sa.String(length=255), nullable=False),
        sa.Column("model_year", sa.Integer(), nullable=True),
        sa.Column("first_registration", sa.String(length=32), nullable=True),
        sa.Column("mileage_km", sa.Float(), nullable=True),
        sa.Column("emission_standard", sa.String(length=32), nullable=True),
        sa.Column("key_count", sa.Integer(), nullable=True),
        sa.Column("transfer_count", sa.Integer(), nullable=True),
        sa.Column("has_registration_cert", sa.Boolean(), nullable=True),
        sa.Column("has_driving_license", sa.Boolean(), nullable=True),
        sa.Column("mortgage_status", sa.String(length=64), nullable=True),
        sa.Column("violation_status", sa.String(length=255), nullable=True),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("accident_level", sa.String(length=8), nullable=True),
        sa.Column("exterior_score", sa.Integer(), nullable=True),
        sa.Column("interior_score", sa.Integer(), nullable=True),
        sa.Column("mechanical_score", sa.Integer(), nullable=True),
        sa.Column("photos_json", sa.Text(), nullable=True),
        sa.Column("location_city", sa.String(length=64), nullable=False),
        sa.Column("viewing_start", sa.DateTime(), nullable=True),
        sa.Column("viewing_end", sa.DateTime(), nullable=True),
        sa.Column("viewing_contact", sa.String(length=255), nullable=True),
        sa.Column("start_price", sa.Float(), nullable=False),
        sa.Column("deposit_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("min_increment", sa.Float(), nullable=False, server_default="1000"),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="upcoming"),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("bid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("winner_worker_id", sa.Integer(), sa.ForeignKey("marketplace_workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("settlement_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_auction_listings_tenant_id"), "auction_listings", ["tenant_id"])
    op.create_index(op.f("ix_auction_listings_listing_no"), "auction_listings", ["listing_no"])
    op.create_index(op.f("ix_auction_listings_status"), "auction_listings", ["status"])

    op.create_table(
        "auction_bids",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("auction_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("marketplace_workers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_auction_bids_listing_id"), "auction_bids", ["listing_id"])
    op.create_index(op.f("ix_auction_bids_worker_id"), "auction_bids", ["worker_id"])


def downgrade() -> None:
    op.drop_table("auction_bids")
    op.drop_table("auction_listings")
    op.drop_table("tow_order_events")
    op.drop_table("tow_orders")
    op.drop_table("marketplace_workers")
