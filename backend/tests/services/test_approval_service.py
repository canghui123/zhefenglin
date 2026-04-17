import pytest

from errors import BusinessError
from services import approval_service
from tests.services.commercial_test_helpers import (
    create_tenant,
    create_user,
    make_session,
)


def test_create_request_starts_in_pending_state():
    session = make_session()
    try:
        tenant = create_tenant(session)
        applicant = create_user(session, email="applicant@example.com", role="manager")

        request = approval_service.create_request(
            session,
            tenant_id=tenant.id,
            applicant_user_id=applicant.id,
            type="condition_pricing",
            reason="High value vehicle requires additional pricing review",
            related_object_type="vehicle",
            related_object_id="VIN123",
            estimated_cost=36,
            metadata={"source": "asset-pricing"},
        )
        session.commit()

        assert request.status == "pending"
        assert request.actual_cost == 0
        assert request.decided_at is None
        assert request.consumed_at is None
        assert request.consumed_request_id is None
    finally:
        session.close()


def test_approve_and_reject_update_request_status():
    session = make_session()
    try:
        tenant = create_tenant(session)
        applicant = create_user(session, email="applicant2@example.com", role="manager")
        approver = create_user(session, email="approver@example.com", role="admin")
        approve_request = approval_service.create_request(
            session,
            tenant_id=tenant.id,
            applicant_user_id=applicant.id,
            type="condition_pricing",
            reason="Approve this one",
            estimated_cost=36,
        )
        reject_request = approval_service.create_request(
            session,
            tenant_id=tenant.id,
            applicant_user_id=applicant.id,
            type="condition_pricing",
            reason="Reject this one",
            estimated_cost=36,
        )
        session.flush()

        approved = approval_service.approve(
            session,
            approval_request_id=approve_request.id,
            approver_user_id=approver.id,
            actual_cost=36,
        )
        rejected = approval_service.reject(
            session,
            approval_request_id=reject_request.id,
            approver_user_id=approver.id,
            actual_cost=0,
        )
        session.commit()

        assert approved.status == "approved"
        assert approved.actual_cost == 36
        assert approved.approver_user_id == approver.id
        assert approved.decided_at is not None

        assert rejected.status == "rejected"
        assert rejected.actual_cost == 0
        assert rejected.approver_user_id == approver.id
        assert rejected.decided_at is not None
    finally:
        session.close()


def test_cannot_decide_same_request_twice():
    session = make_session()
    try:
        tenant = create_tenant(session)
        applicant = create_user(session, email="applicant3@example.com", role="manager")
        approver = create_user(session, email="approver2@example.com", role="admin")
        request = approval_service.create_request(
            session,
            tenant_id=tenant.id,
            applicant_user_id=applicant.id,
            type="condition_pricing",
            reason="Only once",
            estimated_cost=36,
        )
        session.flush()

        approval_service.approve(
            session,
            approval_request_id=request.id,
            approver_user_id=approver.id,
            actual_cost=36,
        )

        with pytest.raises(BusinessError) as excinfo:
            approval_service.reject(
                session,
                approval_request_id=request.id,
                approver_user_id=approver.id,
            )

        assert excinfo.value.code == "APPROVAL_ALREADY_DECIDED"
    finally:
        session.close()


def test_validate_for_execution_requires_approved_matching_request():
    session = make_session()
    try:
        tenant = create_tenant(session)
        other_tenant = create_tenant(session, code="tenant-b", name="Tenant B")
        applicant = create_user(session, email="applicant4@example.com", role="manager")
        approver = create_user(session, email="approver4@example.com", role="admin")
        request = approval_service.create_request(
            session,
            tenant_id=tenant.id,
            applicant_user_id=applicant.id,
            type="condition_pricing",
            reason="Need advanced pricing",
            related_object_type="asset_package",
            related_object_id="12",
            estimated_cost=36,
        )
        session.flush()

        with pytest.raises(BusinessError) as pending_error:
            approval_service.validate_for_execution(
                session,
                approval_request_id=request.id,
                tenant_id=tenant.id,
                type="condition_pricing",
                related_object_type="asset_package",
                related_object_id="12",
            )
        assert pending_error.value.code == "APPROVAL_NOT_APPROVED"

        approval_service.approve(
            session,
            approval_request_id=request.id,
            approver_user_id=approver.id,
            actual_cost=36,
        )

        with pytest.raises(BusinessError) as mismatch_error:
            approval_service.validate_for_execution(
                session,
                approval_request_id=request.id,
                tenant_id=other_tenant.id,
                type="condition_pricing",
                related_object_type="asset_package",
                related_object_id="12",
            )
        assert mismatch_error.value.code == "APPROVAL_CONTEXT_MISMATCH"

        validated = approval_service.validate_for_execution(
            session,
            approval_request_id=request.id,
            tenant_id=tenant.id,
            type="condition_pricing",
            related_object_type="asset_package",
            related_object_id="12",
        )
        assert validated.id == request.id
    finally:
        session.close()


def test_consume_request_prevents_reuse():
    session = make_session()
    try:
        tenant = create_tenant(session)
        applicant = create_user(session, email="applicant5@example.com", role="manager")
        approver = create_user(session, email="approver5@example.com", role="admin")
        request = approval_service.create_request(
            session,
            tenant_id=tenant.id,
            applicant_user_id=applicant.id,
            type="condition_pricing",
            reason="One-time approval",
            related_object_type="vehicle",
            related_object_id="VIN-APPROVED",
            estimated_cost=36,
        )
        session.flush()
        approval_service.approve(
            session,
            approval_request_id=request.id,
            approver_user_id=approver.id,
            actual_cost=36,
        )

        consumed = approval_service.consume_request(
            session,
            approval_request_id=request.id,
            consumed_request_id="req-123",
        )

        assert consumed.consumed_at is not None
        assert consumed.consumed_request_id == "req-123"

        with pytest.raises(BusinessError) as excinfo:
            approval_service.validate_for_execution(
                session,
                approval_request_id=request.id,
                tenant_id=tenant.id,
                type="condition_pricing",
                related_object_type="vehicle",
                related_object_id="VIN-APPROVED",
            )
        assert excinfo.value.code == "APPROVAL_ALREADY_CONSUMED"
    finally:
        session.close()
