"""P2 任务市场测试:发布方/接单方全链路 + 脱敏 + 跨租户隔离。

覆盖:
- 拖车订单:发布 → worker 接单 → 取车 → 交付 → 发布方确认 → 结算
- 公开 feed 脱敏(车牌/VIN),联系方式仅向接单本人披露
- 拍卖:创建 → go-live → worker 出价(加价校验)→ end → 结算
- 跨租户:B 租户看不到/改不动 A 的订单
- worker 登录走 mock 微信(code 稳定派生 openid)
"""
import io
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import tenant_repo, user_repo
from services.password_service import hash_password

PASSWORD = "Passw0rd!1"


def _seed_publisher(code: str, email: str) -> int:
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(session, code=code, name=code.upper())
        user = user_repo.get_user_by_email(session, email)
        if user is None:
            user = user_repo.create_user(
                session, email=email, password_hash=hash_password(PASSWORD),
                role="operator", display_name=email,
            )
        tenant_repo.create_membership(session, user_id=user.id, tenant_id=tenant.id, role="operator")
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
        return tenant.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _login_publisher(client: TestClient, email: str):
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text


def _worker_token(client: TestClient, code: str, **profile) -> str:
    r = client.post("/api/m/auth/login", json={"code": code, **profile})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tow_payload(**over) -> dict:
    base = {
        "vehicle_desc": "2019 别克GL8",
        "plate_no": "浙A12345",
        "vin": "LSGW12345678ABCDE"[:17],
        "drivable": False,
        "has_keys": True,
        "pickup_city": "杭州",
        "pickup_address": "杭州市西湖区文三路 100 号地库 B2",
        "pickup_contact_name": "王经理",
        "pickup_contact_phone": "13800138000",
        "dropoff_address": "宁波市鄞州区某拍卖停车场",
        "reward_amount": 800,
    }
    base.update(over)
    return base


# ─────────────────────────── 拖车全链路 ───────────────────────────

def test_tow_order_full_lifecycle():
    pub = TestClient(app)
    wrk = TestClient(app)
    _seed_publisher("mkt-tow-a", "mkt-tow-a@example.com")
    _login_publisher(pub, "mkt-tow-a@example.com")

    # 发布
    r = pub.post("/api/marketplace/tow-orders", json=_tow_payload())
    assert r.status_code == 200, r.text
    order_id = r.json()["id"]
    # 发布方视角能看到完整联系方式
    assert r.json()["pickup_contact_phone"] == "13800138000"

    # worker 登录 + 看大厅(脱敏)
    token = _worker_token(wrk, "driver-001", display_name="张师傅", service_city="杭州")
    feed = wrk.get("/api/m/tow-orders", headers=_auth(token))
    assert feed.status_code == 200, feed.text
    card = next(c for c in feed.json() if c["id"] == order_id)
    assert card["plate_no"] == "浙A****5"  # 车牌脱敏:保留省份字母+尾号
    assert "pickup_contact_phone" not in card  # feed 不露电话
    assert card["pickup_city"] == "杭州"

    # 接单前看详情:published 可见但不露联系方式
    d0 = wrk.get(f"/api/m/tow-orders/{order_id}", headers=_auth(token))
    assert d0.status_code == 200
    assert d0.json().get("pickup_contact_phone") is None

    # 接单
    acc = wrk.post(f"/api/m/tow-orders/{order_id}/accept", headers=_auth(token))
    assert acc.status_code == 200, acc.text
    # 接单后联系方式 + 真实车牌披露
    assert acc.json()["pickup_contact_phone"] == "13800138000"
    assert acc.json()["plate_no"] == "浙A12345"

    # 取车 → 交付
    assert wrk.post(f"/api/m/tow-orders/{order_id}/pickup", headers=_auth(token)).status_code == 200
    assert wrk.post(f"/api/m/tow-orders/{order_id}/deliver", headers=_auth(token)).status_code == 200

    # 发布方确认 → 结算
    assert pub.post(f"/api/marketplace/tow-orders/{order_id}/confirm").status_code == 200
    s = pub.post(f"/api/marketplace/tow-orders/{order_id}/settle", json={"settlement_note": "已线下转账 800"})
    assert s.status_code == 200, s.text
    assert s.json()["status"] == "settled"


def test_tow_order_double_accept_rejected():
    pub = TestClient(app)
    w1 = TestClient(app)
    w2 = TestClient(app)
    _seed_publisher("mkt-tow-b", "mkt-tow-b@example.com")
    _login_publisher(pub, "mkt-tow-b@example.com")
    order_id = pub.post("/api/marketplace/tow-orders", json=_tow_payload()).json()["id"]

    t1 = _worker_token(w1, "driver-aa")
    t2 = _worker_token(w2, "driver-bb")
    assert w1.post(f"/api/m/tow-orders/{order_id}/accept", headers=_auth(t1)).status_code == 200
    # 第二个 worker 抢不到
    r2 = w2.post(f"/api/m/tow-orders/{order_id}/accept", headers=_auth(t2))
    assert r2.status_code == 409, r2.text


def test_tow_cross_tenant_isolation():
    pub_a = TestClient(app)
    pub_b = TestClient(app)
    _seed_publisher("mkt-iso-a", "mkt-iso-a@example.com")
    _seed_publisher("mkt-iso-b", "mkt-iso-b@example.com")
    _login_publisher(pub_a, "mkt-iso-a@example.com")
    _login_publisher(pub_b, "mkt-iso-b@example.com")

    order_id = pub_a.post("/api/marketplace/tow-orders", json=_tow_payload()).json()["id"]
    # B 看不到 A 的单
    assert pub_b.get(f"/api/marketplace/tow-orders/{order_id}").status_code == 404
    # B 取消不了 A 的单
    assert pub_b.post(f"/api/marketplace/tow-orders/{order_id}/cancel").status_code == 404
    # A 自己能看到
    assert pub_a.get(f"/api/marketplace/tow-orders/{order_id}").status_code == 200


def test_worker_cannot_pickup_others_order():
    pub = TestClient(app)
    w1 = TestClient(app)
    w2 = TestClient(app)
    _seed_publisher("mkt-tow-c", "mkt-tow-c@example.com")
    _login_publisher(pub, "mkt-tow-c@example.com")
    order_id = pub.post("/api/marketplace/tow-orders", json=_tow_payload()).json()["id"]

    t1 = _worker_token(w1, "driver-c1")
    t2 = _worker_token(w2, "driver-c2")
    w1.post(f"/api/m/tow-orders/{order_id}/accept", headers=_auth(t1))
    # w2 不是接单人,取车应 404
    assert w2.post(f"/api/m/tow-orders/{order_id}/pickup", headers=_auth(t2)).status_code == 404


# ─────────────────────────── 拍卖全链路 ───────────────────────────

def _auction_payload(**over) -> dict:
    now = datetime.utcnow()
    base = {
        "vehicle_desc": "2020 奥迪A6L",
        "model_year": 2020,
        "mileage_km": 65000,
        "location_city": "上海",
        "vin": "LFV2A21G7L3123456"[:17],
        "start_price": 180000,
        "deposit_amount": 10000,
        "min_increment": 2000,
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(hours=2)).isoformat(),
    }
    base.update(over)
    return base


def test_auction_full_lifecycle():
    pub = TestClient(app)
    w1 = TestClient(app)
    w2 = TestClient(app)
    _seed_publisher("mkt-auc-a", "mkt-auc-a@example.com")
    _login_publisher(pub, "mkt-auc-a@example.com")

    r = pub.post("/api/marketplace/auctions", json=_auction_payload())
    assert r.status_code == 200, r.text
    listing_id = r.json()["id"]
    assert r.json()["status"] == "upcoming"

    # 未 go-live 时 worker 大厅看不到
    t1 = _worker_token(w1, "bidder-1")
    assert all(a["id"] != listing_id for a in w1.get("/api/m/auctions", headers=_auth(t1)).json())

    # go-live
    assert pub.post(f"/api/marketplace/auctions/{listing_id}/go-live").status_code == 200
    feed = w1.get("/api/m/auctions", headers=_auth(t1)).json()
    card = next(a for a in feed if a["id"] == listing_id)
    assert card["current_price"] == 180000

    # worker 详情 VIN 脱敏
    det = w1.get(f"/api/m/auctions/{listing_id}", headers=_auth(t1)).json()
    assert "*" in det["vin"]

    # 出价过低被拒(< 180000 + 2000)
    low = w1.post(f"/api/m/auctions/{listing_id}/bid", json={"amount": 181000}, headers=_auth(t1))
    assert low.status_code == 409, low.text

    # 合法出价
    b1 = w1.post(f"/api/m/auctions/{listing_id}/bid", json={"amount": 182000}, headers=_auth(t1))
    assert b1.status_code == 200, b1.text
    assert b1.json()["current_price"] == 182000

    # 第二个 worker 加价
    t2 = _worker_token(w2, "bidder-2")
    b2 = w2.post(f"/api/m/auctions/{listing_id}/bid", json={"amount": 184000}, headers=_auth(t2))
    assert b2.status_code == 200, b2.text
    assert b2.json()["bid_count"] == 2

    # 结束:最高价 184000 的 w2 中标
    end = pub.post(f"/api/marketplace/auctions/{listing_id}/end")
    assert end.status_code == 200, end.text
    assert end.json()["status"] == "ended_sold"
    assert end.json()["current_price"] == 184000

    # 结算
    s = pub.post(f"/api/marketplace/auctions/{listing_id}/settle", json={"settlement_note": "保证金抵扣"})
    assert s.status_code == 200
    assert s.json()["status"] == "settled"


def test_auction_end_unsold_without_bids():
    pub = TestClient(app)
    _seed_publisher("mkt-auc-b", "mkt-auc-b@example.com")
    _login_publisher(pub, "mkt-auc-b@example.com")
    listing_id = pub.post("/api/marketplace/auctions", json=_auction_payload()).json()["id"]
    pub.post(f"/api/marketplace/auctions/{listing_id}/go-live")
    end = pub.post(f"/api/marketplace/auctions/{listing_id}/end")
    assert end.status_code == 200
    assert end.json()["status"] == "ended_unsold"


def test_worker_login_stable_openid():
    """同一 code 复用同一 worker(mock openid 稳定派生)。"""
    c = TestClient(app)
    r1 = c.post("/api/m/auth/login", json={"code": "same-code"})
    r2 = c.post("/api/m/auth/login", json={"code": "same-code"})
    assert r1.json()["worker"]["id"] == r2.json()["worker"]["id"]


def test_worker_endpoints_require_token():
    c = TestClient(app)
    assert c.get("/api/m/tow-orders").status_code == 401
    assert c.get("/api/m/auctions").status_code == 401
