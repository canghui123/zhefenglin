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

    upsert = client.put(
        "/api/admin/model-routing",
        json={
            "scope": "global",
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
