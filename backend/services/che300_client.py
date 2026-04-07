"""车300 API客户端 — VIN估值接口 + 正确签名算法"""

import hashlib
import time
import json
import random
from datetime import date
from typing import Optional

import httpx

from config import settings
from database import get_connection
from models.valuation import ValuationResult


def _generate_signature(business_params: dict, access_key: str, timestamp: str, secret_key: str) -> str:
    """车300签名算法（官方文档）：
    1. 参与签名的字段 = 业务参数 + access_key（不含debug/image_base64）
    2. 按参数名ASCII字典序升序排列，格式化为 key=value 用 & 相连
    3. 左边拼接timestamp，右边拼接secret_key
    4. MD5 32位小写
    """
    sign_params = dict(business_params)
    sign_params["access_key"] = access_key

    sorted_keys = sorted(sign_params.keys())
    param_str = "&".join(f"{k}={sign_params[k]}" for k in sorted_keys)

    sign_str = f"{timestamp}{param_str}{secret_key}"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def _check_cache(cache_key: str) -> Optional[ValuationResult]:
    """查询7天内的估值缓存"""
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM valuation_cache
           WHERE che300_model_id = ? AND created_at > datetime('now', '-7 days')
           ORDER BY created_at DESC LIMIT 1""",
        (cache_key,),
    ).fetchone()
    conn.close()
    if row:
        return ValuationResult(
            model_id=cache_key,
            model_name=row["city_code"] if row["city_code"] else "",
            excellent_price=row["excellent_price"],
            good_price=row["good_price"],
            medium_price=row["medium_price"],
            fair_price=row["fair_price"],
            dealer_buy_price=row["dealer_buy_price"],
            dealer_sell_price=row["dealer_sell_price"],
        )
    return None


def _save_cache(cache_key: str, result: ValuationResult, raw: str, model_name: str = ""):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO valuation_cache
           (che300_model_id, registration_date, query_date, city_code,
            excellent_price, good_price, medium_price, fair_price,
            dealer_buy_price, dealer_sell_price, raw_response)
           VALUES (?, date('now'), date('now'), ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            cache_key, model_name,
            result.excellent_price, result.good_price,
            result.medium_price, result.fair_price,
            result.dealer_buy_price, result.dealer_sell_price, raw,
        ),
    )
    conn.commit()
    conn.close()


async def get_valuation_by_vin(
    vin: str,
    city_name: Optional[str] = None,
    reg_date: Optional[str] = None,
    mile_age: Optional[float] = None,
) -> ValuationResult:
    """通过VIN码获取估值 — 自动选择真实API或Mock"""
    cache_key = f"vin_{vin}"

    cached = _check_cache(cache_key)
    if cached:
        return cached

    if settings.che300_access_key and settings.che300_access_secret:
        return await _real_vin_valuation(vin, city_name, reg_date, mile_age)
    else:
        return _mock_valuation(vin, reg_date or "2020-01")


async def _real_vin_valuation(
    vin: str,
    city_name: Optional[str],
    reg_date: Optional[str],
    mile_age: Optional[float],
) -> ValuationResult:
    """调用车300 VIN估值真实API"""
    timestamp = str(int(time.time() * 1000))  # 毫秒级时间戳

    # 业务参数（city_name是必传字段）
    if not city_name:
        city_name = settings.default_city_name
    business_params = {"vin": vin, "all_level": "1", "city_name": city_name}
    if reg_date:
        business_params["reg_date"] = reg_date
    if mile_age is not None:
        business_params["mile_age"] = str(mile_age)

    # 生成签名
    sn = _generate_signature(
        business_params,
        settings.che300_access_key,
        timestamp,
        settings.che300_access_secret,
    )

    # 完整请求参数
    post_data = dict(business_params)
    post_data["access_key"] = settings.che300_access_key
    post_data["timestamp"] = timestamp
    post_data["sn"] = sn

    url = f"{settings.che300_api_base}/open/v1/get-eval-price-by-vin"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            data=post_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != 2000:
        raise ValueError(f"车300 API错误 (code={data.get('code')}): {data.get('msg', '未知错误')}")

    result_list = data.get("data", {}).get("result", [])
    if not result_list:
        raise ValueError("车300 API返回空结果")

    # 取第一个匹配的车型
    car = result_list[0]
    model_name = f"{car.get('brand_name', '')} {car.get('series_name', '')} {car.get('model_name', '')}"

    # 解析估值（API返回单位为万元，转换为元）
    eval_prices = car.get("eval_result", [{}])

    # 从all_level=1的结果中提取各车况估值
    excellent = None
    good = None
    medium = None
    dealer_buy = None
    dealer_sell = None
    individual = None

    for ep in eval_prices:
        condition = ep.get("condition", "")
        price_data = ep.get("eval_price", {})

        if condition == "excellent" or (not condition and ep.get("is_default_condition") == 1):
            excellent = _wan_to_yuan(price_data.get("individual_price"))
        elif condition == "good":
            good = _wan_to_yuan(price_data.get("individual_price"))
        elif condition == "normal":
            medium = _wan_to_yuan(price_data.get("individual_price"))

        # 取默认车况的车商价
        if ep.get("is_default_condition") == 1 or not condition:
            dealer_buy = _wan_to_yuan(price_data.get("dealer_buy_price"))
            dealer_sell = _wan_to_yuan(price_data.get("dealer_price"))
            individual = _wan_to_yuan(price_data.get("individual_price"))

    # 如果没有分车况数据，用默认值
    if medium is None:
        medium = individual
    if excellent is None and medium:
        excellent = round(medium * 1.12, -2)
    if good is None and medium:
        good = round(medium * 1.06, -2)

    cache_key = f"vin_{vin}"
    result = ValuationResult(
        model_id=str(car.get("model_id", vin)),
        model_name=model_name.strip(),
        excellent_price=excellent,
        good_price=good,
        medium_price=medium,
        fair_price=round(medium * 0.85, -2) if medium else None,
        dealer_buy_price=dealer_buy,
        dealer_sell_price=dealer_sell,
    )

    _save_cache(cache_key, result, json.dumps(data, ensure_ascii=False), model_name)
    return result


def _wan_to_yuan(wan_price) -> Optional[float]:
    """万元转换为元"""
    if wan_price is None:
        return None
    try:
        return round(float(wan_price) * 10000, -2)
    except (ValueError, TypeError):
        return None


# ---- 兼容旧接口 ----

async def get_valuation(
    model_id: str,
    registration_date: str,
    mileage: Optional[float] = None,
    city_code: Optional[str] = None,
) -> ValuationResult:
    """兼容旧接口 — 如果model_id是VIN则用VIN接口，否则用Mock"""
    if len(model_id) == 17 and model_id.isalnum():
        return await get_valuation_by_vin(model_id, reg_date=registration_date, mile_age=mileage)

    cache_key = model_id
    cached = _check_cache(cache_key)
    if cached:
        return cached

    return _mock_valuation(model_id, registration_date)


def _mock_valuation(model_id: str, registration_date: str) -> ValuationResult:
    """Mock估值 — 基于上牌年份生成合理假数据"""
    try:
        reg_year = int(registration_date[:4])
    except (ValueError, IndexError):
        reg_year = 2020

    current_year = date.today().year
    age = max(current_year - reg_year, 0)

    base_price = 150000
    depreciation = base_price * (0.88 ** age)
    noise = random.uniform(0.92, 1.08)
    medium = round(depreciation * noise, -2)
    excellent = round(medium * 1.15, -2)
    good = round(medium * 1.08, -2)
    fair = round(medium * 0.85, -2)

    result = ValuationResult(
        model_id=model_id,
        model_name=f"Mock车型_{model_id}",
        excellent_price=excellent,
        good_price=good,
        medium_price=medium,
        fair_price=fair,
        dealer_buy_price=round(medium * 0.90, -2),
        dealer_sell_price=round(medium * 1.05, -2),
        is_mock=True,
    )
    _save_cache(model_id, result, '{"mock": true}')
    return result


async def batch_valuation(items: list[dict]) -> dict[int, ValuationResult]:
    """批量估值 — 优先使用VIN，回退到Mock"""
    results = {}
    for item in items:
        row_num = item["row_number"]
        vin = item.get("vin")
        model_id = item.get("model_id", "unknown")
        reg_date = item.get("registration_date", "2020-01")

        try:
            if vin and len(vin) == 17:
                val = await get_valuation_by_vin(vin, reg_date=reg_date)
            else:
                val = await get_valuation(model_id, reg_date)
            results[row_num] = val
        except Exception as e:
            results[row_num] = ValuationResult(
                model_id=vin or model_id,
                model_name=f"估值失败: {str(e)}",
                is_mock=True,
            )
    return results
