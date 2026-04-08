"""Repository-layer round trip for the sandbox: simulate -> get -> list."""
from fastapi.testclient import TestClient

from main import app


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


def test_sandbox_round_trip_uses_repository_layer():
    client = TestClient(app)

    sim = client.post("/api/sandbox/simulate", json=SAMPLE_INPUT)
    assert sim.status_code == 200, sim.text
    body = sim.json()
    result_id = body["id"]
    assert result_id > 0

    fetched = client.get(f"/api/sandbox/{result_id}")
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()
    assert data["id"] == result_id
    assert data["car_description"] == SAMPLE_INPUT["car_description"]
    for key in ("path_a", "path_b", "path_c", "path_d", "path_e"):
        assert data[key] is not None, f"{key} should be persisted"

    listed = client.get("/api/sandbox/list/all")
    assert listed.status_code == 200
    ids = [r["id"] for r in listed.json()]
    assert result_id in ids
