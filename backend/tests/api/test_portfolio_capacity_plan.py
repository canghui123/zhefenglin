def test_capacity_plan_uses_real_portfolio_segments_and_respects_limits():
    from db.models.portfolio import AssetSegment
    from db.models.portfolio_capacity import PortfolioCapacitySetting
    from db.session import get_db_session
    from repositories import portfolio_repo, tenant_repo
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
    settings_response = client.get("/api/admin/settings/capacity")
    assert settings_response.status_code == 200, settings_response.text
    assert settings_response.json()["monthly_auction_capacity"] == 7

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "capacity")
        assert tenant is not None
        snapshot = portfolio_repo.create_snapshot(
            session,
            tenant_id=tenant.id,
            org_id="capacity",
            snapshot_date="2026-05-21",
        )
        segment = AssetSegment(
            tenant_id=tenant.id,
            org_id="capacity",
            name="M4(91-120天) | 已入库",
            overdue_bucket="M4(91-120天)",
            recovered_status="已入库",
            inventory_bucket="30天内",
        )
        session.add(segment)
        session.flush()
        portfolio_repo.save_segment_metric(
            session,
            snapshot_id=snapshot.id,
            segment_id=segment.id,
            asset_count=12,
            total_ead=1_200_000,
            avg_vehicle_value=95_000,
            avg_lgd=0.42,
            avg_recovery_days=95,
            expected_loss_amount=504_000,
            expected_loss_rate=0.42,
            expected_cash_30d=120_000,
            expected_cash_90d=520_000,
            expected_cash_180d=760_000,
            recommended_strategy="retail_auction",
        )
        session.commit()
        rows = session.query(PortfolioCapacitySetting).all()
        assert len(rows) == 1
        assert rows[0].monthly_auction_capacity == 7
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    plan_response = client.get("/api/portfolio/capacity-plan")
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()

    assert plan["data_source"] == "real_portfolio"
    assert plan["snapshot_id"]
    assert plan["snapshot_date"] == "2026-05-21"
    assert plan["segment_count"] == 1
    assert plan["asset_count"] == 12
    assert plan["generated_at"]
    assert plan["empty_reason"] is None
    assert plan["resource_usage"]["auction_units"] <= 7
    assert plan["resource_usage"]["collection_accounts"] <= 8
    assert plan["resource_usage"]["legal_team_cases"] <= 6
    assert plan["next_month_deferred_pool"]
    assert "本月建议优先处理" in plan["summary"]


def test_capacity_plan_returns_empty_state_without_real_portfolio_data():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login("capacity-empty@example.com", role="operator", tenant_code="capacity-empty")

    plan_response = client.get("/api/portfolio/capacity-plan")
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()

    assert plan["data_source"] == "empty"
    assert plan["segment_count"] == 0
    assert plan["asset_count"] == 0
    assert plan["current_month_execution_plan"] == []
    assert plan["next_month_deferred_pool"] == []
    assert plan["paused_pool"] == []
    assert "暂无真实组合数据" in plan["empty_reason"]
    assert "暂无真实组合数据" in plan["summary"]
