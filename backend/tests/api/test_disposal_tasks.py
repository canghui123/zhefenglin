def test_task_lifecycle_create_assign_complete_and_audit():
    from repositories import audit_repo
    from db.session import get_db_session
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login("task-operator@example.com", role="operator", tenant_code="tasks")

    created = client.post(
        "/api/tasks",
        json={
            "task_type": "auction",
            "title": "上架竞拍测试车",
            "priority": "high",
            "expected_recovery": 88000,
            "expected_cost": 2500,
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    owner_user_id = me.json()["id"]

    assigned = client.post(f"/api/tasks/{task_id}/assign", json={"owner_user_id": owner_user_id})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "assigned"
    assert assigned.json()["owner_user_id"] == owner_user_id

    completed = client.post(
        f"/api/tasks/{task_id}/complete",
        json={
            "actual_recovery": 90000,
            "result_note": "已成交",
            "variance_reason": "成交价高于底价",
            "evidence_files": ["oss://evidence/task.pdf"],
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "done"
    assert completed.json()["actual_recovery"] == 90000
    completed_at = completed.json()["completed_at"]
    assert completed_at

    detail = client.get(f"/api/tasks/{task_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["completed_at"] == completed_at
    assert detail.json()["result"]["completed_at"] == completed_at

    listed = client.get("/api/tasks?status=done")
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == task_id for row in listed.json())

    gen = get_db_session()
    session = next(gen)
    try:
        assert audit_repo.list_logs(session, action="task_complete")
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_task_assignment_rejects_user_outside_current_tenant():
    from db.session import get_db_session
    from repositories import tenant_repo, user_repo
    from services.password_service import hash_password
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "task-owner@example.com",
        role="operator",
        tenant_code="task-owner-tenant",
    )
    gen = get_db_session()
    session = next(gen)
    try:
        foreign_tenant = tenant_repo.get_or_create_tenant(
            session,
            code="foreign-task-tenant",
            name="FOREIGN",
        )
        foreign_user = user_repo.create_user(
            session,
            email="foreign-assignee@example.com",
            password_hash=hash_password("Passw0rd!1"),
            role="operator",
            display_name="foreign",
        )
        tenant_repo.create_membership(
            session,
            user_id=foreign_user.id,
            tenant_id=foreign_tenant.id,
            role="operator",
        )
        user_repo.set_default_tenant(session, foreign_user.id, foreign_tenant.id)
        session.commit()
        foreign_user_id = foreign_user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    created = client.post(
        "/api/tasks",
        json={"task_type": "auction", "title": "跨租户分配校验"},
    )
    assert created.status_code == 200, created.text

    assigned = client.post(
        f"/api/tasks/{created.json()['id']}/assign",
        json={"owner_user_id": foreign_user_id},
    )
    assert assigned.status_code == 400, assigned.text
    assert "不属于当前租户" in assigned.text


def test_task_assignees_are_active_users_in_current_tenant_and_can_be_assigned():
    from db.session import get_db_session
    from repositories import tenant_repo, user_repo
    from services.password_service import hash_password
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "task-assignee-owner@example.com",
        role="operator",
        tenant_code="task-assignees",
    )
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "task-assignees")
        assert tenant is not None
        active_user = user_repo.create_user(
            session,
            email="active-task-assignee@example.com",
            password_hash=hash_password("Passw0rd!1"),
            role="operator",
            display_name="同租户执行人",
        )
        tenant_repo.create_membership(
            session,
            user_id=active_user.id,
            tenant_id=tenant.id,
            role="operator",
        )
        inactive_user = user_repo.create_user(
            session,
            email="inactive-task-assignee@example.com",
            password_hash=hash_password("Passw0rd!1"),
            role="operator",
            display_name="禁用执行人",
        )
        tenant_repo.create_membership(
            session,
            user_id=inactive_user.id,
            tenant_id=tenant.id,
            role="operator",
        )
        inactive_user.is_active = False
        foreign_tenant = tenant_repo.get_or_create_tenant(
            session,
            code="foreign-task-assignees",
            name="FOREIGN",
        )
        foreign_user = user_repo.create_user(
            session,
            email="foreign-task-assignee@example.com",
            password_hash=hash_password("Passw0rd!1"),
            role="operator",
            display_name="跨租户执行人",
        )
        tenant_repo.create_membership(
            session,
            user_id=foreign_user.id,
            tenant_id=foreign_tenant.id,
            role="operator",
        )
        session.commit()
        active_user_id = active_user.id
        inactive_user_id = inactive_user.id
        foreign_user_id = foreign_user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    assignees = client.get("/api/tasks/assignees")
    assert assignees.status_code == 200, assignees.text
    assignee_ids = {row["id"] for row in assignees.json()}
    assert active_user_id in assignee_ids
    assert inactive_user_id not in assignee_ids
    assert foreign_user_id not in assignee_ids

    created = client.post(
        "/api/tasks",
        json={"task_type": "auction", "title": "指定真实人员分配"},
    )
    assert created.status_code == 200, created.text

    assigned = client.post(
        f"/api/tasks/{created.json()['id']}/assign",
        json={"owner_user_id": active_user_id},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "assigned"
    assert assigned.json()["owner_user_id"] == active_user_id
    assert assigned.json()["owner_user_email"] == "active-task-assignee@example.com"
    assert assigned.json()["owner_display_name"] == "同租户执行人"

    detail = client.get(f"/api/tasks/{created.json()['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["owner_user_email"] == "active-task-assignee@example.com"
    assert detail.json()["owner_display_name"] == "同租户执行人"

    listed = client.get("/api/tasks")
    assert listed.status_code == 200, listed.text
    listed_task = next(row for row in listed.json() if row["id"] == created.json()["id"])
    assert listed_task["owner_user_email"] == "active-task-assignee@example.com"
    assert listed_task["owner_display_name"] == "同租户执行人"


def test_task_evidence_upload_is_tenant_scoped_and_returned_from_task_detail():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "task-evidence-owner@example.com",
        role="operator",
        tenant_code="task-evidence-owner",
    )
    created = client.post(
        "/api/tasks",
        json={"task_type": "auction", "title": "证据上传任务"},
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    uploaded = client.post(
        f"/api/tasks/{task_id}/evidence",
        files={"file": ("proof.pdf", b"%PDF-1.4 task evidence", "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["storage_key"].startswith("tasks/")
    assert f"/{task_id}/evidence/" in body["storage_key"]
    assert body["filename"] == "proof.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size"] == len(b"%PDF-1.4 task evidence")

    detail = client.get(f"/api/tasks/{task_id}")
    assert detail.status_code == 200, detail.text
    assert body["storage_key"] in detail.json()["evidence_files"]

    invalid = client.post(
        f"/api/tasks/{task_id}/evidence",
        files={"file": ("script.sh", b"#!/bin/sh", "application/x-sh")},
    )
    assert invalid.status_code == 400, invalid.text

    completed = client.post(
        f"/api/tasks/{task_id}/complete",
        json={
            "actual_recovery": 91000,
            "result_note": "已归档",
            "evidence_files": ["tasks/manual/manual-proof.pdf"],
        },
    )
    assert completed.status_code == 200, completed.text
    assert body["storage_key"] in completed.json()["evidence_files"]
    assert "tasks/manual/manual-proof.pdf" in completed.json()["evidence_files"]

    detail_after_complete = client.get(f"/api/tasks/{task_id}")
    assert detail_after_complete.status_code == 200, detail_after_complete.text
    assert body["storage_key"] in detail_after_complete.json()["evidence_files"]
    assert "tasks/manual/manual-proof.pdf" in detail_after_complete.json()["evidence_files"]

    foreign_client = seed_user_and_login(
        "task-evidence-foreign@example.com",
        role="operator",
        tenant_code="task-evidence-foreign",
    )
    foreign_upload = foreign_client.post(
        f"/api/tasks/{task_id}/evidence",
        files={"file": ("foreign.pdf", b"%PDF-1.4 foreign", "application/pdf")},
    )
    assert foreign_upload.status_code == 404, foreign_upload.text


def test_generate_tasks_from_portfolio_capacity_plan_is_idempotent():
    from db.models.portfolio import AssetSegment
    from db.session import get_db_session
    from repositories import portfolio_repo, tenant_repo
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login("portfolio-task@example.com", role="operator", tenant_code="portfolio-tasks")
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "portfolio-tasks")
        assert tenant is not None
        snapshot = portfolio_repo.create_snapshot(
            session,
            tenant_id=tenant.id,
            org_id="portfolio-tasks",
            snapshot_date="2026-05-21",
        )
        segment = AssetSegment(
            tenant_id=tenant.id,
            org_id="portfolio-tasks",
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
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    first = client.post("/api/tasks/generate-from-portfolio")
    assert first.status_code == 200, first.text
    assert first.json()

    second = client.post("/api/tasks/generate-from-portfolio")
    assert second.status_code == 200, second.text
    assert [row["id"] for row in second.json()] == [row["id"] for row in first.json()]


def test_generate_task_from_sandbox_result():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login("sandbox-task@example.com", role="operator", tenant_code="sandbox-tasks")
    simulated = client.post(
        "/api/sandbox/simulate",
        json={
            "car_description": "2021 丰田 凯美瑞 2.0G",
            "entry_date": "2026-04-01",
            "overdue_bucket": "M4(91-120天)",
            "overdue_amount": 120000,
            "che300_value": 150000,
            "vehicle_type": "japanese",
            "vehicle_age_years": 5,
            "vehicle_recovered": True,
            "vehicle_in_inventory": True,
        },
    )
    assert simulated.status_code == 200, simulated.text
    result_id = simulated.json()["id"]

    generated = client.post(f"/api/tasks/generate-from-sandbox/{result_id}")
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["source_type"] == "sandbox"
    assert body["source_id"] == str(result_id)
    assert body["task_type"] in {"collection", "litigation", "auction", "special_procedure", "restructure"}
