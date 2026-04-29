"""OpenAI-compatible LLM client.

Production defaults to Qwen/DashScope so all AI-assisted analysis goes through
the same model gateway.  Legacy DeepSeek variables remain supported to avoid
breaking older deployments while operations rotate credentials.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI
from config import settings
from services.metrics import EXTERNAL_API_CALLS, EXTERNAL_API_LATENCY

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRuntimeConfig:
    service: str
    api_key: str
    base_url: str
    model: str


QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _configured_provider() -> str:
    return (settings.llm_provider or "qwen").strip().lower()


def _model_for(service: str) -> str:
    configured = (settings.llm_model or "").strip()
    if service == "qwen":
        return configured or settings.qwen_model or "qwen-plus"
    # `LLM_MODEL` defaults to qwen-plus for new deployments, so avoid passing
    # that Qwen model name to the legacy DeepSeek fallback by accident.
    if configured and configured != "qwen-plus":
        return configured
    return "deepseek-chat"


def _qwen_base_url() -> str:
    # Prefer the explicit DashScope alias if operators set it; otherwise keep
    # the canonical Qwen variable and final hard-coded default.
    return (settings.dashscope_base_url or settings.qwen_base_url or QWEN_BASE_URL).strip()


def get_llm_runtime_config() -> Optional[LLMRuntimeConfig]:
    """Resolve LLM config with Qwen first and legacy DeepSeek fallback."""
    generic_key = (settings.llm_api_key or "").strip()
    generic_base = (settings.llm_base_url or "").strip()
    provider = _configured_provider()

    if generic_key:
        service = provider or "llm"
        default_base = QWEN_BASE_URL if service == "qwen" else settings.deepseek_base_url
        return LLMRuntimeConfig(
            service=service,
            api_key=generic_key,
            base_url=generic_base or default_base,
            model=_model_for(service),
        )

    qwen_key = (settings.qwen_api_key or settings.dashscope_api_key or "").strip()
    if provider == "qwen" and qwen_key:
        return LLMRuntimeConfig(
            service="qwen",
            api_key=qwen_key,
            base_url=_qwen_base_url(),
            model=_model_for("qwen"),
        )

    # Backward compatibility: existing servers may still only have DEEPSEEK_*.
    if settings.deepseek_api_key:
        return LLMRuntimeConfig(
            service="deepseek",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=_model_for("deepseek"),
        )

    if qwen_key:
        return LLMRuntimeConfig(
            service="qwen",
            api_key=qwen_key,
            base_url=_qwen_base_url(),
            model=_model_for("qwen"),
        )

    return None


def get_llm_client() -> Optional[AsyncOpenAI]:
    runtime = get_llm_runtime_config()
    if runtime is None:
        return None
    return AsyncOpenAI(
        api_key=runtime.api_key,
        base_url=runtime.base_url,
        timeout=30,
    )


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """Generate text through the configured LLM, falling back gracefully."""
    runtime = get_llm_runtime_config()
    client = get_llm_client()
    if client is None or runtime is None:
        return "[LLM未配置] 请设置 QWEN_API_KEY 或 DASHSCOPE_API_KEY 以启用千问AI分析。"

    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=runtime.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed = time.monotonic() - start
        EXTERNAL_API_LATENCY.labels(service=runtime.service).observe(elapsed)
        EXTERNAL_API_CALLS.labels(service=runtime.service, status="success").inc()
        return response.choices[0].message.content
    except Exception as exc:
        elapsed = time.monotonic() - start
        EXTERNAL_API_LATENCY.labels(service=runtime.service).observe(elapsed)
        EXTERNAL_API_CALLS.labels(service=runtime.service, status="error").inc()
        logger.warning("LLM调用失败: %s", exc)
        return "[LLM调用失败] 服务暂时不可用，请稍后重试。"
