from db.models.decision_model_config import RegionDisposalCoefficient
from db.session import get_db_session
from models.model_feedback import DisposalOutcomeCreate
from repositories import tenant_repo, user_repo
from services.model_feedback_service import (
    compute_feedback_summary,
    record_disposal_outcome,
    run_learning_cycle,
)
from services.password_service import hash_password


def _session_with_tenant_user():
    gen = get_db_session()
    session = next(gen)
    tenant = tenant_repo.get_or_create_tenant(
        session,
        code="feedback",
        name="FEEDBACK",
    )
    user = user_repo.create_user(
        session,
        email="feedback@example.com",
        password_hash=hash_password("Passw0rd!"),
        role="manager",
        display_name="manager",
    )
    tenant_repo.create_membership(
        session,
        user_id=user.id,
        tenant_id=tenant.id,
        role="manager",
    )
    user_repo.set_default_tenant(session, user.id, tenant.id)
    return gen, session, tenant.id, user.id


def _record(session, tenant_id: int, user_id: int, **overrides):
    payload = {
        "asset_identifier": "CAR-001",
        "strategy_path": "auction",
        "province": "江苏省",
        "city": "南京市",
        "predicted_recovery_amount": 100000,
        "actual_recovery_amount": 90000,
        "predicted_cycle_days": 30,
        "actual_cycle_days": 45,
        "predicted_success_probability": 0.8,
        "outcome_status": "failed",
    }
    payload.update(overrides)
    return record_disposal_outcome(
        session,
        tenant_id=tenant_id,
        created_by=user_id,
        req=DisposalOutcomeCreate(**payload),
    )


def test_feedback_summary_computes_bias_and_success_gap():
    gen, session, tenant_id, user_id = _session_with_tenant_user()
    try:
        _record(session, tenant_id, user_id, asset_identifier="CAR-001")
        _record(
            session,
            tenant_id,
            user_id,
            asset_identifier="CAR-002",
            actual_recovery_amount=110000,
            actual_cycle_days=30,
            outcome_status="success",
        )
        session.commit()

        summary = compute_feedback_summary(session, tenant_id=tenant_id)

        assert summary.sample_count == 2
        assert summary.recovery_bias_ratio == 0.0
        assert summary.cycle_bias_ratio == 0.25
        assert summary.actual_success_rate == 0.5
        assert summary.suggested_success_adjustment == -0.15
        assert summary.region_adjustments[0].province == "江苏省"
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_learning_run_can_apply_region_adjustment():
    gen, session, tenant_id, user_id = _session_with_tenant_user()
    try:
        session.add(
            RegionDisposalCoefficient(
                region_code="JS_NJ",
                province="江苏省",
                city="南京市",
                liquidity_speed_factor=1.0,
                legal_efficiency_factor=1.0,
                towing_cost_factor=1.0,
                is_active=True,
            )
        )
        _record(session, tenant_id, user_id, actual_cycle_days=15, outcome_status="success")
        session.commit()

        run = run_learning_cycle(
            session,
            tenant_id=tenant_id,
            created_by=user_id,
            apply_region_adjustments=True,
        )
        session.commit()

        assert run.applied is True
        assert run.sample_count == 1
        region = session.query(RegionDisposalCoefficient).filter_by(region_code="JS_NJ").one()
        assert region.liquidity_speed_factor > 1.0
        assert region.legal_efficiency_factor > 1.0
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
