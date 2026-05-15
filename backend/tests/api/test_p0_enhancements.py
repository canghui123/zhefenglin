import os


SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def test_asset_package_result_buyer_offer_and_pdf_include_p0_fields(authed_client):
    with open(SAMPLE_EXCEL, "rb") as f:
        upload = authed_client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "p0_asset_package.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert upload.status_code == 200, upload.text
    package_id = upload.json()["package_id"]

    calc = authed_client.post(
        "/api/asset-package/calculate",
        json={
            "package_id": package_id,
            "parameters": {
                "asset_package_type": "inventory",
                "vehicle_condition": "good",
            },
        },
    )
    assert calc.status_code == 202, calc.text
    job = authed_client.get(f"/api/jobs/{calc.json()['job_id']}")
    assert job.status_code == 200, job.text
    assert job.json()["status"] == "succeeded"

    package = authed_client.get(f"/api/asset-package/{package_id}")
    assert package.status_code == 200, package.text
    result = package.json()["results"]
    assert result["summary"]["tradeability_score"] >= 0
    assert result["summary"]["tradeability_level"] in {"A", "B", "C", "D", "E"}
    assert "valuation_confidence_score" in result["assets"][0]
    assert "valuation_source" in result["assets"][0]

    offer = authed_client.post(
        f"/api/asset-package/{package_id}/buyer-offer-analysis",
        json={"buyer_offer_price": 100000, "buyer_offer_note": "测试报价"},
    )
    assert offer.status_code == 200, offer.text
    assert offer.json()["buyer_offer_price"] == 100000
    assert offer.json()["negotiation_suggestions"]

    package_after_offer = authed_client.get(f"/api/asset-package/{package_id}")
    assert package_after_offer.status_code == 200, package_after_offer.text
    assert (
        package_after_offer.json()["results"]["summary"]["buyer_offer_analysis"][
            "buyer_offer_price"
        ]
        == 100000
    )

    pdf = authed_client.get(f"/api/asset-package/{package_id}/report.pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_sandbox_result_and_legal_assessment_endpoint_include_material_gaps(authed_client):
    payload = {
        "car_description": "2022 丰田 凯美瑞 2.0G",
        "entry_date": "2026-04-01",
        "overdue_bucket": "M4(91-120天)",
        "overdue_amount": 120000,
        "che300_value": 150000,
        "vehicle_type": "japanese",
        "vehicle_age_years": 4,
        "daily_parking": 30,
        "recovery_cost": 2000,
        "vehicle_recovered": True,
        "vehicle_in_inventory": True,
        "strategy_preference": "reduce_legal_risk",
        "legal_materials": {
            "loan_contract": False,
            "mortgage_contract": False,
            "mortgage_registration": False,
            "overdue_statement": False,
            "repayment_records": False,
            "debtor_identity": False,
            "collection_records": False,
            "vehicle_location_records": False,
            "inventory_certificate": False,
            "vehicle_photos": False,
            "valuation_report": False,
            "debt_balance_sheet": False,
            "title_check": False,
            "debt_matured": False,
            "no_substantive_dispute": False,
            "no_title_abnormality": False,
        },
    }

    sim = authed_client.post("/api/sandbox/simulate", json=payload)
    assert sim.status_code == 200, sim.text
    body = sim.json()
    assert body["path_scores"]
    assert body["path_b"]["legal_assessment"]["material_gaps"]
    assert body["path_d"]["legal_assessment"]["material_gaps"]

    legal = authed_client.get(f"/api/sandbox/{body['id']}/legal-assessment")
    assert legal.status_code == 200, legal.text
    legal_body = legal.json()
    assert legal_body["litigation"]["score"] < 60
    assert "借款合同" in legal_body["litigation"]["material_gaps"]
    assert legal_body["special_procedure"]["score"] <= 40
