from db.models.model_routing import ModelRoutingRule
from services import model_routing_service
from tests.services.commercial_test_helpers import create_tenant, make_session
from scripts.seed_commercial_defaults import seed_defaults


def test_resolve_route_returns_global_default_for_known_task_type():
    session = make_session()
    try:
        seed_defaults(session)
        session.commit()

        route = model_routing_service.resolve_route(
            session,
            task_type="medium_task",
            tenant_id=None,
        )

        assert route["scope"] == "global"
        assert route["preferred_model"] == "qwen-plus"
        assert route["fallback_model"] == "qwen-turbo"
        assert route["prompt_version"] == "v1"
    finally:
        session.close()


def test_resolve_route_prefers_active_tenant_override():
    session = make_session()
    try:
        seed_defaults(session)
        tenant = create_tenant(session)
        session.add(
            ModelRoutingRule(
                scope="tenant",
                tenant_id=tenant.id,
                task_type="medium_task",
                preferred_model="qwen-long",
                fallback_model="qwen-plus",
                allow_batch=False,
                allow_search=True,
                allow_high_cost_mode=True,
                prompt_version="tenant-v2",
                is_active=True,
                created_by=None,
            )
        )
        session.commit()

        route = model_routing_service.resolve_route(
            session,
            task_type="medium_task",
            tenant_id=tenant.id,
        )

        assert route["scope"] == "tenant"
        assert route["preferred_model"] == "qwen-long"
        assert route["allow_search"] is True
        assert route["prompt_version"] == "tenant-v2"
    finally:
        session.close()
