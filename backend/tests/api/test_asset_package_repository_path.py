"""Repository-layer round trip: upload -> get returns the same package."""
import os

SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def test_asset_package_round_trip_uses_repository_layer(authed_client):
    with open(SAMPLE_EXCEL, "rb") as f:
        upload = authed_client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "roundtrip.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert upload.status_code == 200, upload.text
    package_id = upload.json()["package_id"]
    assert package_id > 0

    # The get endpoint must find the package that upload just created.
    fetched = authed_client.get(f"/api/asset-package/{package_id}")
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["id"] == package_id
    assert body["name"] == "roundtrip.xlsx"
    assert body["total_assets"] > 0

    # And listing must include the new package.
    listed = authed_client.get("/api/asset-package/list/all")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert package_id in ids
