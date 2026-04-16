def test_admin_can_manage_plans_and_subscriptions():
    from sqlalchemy import select

    from db.models.plan import Plan
    from db.session import get_db_session

    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login("commercial-admin@example.com", role="admin")
    tenant_id = seed_subscription(tenant_code="tenant-b", plan_code="standard")

    plans = client.get("/api/admin/settings/plans")
    assert plans.status_code == 200, plans.text
    assert any(plan["code"] == "standard" for plan in plans.json())

    create_plan = client.post(
        "/api/admin/settings/plans",
        json={
            "code": "manager_plus",
            "name": "Manager Plus",
            "billing_cycle_supported": "monthly,yearly",
            "monthly_price": 8999,
            "yearly_price": 89990,
            "setup_fee": 3000,
            "private_deploy_fee": 0,
            "seat_limit": 12,
            "included_vin_calls": 1200,
            "included_condition_pricing_points": 30,
            "included_ai_reports": 260,
            "included_asset_packages": 80,
            "included_sandbox_runs": 220,
            "overage_vin_unit_price": 1.8,
            "overage_condition_pricing_unit_price": 40,
            "feature_flags": {"dashboard.advanced": True},
            "is_active": True,
        },
    )
    assert create_plan.status_code == 200, create_plan.text
    created_plan = create_plan.json()
    assert created_plan["code"] == "manager_plus"

    update_plan = client.put(
        f"/api/admin/settings/plans/{created_plan['id']}",
        json={"monthly_price": 9999, "seat_limit": 15},
    )
    assert update_plan.status_code == 200, update_plan.text
    assert update_plan.json()["monthly_price"] == 9999
    assert update_plan.json()["seat_limit"] == 15

    update_subscription = client.put(
        f"/api/admin/settings/subscriptions/{tenant_id}",
        json={
            "plan_code": "manager_plus",
            "monthly_budget_limit": 12000,
            "alert_threshold_percent": 75,
        },
    )
    assert update_subscription.status_code == 200, update_subscription.text
    assert update_subscription.json()["plan_code"] == "manager_plus"
    assert update_subscription.json()["monthly_budget_limit"] == 12000

    gen = get_db_session()
    session = next(gen)
    try:
        saved_plan = session.scalars(
            select(Plan).where(Plan.code == "manager_plus").limit(1)
        ).first()
        assert saved_plan.monthly_price == 9999
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_manager_cannot_mutate_commercial_settings():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login("commercial-manager@example.com", role="manager")
    response = client.post(
        "/api/admin/settings/plans",
        json={"code": "forbidden", "name": "Forbidden"},
    )
    assert response.status_code == 403, response.text
