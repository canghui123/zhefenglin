"""P2 任务市场业务逻辑:状态机 + 公开 feed 脱敏序列化。

设计要点:
- 拖车订单/拍卖标的的敏感字段(车牌/VIN/取车详址/联系电话)全量入库;
  对小程序公开 feed 做脱敏,接单/中标后才向当事 worker 披露联系方式。
- 状态流转集中在本模块,非法流转抛 InvalidStateTransition。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from db.models.marketplace import AuctionListing, TowOrder
from services.data_masking import _mask_vin  # 复用 B6 VIN 脱敏

from errors import BusinessError


class InvalidStateTransition(BusinessError):
    def __init__(self, detail: str = "当前状态不允许该操作"):
        super().__init__("INVALID_STATE_TRANSITION", detail, 409)


# ---- 拖车订单状态机 ----
TOW_TRANSITIONS = {
    "published": {"accepted", "cancelled"},
    "accepted": {"in_transit", "cancelled"},
    "in_transit": {"delivered"},
    "delivered": {"confirmed"},
    "confirmed": {"settled"},
    "settled": set(),
    "cancelled": set(),
}

# ---- 拍卖标的状态机 ----
AUCTION_TRANSITIONS = {
    "upcoming": {"live", "cancelled"},
    "live": {"ended_sold", "ended_unsold", "cancelled"},
    "ended_sold": {"settled"},
    "ended_unsold": set(),
    "settled": set(),
    "cancelled": set(),
}


def assert_tow_transition(current: str, target: str) -> None:
    if target not in TOW_TRANSITIONS.get(current, set()):
        raise InvalidStateTransition(f"拖车订单不能从 {current} 变为 {target}")


def assert_auction_transition(current: str, target: str) -> None:
    if target not in AUCTION_TRANSITIONS.get(current, set()):
        raise InvalidStateTransition(f"拍卖标的不能从 {current} 变为 {target}")


def _mask_plate(plate: Optional[str]) -> Optional[str]:
    """车牌脱敏:保留省份简称+字母,中间打码,留尾号。浙A12345 -> 浙A***5。"""
    if not plate:
        return None
    if len(plate) <= 3:
        return plate[:2] + "*"
    return plate[:2] + "*" * (len(plate) - 3) + plate[-1:]


def _mask_vin_value(vin: Optional[str]) -> Optional[str]:
    if not vin or len(vin) < 6:
        return None
    return vin[:3] + "*" * (len(vin) - 6) + vin[-3:]


# ---------- 拖车订单序列化 ----------

def tow_order_feed_dict(order: TowOrder) -> dict:
    """公开大厅卡片:脱敏车牌/VIN,只给城市,不露详址和联系电话。"""
    return {
        "id": order.id,
        "order_no": order.order_no,
        "vehicle_desc": order.vehicle_desc,
        "plate_no": _mask_plate(order.plate_no),
        "vin": _mask_vin_value(order.vin),
        "drivable": order.drivable,
        "has_keys": order.has_keys,
        "condition_notes": order.condition_notes,
        "pickup_city": order.pickup_city,
        "pickup_district": order.pickup_district,
        "dropoff_city_hint": _city_hint(order.dropoff_address),
        "distance_km": order.distance_km,
        "deadline_at": _iso(order.deadline_at),
        "special_requirements": order.special_requirements,
        "reward_amount": order.reward_amount,
        "status": order.status,
        "created_at": _iso(order.created_at),
    }


def tow_order_detail_dict(order: TowOrder, *, reveal_contact: bool) -> dict:
    """订单详情:reveal_contact=True(接单本人)才返回详址+联系电话。"""
    data = tow_order_feed_dict(order)
    data["accepted_by"] = order.accepted_by
    data["accepted_at"] = _iso(order.accepted_at)
    data["picked_up_at"] = _iso(order.picked_up_at)
    data["delivered_at"] = _iso(order.delivered_at)
    data["confirmed_at"] = _iso(order.confirmed_at)
    if reveal_contact:
        data["plate_no"] = order.plate_no
        data["vin"] = order.vin
        data["pickup_address"] = order.pickup_address
        data["pickup_contact_name"] = order.pickup_contact_name
        data["pickup_contact_phone"] = order.pickup_contact_phone
        data["dropoff_address"] = order.dropoff_address
        data["dropoff_contact_name"] = order.dropoff_contact_name
        data["dropoff_contact_phone"] = order.dropoff_contact_phone
    return data


def tow_order_owner_dict(order: TowOrder) -> dict:
    """发布方视角:全量(发布方本就拥有这些数据)。"""
    return tow_order_detail_dict(order, reveal_contact=True)


# ---------- 拍卖标的序列化 ----------

def auction_feed_dict(listing: AuctionListing) -> dict:
    """竞拍大厅卡片:脱敏 VIN,看车只给城市。"""
    return {
        "id": listing.id,
        "listing_no": listing.listing_no,
        "vehicle_desc": listing.vehicle_desc,
        "model_year": listing.model_year,
        "mileage_km": listing.mileage_km,
        "emission_standard": listing.emission_standard,
        "accident_level": listing.accident_level,
        "exterior_score": listing.exterior_score,
        "interior_score": listing.interior_score,
        "mechanical_score": listing.mechanical_score,
        "location_city": listing.location_city,
        "start_price": listing.start_price,
        "current_price": listing.current_price or listing.start_price,
        "deposit_amount": listing.deposit_amount,
        "min_increment": listing.min_increment,
        "bid_count": listing.bid_count,
        "starts_at": _iso(listing.starts_at),
        "ends_at": _iso(listing.ends_at),
        "status": listing.status,
    }


def auction_detail_dict(listing: AuctionListing, *, reveal_vin: bool = False) -> dict:
    data = auction_feed_dict(listing)
    data.update({
        "first_registration": listing.first_registration,
        "key_count": listing.key_count,
        "transfer_count": listing.transfer_count,
        "has_registration_cert": listing.has_registration_cert,
        "has_driving_license": listing.has_driving_license,
        "mortgage_status": listing.mortgage_status,
        "violation_status": listing.violation_status,
        "vin": listing.vin if reveal_vin else _mask_vin_value(listing.vin),
        "photos_json": listing.photos_json,
        "viewing_start": _iso(listing.viewing_start),
        "viewing_end": _iso(listing.viewing_end),
        "viewing_contact": listing.viewing_contact if reveal_vin else None,
        "winner_worker_id": listing.winner_worker_id,
    })
    return data


# ---------- helpers ----------

def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _city_hint(address: Optional[str]) -> Optional[str]:
    """从交付地址里粗取前 6 个字作为城市提示(不露完整地址)。"""
    if not address:
        return None
    return address[:6]
