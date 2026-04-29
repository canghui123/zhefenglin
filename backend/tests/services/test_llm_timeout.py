"""Task 9 — LLM client timeout / error handling.

When the LLM API times out or errors, the service should return a
clean fallback instead of letting raw exceptions propagate.
"""
import pytest
from unittest.mock import patch, AsyncMock

from services.llm_client import chat_completion, get_llm_runtime_config
from services.http_client import ExternalTimeoutError


def test_llm_timeout_returns_fallback():
    """When the configured LLM times out, chat_completion returns a fallback string
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
        mock_settings.llm_provider = "qwen"
        mock_settings.llm_api_key = ""
        mock_settings.llm_base_url = ""
        mock_settings.qwen_api_key = ""
        mock_settings.qwen_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.qwen_model = "qwen-plus"
        mock_settings.dashscope_api_key = ""
        mock_settings.dashscope_base_url = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.deepseek_base_url = "https://api.deepseek.com"
        mock_settings.llm_model = "qwen-plus"

        result = asyncio.get_event_loop().run_until_complete(
            chat_completion("system", "user")
        )
        assert "LLM" in result or "未配置" in result
        assert "QWEN_API_KEY" in result or "DASHSCOPE_API_KEY" in result


def test_qwen_runtime_config_uses_dashscope_compatible_endpoint():
    with patch("services.llm_client.settings") as mock_settings:
        mock_settings.llm_provider = "qwen"
        mock_settings.llm_api_key = ""
        mock_settings.llm_base_url = ""
        mock_settings.qwen_api_key = "qwen-key"
        mock_settings.qwen_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.qwen_model = "qwen-plus"
        mock_settings.dashscope_api_key = ""
        mock_settings.dashscope_base_url = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.deepseek_base_url = "https://api.deepseek.com"
        mock_settings.llm_model = ""

        runtime = get_llm_runtime_config()

        assert runtime is not None
        assert runtime.service == "qwen"
        assert runtime.api_key == "qwen-key"
        assert runtime.base_url.endswith("/compatible-mode/v1")
        assert runtime.model == "qwen-plus"


def test_legacy_deepseek_fallback_does_not_reuse_qwen_default_model():
    with patch("services.llm_client.settings") as mock_settings:
        mock_settings.llm_provider = "qwen"
        mock_settings.llm_api_key = ""
        mock_settings.llm_base_url = ""
        mock_settings.qwen_api_key = ""
        mock_settings.qwen_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.qwen_model = "qwen-plus"
        mock_settings.dashscope_api_key = ""
        mock_settings.dashscope_base_url = ""
        mock_settings.deepseek_api_key = "legacy-key"
        mock_settings.deepseek_base_url = "https://api.deepseek.com"
        mock_settings.llm_model = "qwen-plus"

        runtime = get_llm_runtime_config()

        assert runtime is not None
        assert runtime.service == "deepseek"
        assert runtime.model == "deepseek-chat"
