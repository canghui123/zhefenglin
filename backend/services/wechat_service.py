"""微信小程序登录:code2session。

两种模式(由 settings.wechat_login_mode 控制):
- "mock"  (默认/开发): 不打微信 API,直接用 code 派生一个稳定的 openid,
  让小程序联调和自动化测试在没有商户资质时也能跑通全链路。
- "real"  : 调微信 jscode2session,需要 wechat_appid + wechat_secret。

返回 {"openid": str, "unionid": Optional[str]}。
"""
from __future__ import annotations

import hashlib
from typing import Optional

import httpx

from config import settings


class WeChatError(Exception):
    """微信登录失败(code 无效 / 配置缺失 / 接口异常)。"""


_JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


def code_to_session(code: str) -> dict:
    if not code:
        raise WeChatError("缺少 code")

    mode = getattr(settings, "wechat_login_mode", "mock")
    if mode == "mock":
        # 稳定派生:同一个 code 永远映射到同一个 openid,方便联调/测试复用账号
        digest = hashlib.sha256(f"mock-openid:{code}".encode("utf-8")).hexdigest()
        return {"openid": f"mock_{digest[:24]}", "unionid": None}

    appid = getattr(settings, "wechat_appid", "")
    secret = getattr(settings, "wechat_secret", "")
    if not appid or not secret:
        raise WeChatError("real 模式需要配置 wechat_appid / wechat_secret")

    try:
        resp = httpx.get(
            _JSCODE2SESSION_URL,
            params={
                "appid": appid,
                "secret": secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise WeChatError(f"微信接口调用失败: {exc}") from exc

    if data.get("errcode"):
        raise WeChatError(f"微信登录失败: {data.get('errmsg')} (errcode={data.get('errcode')})")

    openid = data.get("openid")
    if not openid:
        raise WeChatError("微信未返回 openid")
    return {"openid": openid, "unionid": data.get("unionid")}
