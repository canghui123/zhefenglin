"""DeepSeek LLM客户端封装"""
from __future__ import annotations

import logging
import time

from openai import AsyncOpenAI
from config import settings
from services.metrics import EXTERNAL_API_CALLS, EXTERNAL_API_LATENCY

logger = logging.getLogger(__name__)


def get_llm_client() -> AsyncOpenAI:
    if not settings.deepseek_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=30,
    )


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """调用DeepSeek生成文本，无API Key时返回占位文本，异常时返回降级文本"""
    client = get_llm_client()
    if client is None:
        return "[LLM未配置] 请在.env中设置DEEPSEEK_API_KEY以启用AI功能。"

    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model or "qwen-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed = time.monotonic() - start
        EXTERNAL_API_LATENCY.labels(service="deepseek").observe(elapsed)
        EXTERNAL_API_CALLS.labels(service="deepseek", status="success").inc()
        return response.choices[0].message.content
    except Exception as exc:
        elapsed = time.monotonic() - start
        EXTERNAL_API_LATENCY.labels(service="deepseek").observe(elapsed)
        EXTERNAL_API_CALLS.labels(service="deepseek", status="error").inc()
        logger.warning("LLM调用失败: %s", exc)
        return "[LLM调用失败] 服务暂时不可用，请稍后重试。"
