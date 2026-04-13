"""Task 9 — LLM client timeout / error handling.

When the LLM API times out or errors, the service should return a
clean fallback instead of letting raw exceptions propagate.
"""
import pytest
from unittest.mock import patch, AsyncMock

from services.llm_client import chat_completion
from services.http_client import ExternalTimeoutError


def test_llm_timeout_returns_fallback():
    """When DeepSeek times out, chat_completion returns a fallback string
    rather than crashing with a raw exception."""
    import asyncio

    with patch("services.llm_client.get_llm_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("Connection timeout")
        mock_get.return_value = mock_client

        result = asyncio.get_event_loop().run_until_complete(
            chat_completion("system", "user")
        )
        assert isinstance(result, str)
        assert "失败" in result or "超时" in result or "LLM" in result


def test_llm_no_api_key_returns_placeholder():
    """When no API key is configured, we get a placeholder, not an error."""
    import asyncio

    with patch("services.llm_client.settings") as mock_settings:
        mock_settings.deepseek_api_key = ""
        mock_settings.deepseek_base_url = "https://api.deepseek.com"

        result = asyncio.get_event_loop().run_until_complete(
            chat_completion("system", "user")
        )
        assert "LLM" in result or "未配置" in result
