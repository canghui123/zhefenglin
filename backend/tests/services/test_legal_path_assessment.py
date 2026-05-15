from models.simulation import LegalMaterialStatus, SandboxInput
from services.legal_path_assessment import assess_legal_paths
from services.sandbox_simulator import run_simulation


def _sandbox_input(**overrides) -> SandboxInput:
    data = {
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
        "legal_materials": LegalMaterialStatus(
            loan_contract=True,
            mortgage_contract=True,
            mortgage_registration=True,
            overdue_statement=True,
            repayment_records=True,
            debtor_identity=True,
            collection_records=True,
            vehicle_location_records=True,
            inventory_certificate=True,
            vehicle_photos=True,
            valuation_report=True,
            debt_balance_sheet=True,
            title_check=True,
            jurisdiction_clause=True,
            debt_matured=True,
            no_substantive_dispute=True,
            no_title_abnormality=True,
        ),
    }
    data.update(overrides)
    return SandboxInput(**data)


def test_legal_paths_score_complete_materials_as_suitable():
    litigation, special = assess_legal_paths(_sandbox_input())

    assert litigation.score >= 80
    assert litigation.level == "suitable"
    assert special.score >= 80
    assert special.level == "suitable"
    assert special.material_gaps == []


def test_special_procedure_missing_inventory_and_registration_is_high_risk():
    inp = _sandbox_input(
        vehicle_recovered=False,
        vehicle_in_inventory=False,
        legal_materials=LegalMaterialStatus(
            loan_contract=True,
            mortgage_contract=True,
            mortgage_registration=False,
            overdue_statement=True,
            repayment_records=True,
            debtor_identity=True,
            debt_matured=True,
            no_substantive_dispute=False,
            no_title_abnormality=True,
        ),
    )

    _, special = assess_legal_paths(inp)

    assert special.score < 60
    assert special.level in {"high_risk", "not_recommended"}
    assert "车辆收回或占有证明" in special.material_gaps
    assert "抵押登记证明" in special.material_gaps
    assert "substantive_dispute_risk" in special.risk_tags


def test_litigation_missing_core_materials_outputs_gaps():
    inp = _sandbox_input(
        legal_materials=LegalMaterialStatus(
            loan_contract=False,
            mortgage_contract=False,
            mortgage_registration=False,
            overdue_statement=False,
            repayment_records=False,
            debtor_identity=False,
            collection_records=False,
            valuation_report=False,
            debt_balance_sheet=False,
            no_substantive_dispute=True,
            no_title_abnormality=True,
        )
    )

    litigation, _ = assess_legal_paths(inp)

    assert litigation.score < 60
    assert "借款合同" in litigation.material_gaps
    assert "还款流水" in litigation.material_gaps
    assert "债务人身份信息" in litigation.material_gaps


def test_composite_scoring_explains_legal_risk_when_net_recovery_is_not_enough():
    inp = _sandbox_input(
        strategy_preference="reduce_legal_risk",
        legal_materials=LegalMaterialStatus(
            loan_contract=False,
            mortgage_contract=False,
            mortgage_registration=False,
            overdue_statement=False,
            repayment_records=False,
            debtor_identity=False,
            collection_records=False,
            vehicle_location_records=False,
            inventory_certificate=False,
            vehicle_photos=False,
            valuation_report=False,
            debt_balance_sheet=False,
            title_check=False,
            debt_matured=False,
            no_substantive_dispute=False,
            no_title_abnormality=False,
        ),
    )

    result = run_simulation(inp)
    special_score = next(score for score in result.path_scores if score.path == "D")

    assert special_score.legal_feasibility_score <= 40
    assert result.best_path != "D"
    assert "综合评分" in result.recommendation
