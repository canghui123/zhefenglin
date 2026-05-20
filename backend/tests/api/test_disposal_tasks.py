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


def test_generate_tasks_from_portfolio_capacity_plan_is_idempotent():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login("portfolio-task@example.com", role="operator", tenant_code="portfolio-tasks")

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
