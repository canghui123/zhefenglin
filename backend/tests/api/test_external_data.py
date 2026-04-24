def test_operator_can_query_find_car_score(authed_client):
    response = authed_client.post(
        "/api/external-data/find-car-score",
        json={
            "city": "南京市",
            "gps_recent_days": 1,
            "etc_recent_days": 4,
            "violation_recent_days": 10,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["score"] >= 70
    assert body["level"] == "high"


def test_operator_can_query_judicial_risk_blocking_signal(authed_client):
    response = authed_client.post(
        "/api/external-data/judicial-risk",
        json={
            "debtor_name": "张三",
            "dishonest_enforced": True,
            "restricted_consumption": True,
            "litigation_count": 2,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["collection_blocked"] is True
    assert "失信被执行人" in body["risk_tags"]


def test_external_provider_catalog_is_readable_for_logged_in_user(authed_client):
    response = authed_client.get("/api/external-data/providers")

    assert response.status_code == 200, response.text
    codes = {item["provider_code"] for item in response.json()}
    assert "judicial_risk" in codes
