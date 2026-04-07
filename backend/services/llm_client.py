"""DeepSeek LLM客户端封装"""

from openai import AsyncOpenAI
from config import settings


def get_llm_client() -> AsyncOpenAI:
    if not settings.deepseek_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """调用DeepSeek生成文本，无API Key时返回占位文本"""
    client = get_llm_client()
    if client is None:
        return "[LLM未配置] 请在.env中设置DEEPSEEK_API_KEY以启用AI功能。"

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
