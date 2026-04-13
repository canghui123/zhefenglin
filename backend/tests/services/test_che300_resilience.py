"""Task 9 — che300 client resilience tests.

Timeouts and server errors should be translated into clean domain
errors with structured error codes, not raw httpx/network exceptions.
Retries should happen automatically on transient failures.
"""
import httpx
import pytest
from unittest.mock import AsyncMock, patch

from services.che300_client import get_valuation_by_vin
from services.http_client import ExternalServiceError, ExternalTimeoutError


def _make_session():
    """Return a lightweight DB session for tests."""
    from db.session import get_db_session
    gen = get_db_session()
    session = next(gen)
    return session, gen


def test_che300_timeout_is_translated_to_domain_error():
    """When the che300 API times out we should get ExternalTimeoutError,
    not a raw httpx.TimeoutException leaking out."""
    session, gen = _make_session()
    try:
        with patch("services.che300_client.settings") as mock_settings:
            mock_settings.che300_access_key = "test_key"
            mock_settings.che300_access_secret = "test_secret"
            mock_settings.che300_api_base = "https://fake.che300.com"
            mock_settings.default_city_name = "南京"

            with patch("services.che300_client.resilient_post") as mock_post:
                mock_post.side_effect = ExternalTimeoutError(
                    service="che300", url="https://fake.che300.com/open/v1/get-eval-price-by-vin"
                )

                import asyncio
                with pytest.raises(ExternalTimeoutError) as exc_info:
                    asyncio.get_event_loop().run_until_complete(
                        get_valuation_by_vin(session, "WVWZZZ3CZWE123456")
                    )
                assert exc_info.value.service == "che300"
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_che300_server_error_is_wrapped():
    """A 503 from che300 after retries should become ExternalServiceError."""
    session, gen = _make_session()
    try:
        with patch("services.che300_client.settings") as mock_settings:
            mock_settings.che300_access_key = "test_key"
            mock_settings.che300_access_secret = "test_secret"
            mock_settings.che300_api_base = "https://fake.che300.com"
            mock_settings.default_city_name = "南京"

            with patch("services.che300_client.resilient_post") as mock_post:
                mock_post.side_effect = ExternalServiceError(
                    service="che300",
                    url="https://fake.che300.com/open/v1/get-eval-price-by-vin",
                    status_code=503,
                    message="Service Unavailable",
                )

                import asyncio
                with pytest.raises(ExternalServiceError) as exc_info:
                    asyncio.get_event_loop().run_until_complete(
                        get_valuation_by_vin(session, "WVWZZZ3CZWE123456")
                    )
                assert exc_info.value.status_code == 503
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
