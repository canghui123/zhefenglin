"""DeepSeek LLM客户端封装"""
from __future__ import annotations

import logging
import time
from typing import Optional

from openai import AsyncOpenAI
from config import settings
from services import commercial_policy_service, cost_metering_service
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


def _llm_unit_cost(model_name: str) -> float:
    model = (model_name or "").lower()
    if "turbo" in model:
        return settings.llm_turbo_unit_cost
    if "long" in model:
        return settings.llm_long_unit_cost
    return settings.llm_plus_unit_cost


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    session=None,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
    module: str = "system",
    task_type: str = "medium_task",
    request_id: Optional[str] = None,
    single_task_budget: Optional[float] = None,
) -> str:
    """调用DeepSeek生成文本，无API Key时返回占位文本，异常时返回降级文本"""
    route = None
    degraded = False
    degrade_reason = None
    if session is not None and tenant_id is not None:
        policy = commercial_policy_service.preflight_llm_task(
            session,
            tenant_id=tenant_id,
            task_type=task_type,
            single_task_budget=single_task_budget,
        )
        route = policy["route"]
        degraded = bool(policy.get("degraded"))
        degrade_reason = policy.get("reason")
        if policy.get("use_template_fallback"):
            fallback = "[LLM额度受限] 已回退为模板化输出，请升级套餐或联系管理员调整预算。"
            cost_metering_service.record_usage(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                module=module,
                action="llm_completion",
                resource_type="ai_report",
                quantity=1,
                unit_cost_internal=0,
                unit_price_external=0,
                request_id=request_id,
                metadata={
                    "task_type": task_type,
                    "model": route["preferred_model"],
                    "degraded": True,
                    "reason": degrade_reason,
                    "template_fallback": True,
                },
            )
            return fallback

    client = get_llm_client()
    if client is None:
        placeholder = "[LLM未配置] 请在.env中设置DEEPSEEK_API_KEY以启用AI功能。"
        if session is not None and tenant_id is not None:
            cost_metering_service.record_usage(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                module=module,
                action="llm_completion",
                resource_type="ai_report",
                quantity=1,
                unit_cost_internal=0,
                unit_price_external=0,
                request_id=request_id,
                metadata={
                    "task_type": task_type,
                    "model": route["preferred_model"] if route else settings.llm_model or "qwen-plus",
                    "degraded": degraded,
                    "reason": "llm_not_configured",
                    "template_fallback": True,
                },
            )
        return placeholder

    selected_model = route["preferred_model"] if route else settings.llm_model or "qwen-plus"
    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=selected_model,
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
        content = response.choices[0].message.content
        if session is not None and tenant_id is not None:
            usage = getattr(response, "usage", None)
            cost_metering_service.record_usage(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                module=module,
                action="llm_completion",
                resource_type="ai_report",
                quantity=1,
                unit_cost_internal=_llm_unit_cost(selected_model),
                unit_price_external=0,
                request_id=request_id,
                metadata={
                    "task_type": task_type,
                    "model": selected_model,
                    "degraded": degraded,
                    "reason": degrade_reason,
                },
                extra_snapshot_metrics={
                    "llm_input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                    "llm_output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                    "llm_cost": _llm_unit_cost(selected_model),
                },
            )
        return content
    except Exception as exc:
        elapsed = time.monotonic() - start
        EXTERNAL_API_LATENCY.labels(service="deepseek").observe(elapsed)
        EXTERNAL_API_CALLS.labels(service="deepseek", status="error").inc()
        logger.warning("LLM调用失败: %s", exc)
        fallback = "[LLM调用失败] 服务暂时不可用，请稍后重试。"
        if session is not None and tenant_id is not None:
            cost_metering_service.record_usage(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                module=module,
                action="llm_completion",
                resource_type="ai_report",
                quantity=1,
                unit_cost_internal=0,
                unit_price_external=0,
                request_id=request_id,
                metadata={
                    "task_type": task_type,
                    "model": selected_model,
                    "degraded": True,
                    "reason": str(exc),
                    "template_fallback": True,
                },
            )
        return fallback
