def test_admin_can_list_deployment_profiles():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login("deployment-admin@example.com", role="admin")
    tenant_id = seed_subscription(tenant_code="deployment-enabled", plan_code="pro_manager")

    enabled = client.put(
        f"/api/admin/feature-flags/tenants/{tenant_id}",
        json={"features": {"deployment.private_config": True}},
    )
    assert enabled.status_code == 200, enabled.text

    response = client.get("/api/admin/settings/deployment-profiles")

    expected_row_keys = {
        "tenant_id",
        "tenant_code",
        "tenant_name",
        "plan_code",
        "plan_name",
        "private_config_enabled",
        "private_config_source",
    }
    assert response.status_code == 200, response.text
    body = response.json()
    assert any(row["tenant_id"] == tenant_id for row in body)
    assert expected_row_keys.issubset(body[0].keys())


def test_admin_can_upsert_profile_for_enabled_tenant():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login("deployment-upsert@example.com", role="admin")
    tenant_id = seed_subscription(tenant_code="deployment-upsert", plan_code="pro_manager")

    enabled = client.put(
        f"/api/admin/feature-flags/tenants/{tenant_id}",
        json={"features": {"deployment.private_config": True}},
    )
    assert enabled.status_code == 200, enabled.text

    response = client.put(
        f"/api/admin/settings/deployment-profiles/{tenant_id}",
        json={
            "deployment_mode": "private_vpc",
            "delivery_status": "provisioning",
            "access_domain": "deployment.example.com",
            "sso_enabled": True,
            "sso_provider": "feishu",
            "sso_login_url": "https://sso.example.com/login",
            "storage_mode": "customer_s3",
            "backup_level": "enhanced",
            "environment_notes": "customer controlled infra",
            "handover_notes": "handover packet prepared",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == tenant_id
    assert body["deployment_mode"] == "private_vpc"
    assert body["delivery_status"] == "provisioning"


def test_upsert_rejects_tenant_without_private_config():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login("deployment-reject@example.com", role="admin")
    tenant_id = seed_subscription(tenant_code="deployment-standard", plan_code="standard")

    response = client.put(
        f"/api/admin/settings/deployment-profiles/{tenant_id}",
        json={"deployment_mode": "private_vpc"},
    )

    expected_detail_keys = {
        "feature_key",
        "tenant_id",
        "source",
    }
    assert response.status_code == 403, response.text
    body = response.json()
    assert body["error"]["code"] == "FEATURE_NOT_ENABLED"
    assert body["error"]["details"]["feature_key"] == "deployment.private_config"
    assert expected_detail_keys.issubset(body["error"]["details"].keys())


def test_manager_can_read_but_cannot_write_deployment_profiles():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "deployment-manager@example.com",
        role="manager",
        tenant_code="deployment-manager",
    )
    tenant_id = seed_subscription(tenant_code="deployment-manager", plan_code="pro_manager")

    response = client.get("/api/admin/settings/deployment-profiles")
    assert response.status_code == 200, response.text

    denied = client.put(
        f"/api/admin/settings/deployment-profiles/{tenant_id}",
        json={"deployment_mode": "private_vpc"},
    )
    assert denied.status_code == 403, denied.text
