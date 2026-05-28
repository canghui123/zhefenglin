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
    assert logs.json()[0]["tenant_id"]
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
            assert "quick_auction_pool" in plan["value"]
            assert "auction_pool" in plan["value"]
            assert "legal_advancement_pool" in plan["value"]
            assert "data_completion_pool" in plan["value"]
            assert "valuation_review_pool" in plan["value"]
            assert "debt_transfer_pool" in plan["value"]
            assert "observe_pool" in plan["value"]
            assert "capacity_budget_constraints" in plan["value"]
            assert "missing_data" in plan["value"]
            assert "data_quality_notes" in plan["value"]
            assert plan["value"]["requires_human_review"] is True
            assert plan["value"]["agent_status"] == "rules_based"
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
                "cost_approval",
            }
            assert first["suggested_owner_role"]
            assert first["required_documents"]
            assert first["evidence"]
            assert 0 <= first["confidence_score"] <= 1
            assert all(draft["status"] == "draft" for draft in drafts["value"])
            assert all(draft["requires_human_review"] is True for draft in drafts["value"])
        if agent_type == "report_generation_agent":
            draft = next(item for item in body["output"]["evidence"] if item["label"] == "report_draft")
            assert draft["value"]["status"] == "draft"
            assert draft["value"]["distribution"] == "draft_only"
            assert draft["value"]["requires_human_review"] is True
            assert draft["value"]["confidence_score"] == body["output"]["confidence_score"]
            assert draft["value"]["review_checklist"]
            assert "missing_data" in draft["value"]
            assert "data_quality_notes" in draft["value"]
            assert "自动外发" in draft["value"]["forbidden_actions"]

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

    cost_task_response = manager.post(
        "/api/ai-command-center/runs",
        json={
            "agent_type": "task_generation_agent",
            "asset_package_id": package_id,
            "expected_condition_pricing_calls": 2,
            "single_task_budget": 100,
            "question": "生成成本审批任务草稿",
        },
    )
    assert cost_task_response.status_code == 200, cost_task_response.text
    cost_task_drafts = next(
        item for item in cost_task_response.json()["output"]["evidence"] if item["label"] == "task_drafts"
    )
    assert any(draft["task_type"] == "cost_approval" for draft in cost_task_drafts["value"])

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


def test_operation_planning_agent_limited_data_and_tenant_isolation():
    from db.session import get_db_session
    from repositories import agent_repo, tenant_repo
    from tests.api.admin_commercial_helpers import seed_user_and_login

    manager = seed_user_and_login(
        "ai-operation-limited-manager@example.com",
        role="manager",
        tenant_code="ai-operation-limited",
    )
    operator = seed_user_and_login(
        "ai-operation-limited-operator@example.com",
        role="operator",
        tenant_code="ai-operation-limited",
    )
    foreign_manager = seed_user_and_login(
        "ai-operation-limited-foreign@example.com",
        role="manager",
        tenant_code="ai-operation-limited-foreign",
    )

    denied = operator.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "operation_planning_agent", "question": "生成本周作战计划"},
    )
    assert denied.status_code == 403, denied.text

    created = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "operation_planning_agent", "question": "生成本周作战计划"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    output = body["output"]
    _assert_agent_output_schema(output)
    assert output["agent_status"] == "rules_based"
    assert output["confidence_score"] == 0.35
    plan = next(item for item in output["evidence"] if item["label"] == "operation_plan")
    assert plan["value"]["missing_data"]
    assert "asset_package" in plan["value"]["missing_data"]
    assert "portfolio_segments" in plan["value"]["missing_data"]
    assert plan["value"]["limited_data_reason"]
    assert plan["value"]["fallback_reason"] == "暂无真实组合数据和资产包数据"
    assert plan["value"]["weekly_focus"] == ["先补齐资产包、组合分层和定价结果，再形成正式作战计划"]

    leaked = foreign_manager.get(f"/api/ai-command-center/runs/{body['id']}")
    assert leaked.status_code == 404, leaked.text

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "ai-operation-limited")
        assert tenant is not None
        recommendations = agent_repo.list_recommendations(session, tenant_id=tenant.id, limit=5)
        assert any(row.recommendation_type == "operation_planning_agent" for row in recommendations)
        logs = agent_repo.list_decision_audit_logs(session, tenant_id=tenant.id, limit=5)
        assert any(
            row.decision_type == "operation_planning_agent" and row.action == "completed"
            for row in logs
        )
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_task_generation_draft_confirmation_creates_pending_work_order_and_audit():
    from db.session import get_db_session
    from repositories import agent_repo, tenant_repo, work_order_repo
    from tests.api.admin_commercial_helpers import seed_user_and_login

    manager = seed_user_and_login(
        "ai-task-confirm-manager@example.com",
        role="manager",
        tenant_code="ai-task-confirm",
    )
    admin = seed_user_and_login(
        "ai-task-confirm-admin@example.com",
        role="admin",
        tenant_code="ai-task-confirm",
    )
    operator = seed_user_and_login(
        "ai-task-confirm-operator@example.com",
        role="operator",
        tenant_code="ai-task-confirm",
    )
    foreign_manager = seed_user_and_login(
        "ai-task-confirm-foreign@example.com",
        role="manager",
        tenant_code="ai-task-confirm-foreign",
    )
    package_id = _seed_asset_package("ai-task-confirm", with_result=True)

    created = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "task_generation_agent", "asset_package_id": package_id},
    )
    assert created.status_code == 200, created.text

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "ai-task-confirm")
        assert tenant is not None
        drafts = agent_repo.list_pending_tasks(session, tenant_id=tenant.id, limit=20)
        assert drafts
        high_draft = next(draft for draft in drafts if draft.priority == "high")
        normal_draft = next(draft for draft in drafts if draft.priority != "high")
        high_draft_id = high_draft.id
        draft_id = normal_draft.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    denied = operator.post(
        f"/api/ai-command-center/tasks/{draft_id}/confirm",
        json={"reason": "operator 不应确认"},
    )
    assert denied.status_code == 403, denied.text

    high_denied = manager.post(
        f"/api/ai-command-center/tasks/{high_draft_id}/confirm",
        json={"reason": "manager 不应确认高风险任务"},
    )
    assert high_denied.status_code == 403, high_denied.text
    assert "高风险任务草稿需 admin 确认" in high_denied.json()["error"]["message"]

    leaked = foreign_manager.post(
        f"/api/ai-command-center/tasks/{draft_id}/confirm",
        json={"reason": "跨租户不应确认"},
    )
    assert leaked.status_code == 404, leaked.text

    confirmed = manager.post(
        f"/api/ai-command-center/tasks/{draft_id}/confirm",
        json={"reason": "经理确认进入正式任务池"},
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["status"] == "confirmed"
    assert body["requires_human_review"] is True
    assert body["payload"]["status"] == "confirmed"
    assert body["payload"]["work_order_id"]
    work_order_id = body["payload"]["work_order_id"]

    duplicate = manager.post(f"/api/ai-command-center/tasks/{draft_id}/confirm")
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "agent_task_already_decided"

    high_confirmed = admin.post(
        f"/api/ai-command-center/tasks/{high_draft_id}/confirm",
        json={"reason": "管理员确认高风险任务进入正式任务池"},
    )
    assert high_confirmed.status_code == 200, high_confirmed.text
    assert high_confirmed.json()["status"] == "confirmed"

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "ai-task-confirm")
        assert tenant is not None
        work_order = work_order_repo.get_work_order(session, work_order_id, tenant_id=tenant.id)
        assert work_order is not None
        assert work_order.status == "pending"
        assert work_order.source_type == "agent_task"
        assert work_order.source_id == str(draft_id)
        assert work_order.created_by is not None
        persisted = agent_repo.get_task(session, draft_id, tenant_id=tenant.id)
        assert persisted is not None
        assert persisted.status == "confirmed"
        logs = agent_repo.list_decision_audit_logs(session, tenant_id=tenant.id, limit=10)
        assert any(
            log.decision_type == "agent_task_confirmation" and log.action == "confirmed"
            for log in logs
        )
        assert len(
            [
                log
                for log in logs
                if log.decision_type == "agent_task_confirmation" and log.action == "confirmed"
            ]
        ) >= 2
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_operator_can_view_task_drafts_but_cannot_confirm():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    manager = seed_user_and_login(
        "ai-task-view-manager@example.com",
        role="manager",
        tenant_code="ai-task-view",
    )
    operator = seed_user_and_login(
        "ai-task-view-operator@example.com",
        role="operator",
        tenant_code="ai-task-view",
    )
    package_id = _seed_asset_package("ai-task-view", with_result=True)
    created = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "task_generation_agent", "asset_package_id": package_id},
    )
    assert created.status_code == 200, created.text

    overview = operator.get("/api/ai-command-center/overview")
    assert overview.status_code == 200, overview.text
    assert overview.json()["pending_tasks"]
    draft_id = overview.json()["pending_tasks"][0]["id"]

    denied = operator.post(
        f"/api/ai-command-center/tasks/{draft_id}/confirm",
        json={"reason": "operator 不能确认任务草稿"},
    )
    assert denied.status_code == 403, denied.text


def test_task_generation_draft_can_be_rejected_without_creating_work_order():
    from db.session import get_db_session
    from repositories import agent_repo, tenant_repo, work_order_repo
    from tests.api.admin_commercial_helpers import seed_user_and_login

    manager = seed_user_and_login(
        "ai-task-reject-manager@example.com",
        role="manager",
        tenant_code="ai-task-reject",
    )
    package_id = _seed_asset_package("ai-task-reject", with_result=True)
    created = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "task_generation_agent", "asset_package_id": package_id},
    )
    assert created.status_code == 200, created.text

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "ai-task-reject")
        assert tenant is not None
        draft = agent_repo.list_pending_tasks(session, tenant_id=tenant.id, limit=20)[0]
        draft_id = draft.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    rejected = manager.post(
        f"/api/ai-command-center/tasks/{draft_id}/reject",
        json={"reason": "资料不充分，暂不派发"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["payload"]["rejection_reason"] == "资料不充分，暂不派发"

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "ai-task-reject")
        assert tenant is not None
        persisted = agent_repo.get_task(session, draft_id, tenant_id=tenant.id)
        assert persisted is not None
        assert persisted.status == "rejected"
        assert work_order_repo.find_open_by_source(
            session,
            tenant_id=tenant.id,
            source_type="agent_task",
            source_id=str(draft_id),
            order_type=persisted.task_type,
        ) is None
        logs = agent_repo.list_decision_audit_logs(session, tenant_id=tenant.id, limit=10)
        assert any(
            log.decision_type == "agent_task_confirmation" and log.action == "rejected"
            for log in logs
        )
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_agent_rule_settings_are_admin_configurable_and_audited():
    from db.session import get_db_session
    from repositories import agent_repo, tenant_repo
    from tests.api.admin_commercial_helpers import seed_user_and_login

    manager = seed_user_and_login(
        "ai-rules-manager@example.com",
        role="manager",
        tenant_code="ai-rules",
    )
    defaults = manager.get("/api/ai-command-center/settings")
    assert defaults.status_code == 200, defaults.text
    assert defaults.json()["task_max_drafts"] == 8

    denied = manager.put(
        "/api/ai-command-center/settings",
        json={**defaults.json(), "task_max_drafts": 2},
    )
    assert denied.status_code == 403, denied.text

    admin = seed_user_and_login(
        "ai-rules-admin@example.com",
        role="admin",
        tenant_code="ai-rules",
    )
    payload = {
        "operation_high_priority_limit": 1,
        "operation_data_gap_min_count": 2,
        "task_max_drafts": 2,
        "task_urgent_deadline_days": 2,
        "task_normal_deadline_days": 9,
        "cost_budget_warning_percent": 0.6,
        "cost_condition_call_approval_threshold": 3,
        "cost_ai_report_merge_threshold": 3,
        "report_confidence_floor": 0.6,
        "report_max_sections": 2,
    }
    updated = admin.put("/api/ai-command-center/settings", json=payload)
    assert updated.status_code == 200, updated.text
    assert updated.json()["task_max_drafts"] == 2
    assert updated.json()["operation_high_priority_limit"] == 1
    assert updated.json()["agent_type"] == "global"
    assert updated.json()["scenario"] == "default"
    assert updated.json()["version"] == 1

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "ai-rules")
        assert tenant is not None
        settings = agent_repo.get_rule_settings(session, tenant_id=tenant.id)
        assert settings.task_max_drafts == 2
        logs = agent_repo.list_decision_audit_logs(session, tenant_id=tenant.id, limit=10)
        assert logs[0].decision_type == "agent_rule_settings"
        assert logs[0].action == "updated"
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_agent_rule_settings_drive_rule_based_agent_outputs():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    admin = seed_user_and_login(
        "ai-rules-output-admin@example.com",
        role="admin",
        tenant_code="ai-rules-output",
    )
    manager = seed_user_and_login(
        "ai-rules-output-manager@example.com",
        role="manager",
        tenant_code="ai-rules-output",
    )
    seed_subscription(tenant_code="ai-rules-output", plan_code="standard", monthly_budget_limit=5000)
    package_id = _seed_asset_package("ai-rules-output", with_result=True)
    _seed_portfolio_snapshot("ai-rules-output")

    settings_payload = {
        "operation_high_priority_limit": 1,
        "operation_data_gap_min_count": 1,
        "task_max_drafts": 2,
        "task_urgent_deadline_days": 2,
        "task_normal_deadline_days": 9,
        "cost_budget_warning_percent": 0.9,
        "cost_condition_call_approval_threshold": 3,
        "cost_ai_report_merge_threshold": 3,
        "report_confidence_floor": 0.6,
        "report_max_sections": 2,
    }
    assert admin.put("/api/ai-command-center/settings", json=settings_payload).status_code == 200

    operation = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "operation_planning_agent", "asset_package_id": package_id},
    )
    assert operation.status_code == 200, operation.text
    operation_plan = next(
        item for item in operation.json()["output"]["evidence"] if item["label"] == "operation_plan"
    )
    assert len(operation_plan["value"]["high_priority_asset_pool"]) <= 1
    thresholds = next(
        item for item in operation.json()["output"]["evidence"] if item["label"] == "rule_thresholds"
    )
    assert thresholds["value"]["operation_high_priority_limit"] == 1

    tasks = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "task_generation_agent", "asset_package_id": package_id},
    )
    assert tasks.status_code == 200, tasks.text
    drafts = next(item for item in tasks.json()["output"]["evidence"] if item["label"] == "task_drafts")
    assert len(drafts["value"]) <= 2
    assert drafts["value"][0]["deadline_suggestion"]

    cost = admin.post(
        "/api/ai-command-center/runs",
        json={
            "agent_type": "cost_control_agent",
            "asset_package_id": package_id,
            "expected_vin_calls": 0,
            "expected_condition_pricing_calls": 2,
            "expected_ai_reports": 2,
            "single_task_budget": 500,
        },
    )
    assert cost.status_code == 200, cost.text
    cost_payload = next(item for item in cost.json()["output"]["evidence"] if item["label"] == "cost_control")
    assert cost_payload["value"]["thresholds"]["cost_condition_call_approval_threshold"] == 3
    assert cost_payload["value"]["approval_required"] is False

    report = manager.post(
        "/api/ai-command-center/runs",
        json={
            "agent_type": "report_generation_agent",
            "asset_package_id": package_id,
            "report_type": "weekly_operation_report",
        },
    )
    assert report.status_code == 200, report.text
    report_draft = next(item for item in report.json()["output"]["evidence"] if item["label"] == "report_draft")
    assert len(report_draft["value"]["sections"]) == 2
    assert report_draft["value"]["status"] == "draft"
    assert report_draft["value"]["source_context"]["asset_package_id"] == package_id
    assert "review_checklist" in report_draft["value"]
    assert report.json()["output"]["confidence_score"] >= 0.6


def test_report_generation_agent_handles_limited_data_as_draft():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    manager = seed_user_and_login(
        "ai-report-limited-manager@example.com",
        role="manager",
        tenant_code="ai-report-limited",
    )

    response = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "report_generation_agent", "report_type": "buyer_offer_memo"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["output"]["requires_human_review"] is True
    assert body["output"]["agent_status"] == "rules_based"
    draft = next(item for item in body["output"]["evidence"] if item["label"] == "report_draft")
    assert draft["value"]["status"] == "draft"
    assert draft["value"]["distribution"] == "draft_only"
    assert {"asset_package", "pricing_result", "asset_details", "buyer_offer_price"}.issubset(
        set(draft["value"]["missing_data"])
    )
    assert "自动外发" in draft["value"]["forbidden_actions"]
    assert "报告草稿缺失数据" in body["output"]["risk_warnings"][1]


def test_agent_rule_profiles_are_agent_scenario_and_version_scoped():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    admin = seed_user_and_login(
        "ai-rule-profile-admin@example.com",
        role="admin",
        tenant_code="ai-rule-profile",
    )
    manager = seed_user_and_login(
        "ai-rule-profile-manager@example.com",
        role="manager",
        tenant_code="ai-rule-profile",
    )
    package_id = _seed_asset_package("ai-rule-profile", with_result=True)
    _seed_portfolio_snapshot("ai-rule-profile")

    payload = {
        "agent_type": "operation_planning_agent",
        "scenario": "stress_week",
        "operation_high_priority_limit": 1,
        "operation_data_gap_min_count": 1,
        "task_max_drafts": 8,
        "task_urgent_deadline_days": 1,
        "task_normal_deadline_days": 7,
        "cost_budget_warning_percent": 0.8,
        "cost_condition_call_approval_threshold": 1,
        "cost_ai_report_merge_threshold": 2,
        "report_confidence_floor": 0.4,
        "report_max_sections": 3,
    }
    first = admin.put("/api/ai-command-center/settings", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 1
    assert first.json()["is_active"] is True

    second = admin.put(
        "/api/ai-command-center/settings",
        json={**payload, "operation_high_priority_limit": 2},
    )
    assert second.status_code == 200, second.text
    assert second.json()["version"] == 2
    assert second.json()["operation_high_priority_limit"] == 2

    profiles = manager.get("/api/ai-command-center/settings/profiles")
    assert profiles.status_code == 200, profiles.text
    profile_rows = [
        row
        for row in profiles.json()
        if row["agent_type"] == "operation_planning_agent" and row["scenario"] == "stress_week"
    ]
    assert [row["version"] for row in profile_rows] == [2, 1]
    assert profile_rows[0]["is_active"] is True
    assert profile_rows[1]["is_active"] is False

    selected = manager.get(
        "/api/ai-command-center/settings",
        params={"agent_type": "operation_planning_agent", "scenario": "stress_week"},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["version"] == 2

    run = manager.post(
        "/api/ai-command-center/runs",
        json={
            "agent_type": "operation_planning_agent",
            "asset_package_id": package_id,
            "rule_scenario": "stress_week",
        },
    )
    assert run.status_code == 200, run.text
    thresholds = next(item for item in run.json()["output"]["evidence"] if item["label"] == "rule_thresholds")
    assert thresholds["value"]["operation_high_priority_limit"] == 2
    assert thresholds["value"]["profile"]["agent_type"] == "operation_planning_agent"
    assert thresholds["value"]["profile"]["scenario"] == "stress_week"
    assert thresholds["value"]["profile"]["version"] == 2


def test_agent_run_review_loop_is_tenant_scoped_and_audited():
    from db.session import get_db_session
    from repositories import agent_repo
    from tests.api.admin_commercial_helpers import seed_user_and_login

    manager = seed_user_and_login(
        "ai-review-manager@example.com",
        role="manager",
        tenant_code="ai-review",
    )
    viewer = seed_user_and_login(
        "ai-review-viewer@example.com",
        role="viewer",
        tenant_code="ai-review",
    )
    package_id = _seed_asset_package("ai-review", with_result=True)
    created = manager.post(
        "/api/ai-command-center/runs",
        json={"agent_type": "pricing_strategy_agent", "asset_package_id": package_id},
    )
    assert created.status_code == 200, created.text
    run_id = created.json()["id"]

    denied = viewer.post(
        f"/api/ai-command-center/runs/{run_id}/reviews",
        json={"outcome": "accepted", "usefulness_score": 4, "accuracy_score": 4},
    )
    assert denied.status_code == 403, denied.text

    review_payload = {
        "outcome": "partial",
        "usefulness_score": 4,
        "accuracy_score": 3,
        "accepted_actions_count": 2,
        "rejected_actions_count": 1,
        "follow_up_required": True,
        "feedback": "证据充分，但报价建议需要下轮优化。",
    }
    created_review = manager.post(
        f"/api/ai-command-center/runs/{run_id}/reviews",
        json=review_payload,
    )
    assert created_review.status_code == 200, created_review.text
    assert created_review.json()["agent_run_id"] == run_id
    assert created_review.json()["follow_up_required"] is True

    reviews = manager.get(f"/api/ai-command-center/runs/{run_id}/reviews")
    assert reviews.status_code == 200, reviews.text
    assert reviews.json()[0]["outcome"] == "partial"

    insights = manager.get("/api/ai-command-center/run-reviews/insights")
    assert insights.status_code == 200, insights.text
    assert insights.json()["review_count"] == 1
    assert insights.json()["accepted_actions_count"] == 2
    assert insights.json()["rejected_actions_count"] == 1
    assert insights.json()["follow_up_required_count"] == 1
    assert insights.json()["requires_human_review"] is True
    assert insights.json()["recommendations"]

    foreign = seed_user_and_login(
        "ai-review-foreign@example.com",
        role="manager",
        tenant_code="ai-review-foreign",
    )
    leaked = foreign.post(
        f"/api/ai-command-center/runs/{run_id}/reviews",
        json=review_payload,
    )
    assert leaked.status_code == 404, leaked.text

    gen = get_db_session()
    session = next(gen)
    try:
        logs = agent_repo.list_decision_audit_logs(
            session,
            tenant_id=created.json()["tenant_id"],
            limit=10,
        )
        assert any(log.decision_type == "agent_run_review" and log.action == "created" for log in logs)
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
