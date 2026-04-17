def test_admin_can_list_and_update_feature_flags():
    from sqlalchemy import select

    from db.models.audit_log import AuditLog
    from db.models.plan import Plan
    from db.models.subscription import FeatureEntitlement
    from db.session import get_db_session
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login("feature-admin@example.com", role="admin")
    tenant_id = seed_subscription(tenant_code="feature-tenant", plan_code="standard")

    listed = client.get("/api/admin/feature-flags")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert any(item["key"] == "deployment.private_config" for item in payload["catalog"])
    standard_row = next(row for row in payload["plans"] if row["plan_code"] == "standard")
    assert standard_row["features"]["deployment.private_config"] is False

    update_plan = client.put(
        "/api/admin/feature-flags/plans/standard",
        json={"features": {"deployment.private_config": True}},
    )
    assert update_plan.status_code == 200, update_plan.text
    updated_plan = update_plan.json()
    assert updated_plan["plan_code"] == "standard"
    assert updated_plan["features"]["deployment.private_config"] is True

    update_tenant = client.put(
        f"/api/admin/feature-flags/tenants/{tenant_id}",
        json={"features": {"deployment.private_config": False}},
    )
    assert update_tenant.status_code == 200, update_tenant.text
    updated_tenant = update_tenant.json()
    assert updated_tenant["tenant_id"] == tenant_id
    assert updated_tenant["overrides"]["deployment.private_config"] is False
    assert updated_tenant["effective_features"]["deployment.private_config"] is False

    clear_override = client.put(
        f"/api/admin/feature-flags/tenants/{tenant_id}",
        json={"features": {"deployment.private_config": None}},
    )
    assert clear_override.status_code == 200, clear_override.text
    cleared_tenant = clear_override.json()
    assert cleared_tenant["overrides"]["deployment.private_config"] is None
    assert cleared_tenant["effective_features"]["deployment.private_config"] is True

    gen = get_db_session()
    session = next(gen)
    try:
        standard_plan = session.scalars(
            select(Plan).where(Plan.code == "standard").limit(1)
        ).first()
        assert standard_plan is not None
        assert '"deployment.private_config": true' in (standard_plan.feature_flags_json or "").lower()

        tenant_override = session.scalars(
            select(FeatureEntitlement)
            .where(FeatureEntitlement.scope == "tenant")
            .where(FeatureEntitlement.tenant_id == tenant_id)
            .where(FeatureEntitlement.feature_key == "deployment.private_config")
            .limit(1)
        ).first()
        assert tenant_override is None

        actions = {
            row.action
            for row in session.scalars(
                select(AuditLog)
                .where(AuditLog.action.in_(("feature_flags_plan_update", "feature_flags_tenant_update")))
                .order_by(AuditLog.id)
            ).all()
        }
        assert actions == {"feature_flags_plan_update", "feature_flags_tenant_update"}
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_manager_can_view_but_cannot_mutate_feature_flags():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "feature-manager@example.com",
        role="manager",
        tenant_code="feature-manager",
    )
    tenant_id = seed_subscription(tenant_code="feature-manager", plan_code="pro_manager")

    listed = client.get("/api/admin/feature-flags")
    assert listed.status_code == 200, listed.text

    plan_update = client.put(
        "/api/admin/feature-flags/plans/pro_manager",
        json={"features": {"audit.export": False}},
    )
    assert plan_update.status_code == 403, plan_update.text

    tenant_update = client.put(
        f"/api/admin/feature-flags/tenants/{tenant_id}",
        json={"features": {"audit.export": None}},
    )
    assert tenant_update.status_code == 403, tenant_update.text
