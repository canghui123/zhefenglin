def test_advanced_portfolio_pages_require_feature_entitlement():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "portfolio-standard@example.com",
        role="manager",
        tenant_code="portfolio-standard",
    )
    seed_subscription(tenant_code="portfolio-standard", plan_code="standard")

    executive = client.get("/api/portfolio/executive")
    assert executive.status_code == 403, executive.text
    executive_body = executive.json()
    assert executive_body["error"]["code"] == "FEATURE_NOT_ENABLED"
    assert executive_body["error"]["details"]["feature_key"] == "portfolio.advanced_pages"

    manager = client.get("/api/portfolio/manager-playbook")
    assert manager.status_code == 403, manager.text
    manager_body = manager.json()
    assert manager_body["error"]["code"] == "FEATURE_NOT_ENABLED"
    assert manager_body["error"]["details"]["feature_key"] == "portfolio.advanced_pages"


def test_advanced_portfolio_pages_allow_enabled_plan():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    client = seed_user_and_login(
        "portfolio-pro@example.com",
        role="manager",
        tenant_code="portfolio-pro",
    )
    seed_subscription(tenant_code="portfolio-pro", plan_code="pro_manager")

    executive = client.get("/api/portfolio/executive")
    assert executive.status_code == 200, executive.text

    manager = client.get("/api/portfolio/manager-playbook")
    assert manager.status_code == 200, manager.text
