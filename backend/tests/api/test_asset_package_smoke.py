import os

SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def test_upload_returns_package_id(authed_client):
    with open(SAMPLE_EXCEL, "rb") as f:
        response = authed_client.post(
            "/api/asset-package/upload",
            files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "package_id" in data
    assert data["parse_result"]["success_rows"] > 0


def test_upload_rejects_non_excel(authed_client):
    response = authed_client.post(
        "/api/asset-package/upload",
        files={"file": ("test.txt", b"not excel", "text/plain")},
    )
    assert response.status_code == 400
