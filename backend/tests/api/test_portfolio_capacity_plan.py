def test_admin_can_update_capacity_and_plan_respects_limits():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login("capacity-admin@example.com", role="admin", tenant_code="capacity")
    response = client.put(
        "/api/admin/settings/capacity",
        json={
            "monthly_towing_capacity": 5,
            "monthly_litigation_capacity": 6,
            "monthly_auction_capacity": 7,
            "monthly_collection_capacity": 8,
            "inventory_yard_capacity": 7,
            "monthly_disposal_budget": 600000,
            "legal_team_capacity": 6,
            "external_vendor_capacity": 7,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["monthly_auction_capacity"] == 7

    plan_response = client.get("/api/portfolio/capacity-plan")
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()

    assert plan["resource_usage"]["auction_units"] <= 7
    assert plan["resource_usage"]["collection_accounts"] <= 8
    assert plan["resource_usage"]["legal_team_cases"] <= 6
    assert plan["next_month_deferred_pool"]
    assert "本月建议优先处理" in plan["summary"]
