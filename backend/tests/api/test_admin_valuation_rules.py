"""Tenant isolation tests for /api/admin/valuation-rules."""


def test_valuation_rules_tenant_admin_can_upsert_and_list():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "valrules-admin-a@example.com", role="admin", tenant_code="valrules-tenant-a"
    )

    upsert = client.put(
        "/api/admin/valuation-rules",
        json={
            "trigger_type": "manual",
            "enabled": True,
            "trigger_config": {"note": "tenant-a rule"},
        },
    )
    assert upsert.status_code == 200, upsert.text

    listed = client.get("/api/admin/valuation-rules")
    assert listed.status_code == 200, listed.text
    assert any(
        r["trigger_config"].get("note") == "tenant-a rule" for r in listed.json()
    )


def test_valuation_rules_reject_global_scope_from_tenant_admin():
    from tests.api.admin_commercial_helpers import seed_user_and_login

    client = seed_user_and_login(
        "valrules-reject-global@example.com",
        role="admin",
        tenant_code="valrules-reject-global",
    )

    response = client.put(
        "/api/admin/valuation-rules",
        json={
            "scope": "global",
            "trigger_type": "manual",
            "enabled": True,
            "trigger_config": {},
        },
    )
    assert response.status_code == 403, response.text


def test_valuation_rules_reject_writing_to_other_tenant():
    from tests.api.admin_commercial_helpers import seed_user_and_login
    from db.session import get_db_session
    from repositories import tenant_repo

    gen = get_db_session()
    session = next(gen)
    try:
        other = tenant_repo.get_or_create_tenant(
            session, code="valrules-other-tenant", name="OTHER"
        )
        other_id = other.id
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = seed_user_and_login(
        "valrules-a@example.com", role="admin", tenant_code="valrules-tenant-a2"
    )

    response = client.put(
        "/api/admin/valuation-rules",
        json={
            "tenant_id": other_id,
            "trigger_type": "manual",
            "enabled": True,
            "trigger_config": {},
        },
    )
    assert response.status_code == 403, response.text


def test_valuation_rules_list_hides_other_tenant_rules():
    from tests.api.admin_commercial_helpers import seed_user_and_login
    from db.session import get_db_session
    from repositories import tenant_repo, valuation_rule_repo

    import json as _json

    gen = get_db_session()
    session = next(gen)
    try:
        other = tenant_repo.get_or_create_tenant(
            session, code="valrules-leak-other", name="OTHER"
        )
        valuation_rule_repo.upsert_rule(
            session,
            scope="tenant",
            tenant_id=other.id,
            enabled=True,
            trigger_type="manual",
            trigger_config_json=_json.dumps({"note": "should-not-be-visible"}),
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = seed_user_and_login(
        "valrules-leak-a@example.com", role="admin", tenant_code="valrules-leak-a"
    )

    response = client.get("/api/admin/valuation-rules")
    assert response.status_code == 200, response.text
    for rule in response.json():
        assert rule["trigger_config"].get("note") != "should-not-be-visible"
