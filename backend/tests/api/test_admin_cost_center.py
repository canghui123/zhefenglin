def test_admin_cost_center_returns_overview_and_tenant_breakdown():
    from db.session import get_db_session
    from services.cost_metering_service import record_usage

    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login("cost-admin@example.com", role="admin")
    tenant_id = seed_subscription(tenant_code="cost-tenant", plan_code="pro_manager")

    gen = get_db_session()
    session = next(gen)
    try:
        record_usage(
            session,
            tenant_id=tenant_id,
            user_id=None,
            module="asset-pricing",
            action="valuation",
            resource_type="vin_call",
            quantity=2,
            unit_cost_internal=1.5,
            unit_price_external=3.0,
            extra_snapshot_metrics={"estimated_revenue": 6.0},
        )
        record_usage(
            session,
            tenant_id=tenant_id,
            user_id=None,
            module="asset-pricing",
            action="llm_completion",
            resource_type="ai_report",
            quantity=1,
            unit_cost_internal=0.8,
            unit_price_external=0,
            extra_snapshot_metrics={
                "llm_input_tokens": 1500,
                "llm_output_tokens": 500,
                "llm_cost": 0.8,
            },
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    overview = client.get("/api/admin/cost-center/overview")
    assert overview.status_code == 200, overview.text
    overview_json = overview.json()
    assert overview_json["totals"]["vin_calls"] >= 2
    assert overview_json["totals"]["llm_input_tokens"] >= 1500
    assert overview_json["totals"]["total_cost"] >= 3.8

    tenants = client.get("/api/admin/cost-center/tenants")
    assert tenants.status_code == 200, tenants.text
    tenant_rows = tenants.json()
    assert any(row["tenant_id"] == tenant_id for row in tenant_rows)

    exported = client.get("/api/admin/cost-center/export")
    assert exported.status_code == 200, exported.text
    assert "tenant_id,tenant_code" in exported.text
