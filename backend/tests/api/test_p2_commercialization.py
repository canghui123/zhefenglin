import json


def _tenant_id(tenant_code: str) -> int:
    from db.session import get_db_session
    from repositories import tenant_repo

    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, tenant_code)
        assert tenant is not None
        return tenant.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_asset_package_compliance_checklist_persists_and_is_audited():
    from models.asset import PackageCalculationResult, PackageSummary
    from repositories import asset_package_repo, audit_repo
    from db.session import get_db_session
    from tests.api.admin_commercial_helpers import seed_user_and_login

    tenant_code = "p2-compliance"
    client = seed_user_and_login(
        "p2-compliance@example.com", role="operator", tenant_code=tenant_code
    )
    tenant_id = _tenant_id(tenant_code)

    gen = get_db_session()
    session = next(gen)
    try:
        pkg = asset_package_repo.create_package(
            session,
            tenant_id=tenant_id,
            name="compliance.xlsx",
            total_assets=1,
            created_by=1,
        )
        result = PackageCalculationResult(
            package_id=pkg.id,
            summary=PackageSummary(total_assets=1, analysis_report="测试报告"),
            assets=[],
        )
        asset_package_repo.save_package_result(
            session,
            pkg.id,
            tenant_id=tenant_id,
            parameters_json="{}",
            results_json=result.model_dump_json(),
        )
        session.commit()
        package_id = pkg.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    update = client.put(
        f"/api/asset-package/{package_id}/compliance-checklist",
        json={
            "asset_scope_confirmed": True,
            "internal_approval_completed": True,
            "asset_authenticity_verified": True,
            "transfer_restriction_checked": True,
            "pricing_basis_archived": True,
            "inquiry_process_recorded": True,
            "debtor_notification_arranged": True,
            "no_hidden_repurchase_commitment": True,
            "archive_completed": True,
            "watermark_export_completed": True,
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["compliance_level"] == "A"

    fetched = client.get(f"/api/asset-package/{package_id}/compliance-checklist")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["compliance_score"] == 100

    gen = get_db_session()
    session = next(gen)
    try:
        pkg = asset_package_repo.get_package_by_id(session, package_id, tenant_id=tenant_id)
        assert pkg is not None and pkg.results_json
        saved = json.loads(pkg.results_json)
        assert saved["summary"]["compliance_checklist"]["compliance_level"] == "A"
        assert audit_repo.list_logs(session, tenant_id=tenant_id, action="compliance_checklist_update")
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_viewer_asset_package_detail_masks_sensitive_fields():
    from repositories import asset_package_repo
    from db.session import get_db_session
    from tests.api.admin_commercial_helpers import seed_user_and_login

    tenant_code = "p2-masking"
    client = seed_user_and_login(
        "p2-masking@example.com", role="viewer", tenant_code=tenant_code
    )
    tenant_id = _tenant_id(tenant_code)

    gen = get_db_session()
    session = next(gen)
    try:
        pkg = asset_package_repo.create_package(
            session,
            tenant_id=tenant_id,
            name="masking.xlsx",
            total_assets=1,
        )
        asset_package_repo.save_package_result(
            session,
            pkg.id,
            tenant_id=tenant_id,
            parameters_json=json.dumps(
                {"asset_overrides": {"2": {"vin": "LSVNP41U2N2000001"}}}
            ),
            results_json=json.dumps(
                {
                    "summary": {"analysis_report": "ok"},
                    "assets": [{"row_number": 2, "vin": "LSVNP41U2N2000001"}],
                }
            ),
        )
        session.commit()
        package_id = pkg.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    response = client.get(f"/api/asset-package/{package_id}")
    assert response.status_code == 200, response.text
    body_text = response.text
    assert "LSVNP41U2N2000001" not in body_text
    assert "LSV" in body_text
    assert "0001" in body_text


def test_audit_and_cost_center_csv_exports_include_watermark():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "p2-export@example.com", role="manager", tenant_code="p2-export"
    )
    seed_subscription(tenant_code="p2-export", plan_code="pro_manager")

    audit_export = client.get("/api/admin/audit-logs/export")
    assert audit_export.status_code == 200, audit_export.text
    assert audit_export.text.startswith("# watermark: tenant=")
    assert "exported_at=" in audit_export.text

    cost_export = client.get("/api/admin/cost-center/export")
    assert cost_export.status_code == 200, cost_export.text
    assert cost_export.text.startswith("# watermark: tenant=")
    assert "tenant_id,tenant_code" in cost_export.text


def test_value_center_includes_task_closure_value_metrics():
    from db.session import get_db_session
    from repositories import work_order_repo
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    tenant_code = "p2-value"
    client = seed_user_and_login(
        "p2-value@example.com", role="manager", tenant_code=tenant_code
    )
    tenant_id = seed_subscription(tenant_code=tenant_code, plan_code="pro_manager")

    gen = get_db_session()
    session = next(gen)
    try:
        work_order_repo.create_work_order(
            session,
            tenant_id=tenant_id,
            created_by=1,
            order_type="auction",
            title="竞拍处置闭环",
            status="done",
            payload={"expected_recovery": 100000},
            result={"actual_recovery": 112000},
        )
        work_order_repo.create_work_order(
            session,
            tenant_id=tenant_id,
            created_by=1,
            order_type="collection",
            title="催收跟进",
            status="pending",
            payload={"expected_recovery": 50000},
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    response = client.get("/api/admin/cost-center/value-dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accelerated_cash_in"] >= 112000
    assert body["estimated_extra_recovery"] >= 12000
    assert body["auction_price_improvement"] >= 12000
    assert body["task_completion_rate"] == 50.0
    assert body["source_trace"]["task_count"] >= 2
    assert any(row["tenant_id"] == tenant_id for row in body["tenant_value_rows"])
