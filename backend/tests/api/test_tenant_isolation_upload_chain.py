"""P1 租户隔离硬化:上传全链路跨租户测试 + 上传配额 + 数据删除。

覆盖:
- 上传后存储 key 带租户前缀
- B 租户读不到/删不掉 A 租户的资产包(全链路 404)
- 属主可删除自己的资产包(DB 行 + 存储对象一起删)
- 有订阅租户按套餐配额限制上传,无订阅租户(内部/私有化)不限
"""
import io

import openpyxl
from fastapi.testclient import TestClient

from main import app
from db.models.subscription import TenantSubscription
from db.session import get_db_session
from repositories import asset_package_repo, plan_repo, tenant_repo, user_repo
from services.password_service import hash_password
from services.storage.factory import get_storage

PASSWORD = "Passw0rd!1"


def _xlsx_bytes(rows: int = 1) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["车型描述", "VIN"])
    for i in range(rows):
        ws.append([f"测试车{i}", ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _run_in_session(fn):
    gen = get_db_session()
    session = next(gen)
    try:
        result = fn(session)
        session.commit()
        return result
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _seed_tenant_user(code: str, email: str) -> int:
    """建 tenant + operator 用户 + membership,返回 tenant_id。"""

    def _do(session):
        tenant = tenant_repo.get_or_create_tenant(
            session, code=code, name=code.upper()
        )
        user = user_repo.get_user_by_email(session, email)
        if user is None:
            user = user_repo.create_user(
                session,
                email=email,
                password_hash=hash_password(PASSWORD),
                role="operator",
                display_name=email,
            )
        tenant_repo.create_membership(
            session, user_id=user.id, tenant_id=tenant.id, role="operator"
        )
        user_repo.set_default_tenant(session, user.id, tenant.id)
        return tenant.id

    return _run_in_session(_do)


def _login(client: TestClient, email: str):
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text


def _upload(client: TestClient, filename: str = "pkg.xlsx"):
    return client.post(
        "/api/asset-package/upload",
        files={
            "file": (
                filename,
                _xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


def _subscribe(
    tenant_id: int,
    included_asset_packages: int,
    status: str = "trial",
    expires_at=None,
) -> None:
    """给租户配一个限额套餐(默认模拟 trial_onboarding 创建的试用订阅)。"""

    def _do(session):
        plan = plan_repo.create_plan(
            session,
            code=f"test-quota-{tenant_id}-{included_asset_packages}-{status}",
            name="测试限额套餐",
            included_asset_packages=included_asset_packages,
        )
        session.flush()
        session.add(
            TenantSubscription(
                tenant_id=tenant_id,
                plan_id=plan.id,
                status=status,
                is_current=True,
                expires_at=expires_at,
            )
        )

    _run_in_session(_do)


def test_upload_storage_key_has_tenant_prefix():
    client = TestClient(app)
    tenant_id = _seed_tenant_user("iso-prefix-t", "iso-prefix@example.com")
    _login(client, "iso-prefix@example.com")

    resp = _upload(client)
    assert resp.status_code == 200, resp.text
    package_id = resp.json()["package_id"]

    def _check(session):
        pkg = asset_package_repo.get_package_by_id(
            session, package_id, tenant_id=tenant_id
        )
        assert pkg is not None
        assert pkg.storage_key.startswith(f"tenants/{tenant_id}/"), pkg.storage_key
        # 存储对象真实可读
        assert get_storage().get_bytes(pkg.storage_key)

    _run_in_session(_check)


def test_cross_tenant_full_chain_denied():
    client_a = TestClient(app)
    client_b = TestClient(app)
    _seed_tenant_user("iso-chain-a", "iso-chain-a@example.com")
    _seed_tenant_user("iso-chain-b", "iso-chain-b@example.com")
    _login(client_a, "iso-chain-a@example.com")
    _login(client_b, "iso-chain-b@example.com")

    resp = _upload(client_a)
    assert resp.status_code == 200, resp.text
    package_id = resp.json()["package_id"]

    # B 读不到
    assert client_b.get(f"/api/asset-package/{package_id}").status_code == 404
    # B 出价分析不行
    r = client_b.post(
        f"/api/asset-package/{package_id}/buyer-offer-analysis",
        json={"buyer_offer_price": 100000},
    )
    assert r.status_code == 404, r.text
    # B 删不掉
    assert client_b.delete(f"/api/asset-package/{package_id}").status_code == 404
    # A 的数据安然无恙
    assert client_a.get(f"/api/asset-package/{package_id}").status_code == 200


def test_owner_can_delete_package_with_storage():
    client = TestClient(app)
    tenant_id = _seed_tenant_user("iso-del-t", "iso-del@example.com")
    _login(client, "iso-del@example.com")

    resp = _upload(client)
    assert resp.status_code == 200, resp.text
    package_id = resp.json()["package_id"]

    def _get_key(session):
        pkg = asset_package_repo.get_package_by_id(
            session, package_id, tenant_id=tenant_id
        )
        return pkg.storage_key

    storage_key = _run_in_session(_get_key)

    r = client.delete(f"/api/asset-package/{package_id}")
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": True, "package_id": package_id}

    # DB 行已删
    assert client.get(f"/api/asset-package/{package_id}").status_code == 404
    # 存储对象已删
    try:
        get_storage().get_bytes(storage_key)
        assert False, "storage object should be deleted"
    except FileNotFoundError:
        pass


def test_upload_quota_enforced_for_trial_tenant():
    """trial 状态订阅(trial_onboarding 创建)必须吃配额限制。"""
    client = TestClient(app)
    tenant_id = _seed_tenant_user("iso-quota-t", "iso-quota@example.com")
    _subscribe(tenant_id, included_asset_packages=1, status="trial")
    _login(client, "iso-quota@example.com")

    assert _upload(client, "first.xlsx").status_code == 200

    resp = _upload(client, "second.xlsx")
    assert resp.status_code == 409, resp.text
    body = resp.json()["error"]
    assert body["code"] == "QUOTA_EXCEEDED"
    assert body["details"]["quota_limit"] == 1


def test_upload_denied_for_expired_trial():
    """试用到期后不能再上传(区别于无订阅的内部租户)。"""
    from datetime import datetime, timedelta

    client = TestClient(app)
    tenant_id = _seed_tenant_user("iso-expired-t", "iso-expired@example.com")
    _subscribe(
        tenant_id,
        included_asset_packages=10,
        status="trial",
        expires_at=datetime.utcnow() - timedelta(days=1),
    )
    _login(client, "iso-expired@example.com")

    resp = _upload(client)
    assert resp.status_code == 409, resp.text
    body = resp.json()["error"]
    assert body["code"] == "QUOTA_EXCEEDED"
    assert body["details"]["reason"] == "subscription_expired"


def test_upload_unlimited_without_subscription():
    """内部/私有化租户没有订阅,不受配额限制。"""
    client = TestClient(app)
    _seed_tenant_user("iso-nosub-t", "iso-nosub@example.com")
    _login(client, "iso-nosub@example.com")

    assert _upload(client, "a.xlsx").status_code == 200
    assert _upload(client, "b.xlsx").status_code == 200
