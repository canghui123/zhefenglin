"""Repository-layer round trip for the sandbox: simulate -> get -> list."""

SAMPLE_INPUT = {
    "car_description": "2019 丰田 凯美瑞 2.5L",
    "entry_date": "2026-01-15",
    "overdue_amount": 120000,
    "che300_value": 135000,
    "vehicle_type": "japanese",
    "vehicle_age_years": 6,
    "daily_parking": 20,
    "recovery_cost": 2000,
}


def test_sandbox_round_trip_uses_repository_layer(authed_client):
    sim = authed_client.post("/api/sandbox/simulate", json=SAMPLE_INPUT)
    assert sim.status_code == 200, sim.text
    body = sim.json()
    result_id = body["id"]
    assert result_id > 0

    fetched = authed_client.get(f"/api/sandbox/{result_id}")
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()
    assert data["id"] == result_id
    assert data["car_description"] == SAMPLE_INPUT["car_description"]
    for key in ("path_a", "path_b", "path_c", "path_d", "path_e"):
        assert data[key] is not None, f"{key} should be persisted"

    listed = authed_client.get("/api/sandbox/list/all")
    assert listed.status_code == 200
    ids = [r["id"] for r in listed.json()]
    assert result_id in ids


def test_sandbox_auto_fills_missing_che300_and_auction_discount(authed_client):
    payload = {
        "car_description": "2020 丰田 凯美瑞 2.0G",
        "vin": "LVGBM51K0LG000001",
        "first_registration": "2020-01-01",
        "entry_date": "2026-04-28",
        "overdue_bucket": "M3(61-90天)",
        "overdue_amount": 100000,
        "vehicle_type": "japanese",
        "vehicle_age_years": 6,
        "auction_discount_rate": None,
    }

    response = authed_client.post("/api/sandbox/simulate", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["input"]["che300_value"] > 0
    assert body["path_c"]["auction_discount_rate"] > 0
    assert body["path_c"]["commission"] == 0


def test_sandbox_redefault_none_requires_history(authed_client):
    payload = dict(SAMPLE_INPUT)
    payload["restructure_redefault_rate"] = None

    response = authed_client.post("/api/sandbox/simulate", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SANDBOX_INPUT_INCOMPLETE"


def test_sandbox_batch_import_preview_marks_missing_fields_and_auto_values(authed_client):
    csv = (
        "车辆描述,VIN,入库日期,逾期天数,逾期金额,当前车300估值,收车状态,入库状态\n"
        "2021 丰田 凯美瑞,LVGBM51K0MG000001,2026-04-28,75,12万,无,已收回,已入库\n"
        ",,2026-04-28,80,90000,无,未收回,未入库\n"
    ).encode("utf-8-sig")

    response = authed_client.post(
        "/api/sandbox/import-preview",
        files={"file": ("sandbox.csv", csv, "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_rows"] == 2
    first = body["rows"][0]
    assert first["input"]["che300_value"] > 0
    assert first["che300_auto_filled"] is True
    assert first["missing_fields"] == []
    second = body["rows"][1]
    assert "car_description" in second["missing_fields"]
