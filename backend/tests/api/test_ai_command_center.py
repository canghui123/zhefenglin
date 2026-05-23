from __future__ import annotations

import json


def _assert_agent_output_schema(output: dict):
    assert output["summary"]
    assert isinstance(output["key_findings"], list)
    assert isinstance(output["recommended_actions"], list)
    assert isinstance(output["risk_warnings"], list)
    assert 0 <= output["confidence_score"] <= 1
    assert isinstance(output["evidence"], list)
    assert output["requires_human_review"] is True
    assert output["agent_status"] in {"rules_based", "mock", "fallback", "llm_assisted"}


def _seed_asset_package(tenant_code: str, *, with_result: bool = False) -> int:
    from db.models.asset_package import Asset
    from db.session import get_db_session
    from models.asset import PackageCalculationResult, PackageSummary
    from repositories import asset_package_repo, tenant_repo

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, tenant_code)
        assert tenant is not None
        package = asset_package_repo.create_package(
            session,
            tenant_id=tenant.id,
            name=f"{tenant_code}-package",
            upload_filename="agent-test.xlsx",
            total_assets=3,
        )
        session.add_all(
            [
                Asset(
                    package_id=package.id,
                    row_number=1,
                    car_description="2022 丰田 凯美瑞",
                    loan_principal=120000,
                    che300_valuation=98000,
                    gps_online=1,
                    insurance_lapsed=0,
                    ownership_transferred=1,
                ),
                Asset(
                    package_id=package.id,
                    row_number=2,
                    car_description="2020 比亚迪 汉",
                    loan_principal=150000,
                    che300_valuation=None,
                    gps_online=0,
                    insurance_lapsed=1,
                    ownership_transferred=0,
                ),
                Asset(
                    package_id=package.id,
                    row_number=3,
                    car_description="2019 大众 迈腾",
                    loan_principal=90000,
                    che300_valuation=72000,
                    gps_online=1,
                    insurance_lapsed=0,
                    ownership_transferred=1,
                ),
            ]
        )
        if with_result:
            result = PackageCalculationResult(
                package_id=package.id,
                summary=PackageSummary(
                    total_assets=3,
                    total_principal=360000,
                    total_vehicle_valuation=170000,
                    valuation_coverage_rate=0.67,
                    recommended_transfer_price_low=180000,
                    recommended_transfer_price_mid=210000,
                    recommended_transfer_price_high=240000,
                    tradeability_score=68,
                    tradeability_level="C",
                    risk_alerts=["估值覆盖率不足，需补齐关键车辆估值"],
                ),
                assets=[],
            )
            package.results_json = result.model_dump_json()
        session.commit()
        return package.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _seed_portfolio_snapshot(tenant_code: str) -> int:
    from repositories import portfolio_repo, tenant_repo
    from db.session import get_db_session

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, tenant_code)
        assert tenant is not None
        snapshot = portfolio_repo.create_snapshot(
            session,
            org_id=tenant_code,
            snapshot_date="2026-05-22",
            tenant_id=tenant.id,
        )
        auction_segment = portfolio_repo.AssetSegment(
            tenant_id=tenant.id,
            org_id=tenant_code,
            name="M3 已入库高价值车辆",
            overdue_bucket="M3",
            recovered_status="已入库",
            inventory_bucket="30-60天",
        )
        legal_segment = portfolio_repo.AssetSegment(
            tenant_id=tenant.id,
            org_id=tenant_code,
            name="M4+ 未收回高损失车辆",
            overdue_bucket="M4+",
            recovered_status="未收回",
            inventory_bucket=None,
        )
        session.add_all([auction_segment, legal_segment])
        session.flush()
        portfolio_repo.save_segment_metric(
            session,
            snapshot_id=snapshot.id,
            segment_id=auction_segment.id,
            asset_count=12,
            total_ead=1_200_000,
            avg_vehicle_value=80_000,
            avg_lgd=0.45,
            avg_recovery_days=45,
            expected_loss_amount=360_000,
            expected_loss_rate=0.3,
            expected_cash_30d=160_000,
            expected_cash_90d=420_000,
            expected_cash_180d=620_000,
            recommended_strategy="retail_auction",
        )
        portfolio_repo.save_segment_metric(
            session,
            snapshot_id=snapshot.id,
            segment_id=legal_segment.id,
            asset_count=8,
            total_ead=900_000,
            avg_vehicle_value=40_000,
            avg_lgd=0.62,
            avg_recovery_days=120,
            expected_loss_amount=500_000,
            expected_loss_rate=0.55,
            expected_cash_30d=40_000,
            expected_cash_90d=160_000,
            expected_cash_180d=300_000,
            recommended_strategy="litigation",
        )
        session.commit()
        return snapshot.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_agent_run_creation_output_format_and_human_review():
    from db.session import get_db_session
    from repositories import agent_repo
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "ai-agent-operator@example.com",
        role="operator",
        tenant_code="ai-agent",
    )
    package_id = _seed_asset_package("ai-agent")

    response = client.post(
        "/api/ai-command-center/runs",
        json={
            "agent_type": "asset_package_diagnosis_agent",
            "asset_package_id": package_id,
            "question": "分析这个资产包适不适合整体出让",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_type"] == "asset_package_diagnosis_agent"
    assert body["status"] == "succeeded"
    assert body["requires_human_review"] is True
    output = body["output"]
    assert output["summary"]
    assert output["key_findings"]
    assert output["recommended_actions"]
    assert output["risk_warnings"]
    assert 0 <= output["confidence_score"] <= 1
    assert output["evidence"]
    assert output["requires_human_review"] is True
    assert output["agent_status"] == "rules_based"

    gen = get_db_session()
    session = next(gen)
    try:
        run = agent_repo.get_run(session, body["id"], tenant_id=body["tenant_id"])
        assert run is not None
        assert run.tenant_id == body["tenant_id"]
        assert run.requires_human_review is True
        assert json.loads(run.output_json)["requires_human_review"] is True
        assert agent_repo.list_recommendations(session, tenant_id=body["tenant_id"])
        audit_logs = agent_repo.list_decision_audit_logs(session, tenant_id=body["tenant_id"])
        assert audit_logs
        assert audit_logs[0].decision_type == "asset_package_diagnosis_agent"
        assert audit_logs[0].decision_type
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_agent_runs_are_tenant_scoped():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    owner = seed_user_and_login(
        "ai-tenant-owner@example.com",
        role="operator",
        tenant_code="ai-tenant-owner",
    )
    package_id = _seed_asset_package("ai-tenant-owner")
    created = owner.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "asset_package_diagnosis_agent", "asset_package_id": package_id},
    )
    assert created.status_code == 200, created.text

    foreign = seed_user_and_login(
        "ai-tenant-foreign@example.com",
        role="operator",
        tenant_code="ai-tenant-foreign",
    )
    leaked = foreign.get(f"/api/ai-command-center/runs/{created.json()['id']}")
    assert leaked.status_code == 404, leaked.text


def test_viewer_only_sees_summary_and_cannot_initiate_agent():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    operator = seed_user_and_login(
        "ai-viewer-owner@example.com",
        role="operator",
        tenant_code="ai-viewer",
    )
    package_id = _seed_asset_package("ai-viewer")
    created = operator.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "asset_package_diagnosis_agent", "asset_package_id": package_id},
    )
    assert created.status_code == 200, created.text

    viewer = seed_user_and_login(
        "ai-viewer@example.com",
        role="viewer",
        tenant_code="ai-viewer",
    )
    forbidden = viewer.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "asset_package_diagnosis_agent", "asset_package_id": package_id},
    )
    assert forbidden.status_code == 403, forbidden.text

    detail = viewer.get(f"/api/ai-command-center/runs/{created.json()['id']}")
    assert detail.status_code == 200, detail.text
    output = detail.json()["output"]
    assert output["summary"]
    assert output["key_findings"] == []
    assert output["recommended_actions"] == []
    assert output["evidence"] == []


def test_agent_type_min_role_is_enforced():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    operator = seed_user_and_login(
        "ai-cost-operator@example.com",
        role="operator",
        tenant_code="ai-cost-role",
    )
    denied = operator.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "cost_control_agent", "question": "检查本月成本风险"},
    )
    assert denied.status_code == 403, denied.text

    manager = seed_user_and_login(
        "ai-pricing-manager@example.com",
        role="manager",
        tenant_code="ai-pricing-role",
    )
    package_id = _seed_asset_package("ai-pricing-role", with_result=True)
    allowed = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "pricing_strategy_agent", "asset_package_id": package_id},
    )
    assert allowed.status_code == 200, allowed.text


def test_admin_can_view_decision_audit_logs_operator_cannot():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    operator = seed_user_and_login(
        "ai-audit-operator@example.com",
        role="operator",
        tenant_code="ai-audit",
    )
    package_id = _seed_asset_package("ai-audit")
    created = operator.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "asset_package_diagnosis_agent", "asset_package_id": package_id},
    )
    assert created.status_code == 200, created.text

    denied = operator.get("/api/ai-command-center/decision-audit-logs")
    assert denied.status_code == 403, denied.text

    admin = seed_user_and_login(
        "ai-audit-admin@example.com",
        role="admin",
        tenant_code="ai-audit",
    )
    logs = admin.get("/api/ai-command-center/decision-audit-logs")
    assert logs.status_code == 200, logs.text
    assert logs.json()
    assert logs.json()[0]["decision_type"] == "asset_package_diagnosis_agent"
    assert logs.json()[0]["action"] == "completed"
    assert logs.json()[0]["requires_human_review"] is True


def test_unsupported_agent_type_returns_business_error():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "ai-unsupported@example.com",
        role="operator",
        tenant_code="ai-unsupported",
    )
    response = client.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "unknown_agent", "question": "跑一个不存在的 Agent"},
    )

    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == "unsupported_agent_type"
    assert error["message"] == "不支持的 Agent 类型"
    assert "asset_package_diagnosis_agent" in error["details"]["supported_agent_types"]


def test_semi_automated_agents_return_rule_outputs_and_enforce_roles():
    from db.session import get_db_session
    from repositories import agent_repo, tenant_repo
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    manager = seed_user_and_login(
        "ai-semi-manager@example.com",
        role="manager",
        tenant_code="ai-semi",
    )
    admin = seed_user_and_login(
        "ai-semi-admin@example.com",
        role="admin",
        tenant_code="ai-semi",
    )
    operator = seed_user_and_login(
        "ai-semi-operator@example.com",
        role="operator",
        tenant_code="ai-semi",
    )
    seed_subscription(tenant_code="ai-semi", plan_code="standard", monthly_budget_limit=5000)
    package_id = _seed_asset_package("ai-semi", with_result=True)
    _seed_portfolio_snapshot("ai-semi")

    for agent_type in [
        "operation_planning_agent",
        "task_generation_agent",
        "report_generation_agent",
    ]:
        denied = operator.post(
            "/api/ai-command-center/runs",
            json={"agent_type": agent_type, "question": "运行预留 Agent"},
        )
        assert denied.status_code == 403, denied.text
        assert "无权运行" in denied.json()["error"]["message"]

        response = manager.post(
            "/api/ai-command-center/runs",
            json={"agent_type": agent_type, "asset_package_id": package_id, "question": "运行半自动 Agent"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["agent_type"] == agent_type
        assert body["status"] == "succeeded"
        assert body["requires_human_review"] is True
        _assert_agent_output_schema(body["output"])
        status_evidence = next(item for item in body["output"]["evidence"] if item["label"] == "status")
        assert status_evidence["value"] == "rules_based"
        assert status_evidence["value"] != "fully_implemented"

        if agent_type == "operation_planning_agent":
            plan = next(item for item in body["output"]["evidence"] if item["label"] == "operation_plan")
            assert "weekly_focus" in plan["value"]
            assert "high_priority_asset_pool" in plan["value"]
            assert "auction_pool" in plan["value"]
            assert "data_completion_pool" in plan["value"]
        if agent_type == "task_generation_agent":
            drafts = next(item for item in body["output"]["evidence"] if item["label"] == "task_drafts")
            first = drafts["value"][0]
            assert first["status"] == "draft"
            assert first["requires_human_review"] is True
            assert first["task_type"] in {
                "data_completion",
                "valuation_review",
                "auction_preparation",
                "legal_material_review",
                "collection_follow_up",
                "buyer_offer_review",
                "report_review",
            }
            assert first["suggested_owner_role"]
            assert first["required_documents"]
        if agent_type == "report_generation_agent":
            draft = next(item for item in body["output"]["evidence"] if item["label"] == "report_draft")
            assert draft["value"]["distribution"] == "draft_only"
            assert draft["value"]["requires_human_review"] is True

    denied_cost = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "cost_control_agent", "question": "运行成本控制 Agent"},
    )
    assert denied_cost.status_code == 403, denied_cost.text
    assert "无权运行" in denied_cost.json()["error"]["message"]

    cost_response = admin.post(
        "/api/ai-command-center/runs",
        json={
            "agent_type": "cost_control_agent",
            "asset_package_id": package_id,
            "question": "运行成本控制 Agent",
            "expected_vin_calls": 5,
            "expected_condition_pricing_calls": 2,
            "expected_ai_reports": 1,
            "single_task_budget": 100,
        },
    )
    assert cost_response.status_code == 200, cost_response.text
    cost_body = cost_response.json()
    assert cost_body["agent_type"] == "cost_control_agent"
    _assert_agent_output_schema(cost_body["output"])
    status_evidence = next(item for item in cost_body["output"]["evidence"] if item["label"] == "status")
    assert status_evidence["value"] == "rules_based"
    cost = next(item for item in cost_body["output"]["evidence"] if item["label"] == "cost_control")
    assert cost["value"]["estimated_cost"] > 0
    assert "quota_remaining" in cost["value"]
    assert "approval_required" in cost["value"]

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "ai-semi")
        assert tenant is not None
        tasks = agent_repo.list_pending_tasks(session, tenant_id=tenant.id, limit=20)
        assert tasks
        payload = agent_repo.load_json(tasks[0].payload_json)
        assert payload["status"] == "draft"
        assert payload["requires_human_review"] is True
        assert payload["suggested_owner_role"]
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_llm_unavailable_uses_fallback_evidence(monkeypatch):
    from config import settings
    from tests.api.admin_commercial_helpers import seed_user_and_login

    monkeypatch.setattr(settings, "deepseek_api_key", "")
    client = seed_user_and_login(
        "ai-fallback@example.com",
        role="operator",
        tenant_code="ai-fallback",
    )
    package_id = _seed_asset_package("ai-fallback")
    response = client.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "valuation_analysis_agent", "asset_package_id": package_id},
    )
    assert response.status_code == 200, response.text
    evidence = response.json()["output"]["evidence"]
    fallback = next(item for item in evidence if item["label"] == "llm_fallback")
    assert fallback["value"] is True


def test_buyer_offer_agent_never_auto_accepts_offer():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "ai-buyer-offer@example.com",
        role="operator",
        tenant_code="ai-buyer-offer",
    )
    package_id = _seed_asset_package("ai-buyer-offer", with_result=True)
    response = client.post(
        "/api/ai-command-center/runs",
        json={
            "question": "买方报价是否合理",
            "asset_package_id": package_id,
            "buyer_offer_price": 160000,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_type"] == "buyer_offer_analysis_agent"
    assert body["requires_human_review"] is True
    assert body["output"]["requires_human_review"] is True
    assert any("不得自动接受" in item for item in body["output"]["risk_warnings"])
