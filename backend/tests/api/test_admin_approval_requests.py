def test_approval_request_flow_supports_create_approve_and_reject():
    from tests.api.admin_commercial_helpers import seed_subscription, seed_user_and_login

    seed_subscription(tenant_code="default", plan_code="standard")
    manager_client = seed_user_and_login("approval-manager@example.com", role="manager")
    admin_client = seed_user_and_login("approval-admin@example.com", role="admin")

    created = manager_client.post(
        "/api/admin/approval-requests",
        json={
            "type": "condition_pricing",
            "reason": "High-value vehicle needs approval",
            "related_object_type": "vehicle",
            "related_object_id": "VIN-001",
            "estimated_cost": 36,
            "metadata": {"source": "asset-pricing"},
        },
    )
    assert created.status_code == 200, created.text
    approval_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    assert created.json()["is_consumed"] is False
    assert created.json()["consumed_at"] is None
    assert created.json()["consumed_request_id"] is None

    listing = admin_client.get("/api/admin/approval-requests")
    assert listing.status_code == 200, listing.text
    assert any(item["id"] == approval_id for item in listing.json())

    approved = admin_client.post(
        f"/api/admin/approval-requests/{approval_id}/approve",
        json={"actual_cost": 36},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["is_consumed"] is False

    created_reject = manager_client.post(
        "/api/admin/approval-requests",
        json={
            "type": "condition_pricing",
            "reason": "Another vehicle",
            "related_object_type": "vehicle",
            "related_object_id": "VIN-002",
            "estimated_cost": 36,
        },
    )
    reject_id = created_reject.json()["id"]
    rejected = admin_client.post(
        f"/api/admin/approval-requests/{reject_id}/reject",
        json={"actual_cost": 0},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
