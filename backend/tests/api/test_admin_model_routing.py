def test_model_routing_requires_feature_entitlement_for_list():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "routing-standard@example.com", role="manager", tenant_code="routing-standard"
    )
    seed_subscription(tenant_code="routing-standard", plan_code="standard")

    response = client.get("/api/admin/model-routing")

    assert response.status_code == 403, response.text
    body = response.json()
    assert body["error"]["code"] == "FEATURE_NOT_ENABLED"
    assert body["error"]["details"]["feature_key"] == "routing.model_control"


def test_model_routing_allows_enabled_plan_and_admin_mutation():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "routing-pro@example.com", role="admin", tenant_code="routing-pro"
    )
    seed_subscription(tenant_code="routing-pro", plan_code="pro_manager")

    listed = client.get("/api/admin/model-routing")
    assert listed.status_code == 200, listed.text
    assert isinstance(listed.json(), list)

    # 租户管理员只能写 tenant scope；无需显式传 scope，服务端会强制
    upsert = client.put(
        "/api/admin/model-routing",
        json={
            "task_type": "batch_report",
            "preferred_model": "qwen-plus",
            "fallback_model": "qwen-turbo",
            "allow_batch": True,
            "allow_search": False,
            "allow_high_cost_mode": False,
            "prompt_version": "v2",
            "is_active": True,
        },
    )
    assert upsert.status_code == 200, upsert.text
    assert upsert.json()["id"] > 0


def test_model_routing_rejects_global_scope_from_tenant_admin():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "routing-reject-global@example.com", role="admin", tenant_code="routing-reject-global"
    )
    seed_subscription(tenant_code="routing-reject-global", plan_code="pro_manager")

    response = client.put(
        "/api/admin/model-routing",
        json={
            "scope": "global",
            "task_type": "batch_report",
            "preferred_model": "qwen-plus",
            "prompt_version": "v1",
            "is_active": True,
        },
    )
    assert response.status_code == 403, response.text


def test_model_routing_rejects_writing_to_other_tenant():
    """租户 A 的 admin 不能通过 tenant_id 字段写入租户 B 的规则。"""
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login
    from db.session import get_db_session
    from repositories import tenant_repo

    # 先创建另一个租户
    gen = get_db_session()
    session = next(gen)
    try:
        other = tenant_repo.get_or_create_tenant(
            session, code="routing-other-tenant", name="OTHER"
        )
        other_id = other.id
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = seed_user_and_login(
        "routing-tenant-a@example.com", role="admin", tenant_code="routing-tenant-a"
    )
    seed_subscription(tenant_code="routing-tenant-a", plan_code="pro_manager")

    response = client.put(
        "/api/admin/model-routing",
        json={
            "tenant_id": other_id,
            "task_type": "batch_report",
            "preferred_model": "qwen-plus",
            "prompt_version": "v1",
            "is_active": True,
        },
    )
    assert response.status_code == 403, response.text


def test_model_routing_list_does_not_leak_other_tenant_rules():
    """租户 A 的 admin 看不到租户 B 的 tenant-scope 规则。"""
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login
    from db.session import get_db_session
    from repositories import model_routing_repo, tenant_repo

    gen = get_db_session()
    session = next(gen)
    try:
        other = tenant_repo.get_or_create_tenant(
            session, code="routing-leak-other", name="OTHER"
        )
        model_routing_repo.upsert_rule(
            session,
            scope="tenant",
            tenant_id=other.id,
            task_type="batch_report",
            preferred_model="should-not-be-visible",
            fallback_model=None,
            allow_batch=False,
            allow_search=False,
            allow_high_cost_mode=False,
            prompt_version="v1",
            is_active=True,
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = seed_user_and_login(
        "routing-leak-a@example.com", role="admin", tenant_code="routing-leak-a"
    )
    seed_subscription(tenant_code="routing-leak-a", plan_code="pro_manager")

    response = client.get("/api/admin/model-routing")
    assert response.status_code == 200, response.text
    for rule in response.json():
        assert rule["preferred_model"] != "should-not-be-visible"
