"""LLM贬值预测服务 — 通过统一千问优先 LLM 网关驱动"""

import json
import re
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from repositories import valuation_repo
from services.llm_client import chat_completion


SYSTEM_PROMPT = """你是一个二手车市场分析专家。根据提供的车型信息，预测其未来30天、60天、90天的贬值率。

请严格按以下JSON格式返回（不要添加其他文字）：
{
  "predictions": [
    {
      "car_description": "车型名称",
      "depreciation_30d": 0.02,
      "depreciation_60d": 0.04,
      "depreciation_90d": 0.07,
      "liquidity_score": "高/中/低",
      "reasoning": "简要说明"
    }
  ]
}

贬值率为小数，如0.02表示2%。参考规律：
- 豪华品牌(BBA)首年贬值20-25%，之后每年10-15%
- 日系车(丰田/本田)保值率最好，年贬值8-10%
- 国产车贬值较快，年贬值15-20%
- 新能源车贬值最快，年贬值20-30%
- 冷门车型流动性差，贬值更快
"""


def _check_cache(session: Session, model_name: str) -> Optional[dict]:
    return valuation_repo.get_fresh_depreciation(session, model_name)


def _save_cache(session: Session, model_name: str, valuation: float, prediction: dict):
    valuation_repo.save_depreciation(session, model_name, valuation, prediction)


def _parse_llm_response(text: str) -> list[dict]:
    """从LLM返回中提取JSON"""
    # 尝试直接解析
    try:
        data = json.loads(text)
        return data.get("predictions", [data] if "depreciation_30d" in data else [])
    except json.JSONDecodeError:
        pass

    # 尝试提取代码块中的JSON
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get("predictions", [data] if "depreciation_30d" in data else [])
        except json.JSONDecodeError:
            pass

    # 尝试提取花括号
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            data = json.loads(match.group())
            return data.get("predictions", [data] if "depreciation_30d" in data else [])
        except json.JSONDecodeError:
            pass

    return []


async def predict_depreciation(
    session: Session,
    cars: list[dict],
) -> dict[int, float]:
    """批量预测贬值率

    Args:
        cars: [{"row_number": int, "car_description": str, "valuation": float, "reg_year": int}]

    Returns:
        {row_number: 预期贬值率(处置周期内)}
    """
    results = {}
    uncached = []

    # 检查缓存
    for car in cars:
        cached = _check_cache(session, car["car_description"])
        if cached:
            results[car["row_number"]] = cached.get("depreciation_30d", 0.02)
        else:
            uncached.append(car)

    if not uncached:
        return results

    # 构建LLM请求
    car_list_text = "\n".join(
        f"- {c['car_description']}，车龄{date.today().year - c.get('reg_year', 2020)}年，"
        f"当前估值{c.get('valuation', 0):.0f}元"
        for c in uncached
    )

    user_prompt = f"请预测以下{len(uncached)}台车的贬值趋势：\n{car_list_text}"

    response = await chat_completion(SYSTEM_PROMPT, user_prompt)
    predictions = _parse_llm_response(response)

    # 匹配结果
    for i, car in enumerate(uncached):
        if i < len(predictions):
            pred = predictions[i]
            dep_rate = pred.get("depreciation_30d", 0.02)
            _save_cache(session, car["car_description"], car.get("valuation", 0), pred)
        else:
            # LLM返回不足时用默认值
            dep_rate = _default_depreciation(car.get("reg_year", 2020))

        results[car["row_number"]] = dep_rate

    return results


def _default_depreciation(reg_year: int) -> float:
    """默认贬值率（无LLM时的兜底）"""
    age = date.today().year - reg_year
    if age <= 1:
        return 0.03
    elif age <= 3:
        return 0.02
    elif age <= 5:
        return 0.015
    else:
        return 0.01
