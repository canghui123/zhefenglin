import os


SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def _upload_sample_package(authed_client) -> int:
    with open(SAMPLE_EXCEL, "rb") as f:
        response = authed_client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "validation.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 200, response.text
    return response.json()["package_id"]


def test_calculate_rejects_negative_discount_rate(authed_client):
    package_id = _upload_sample_package(authed_client)

    response = authed_client.post(
        "/api/asset-package/calculate",
        json={
            "package_id": package_id,
            "parameters": {
                "buyout_strategy": "discount",
                "discount_rate": -0.5,
            },
        },
    )

    assert response.status_code == 422, response.text


def test_calculate_rejects_non_positive_ai_buyout_overrides(authed_client):
    package_id = _upload_sample_package(authed_client)

    response = authed_client.post(
        "/api/asset-package/calculate",
        json={
            "package_id": package_id,
            "parameters": {
                "buyout_strategy": "ai_suggest",
            },
            "ai_buyout_overrides": {
                "2": -100000,
            },
        },
    )

    assert response.status_code == 422, response.text
