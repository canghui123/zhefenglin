"""B5 task — CHE300 模式开关回归测试。

之前判断逻辑:
    if settings.che300_access_key and settings.che300_access_secret:
        走真 API
    else:
        走 mock

历史问题:`disabled_for_demo` 这种占位符是非空字符串,会被误判为"有 key",
然后真的去调车300 API → 必然失败 → 估值覆盖率 0% → 演示翻车。

本次改造:用显式 `che300_mode` 开关 + 占位符白名单。
本测试覆盖:
- mode="mock" 时无论 key 怎么设都走 mock
- mode="real" 时无论 key 怎么设都尝试真 API
- mode="auto"(默认)时:
    - 空 key → mock
    - 占位符 key("disabled_for_demo" 等)→ mock
    - 真实 key → 真 API
"""

from unittest.mock import patch

from services.che300_client import (
    _CHE300_MOCK_PLACEHOLDER_KEYS,
    _should_use_real_che300_api,
)


def _patch_settings(mode="auto", key="", secret=""):
    """构造一个 settings 上下文管理器,统一替换 mode/key/secret。"""
    def _build(stack):
        s = stack.enter_context(patch("services.che300_client.settings"))
        s.che300_mode = mode
        s.che300_access_key = key
        s.che300_access_secret = secret
        return s
    return _build


def test_mock_mode_always_uses_mock():
    """mode=mock 即使有合法 key 也走 mock。"""
    with patch("services.che300_client.settings") as s:
        s.che300_mode = "mock"
        s.che300_access_key = "real_che300_production_key_2026"
        s.che300_access_secret = "real_secret"
        assert _should_use_real_che300_api() is False


def test_real_mode_always_uses_real_api():
    """mode=real 即使 key 为空也尝试真 API(让 API 自己返回明确错误,不静默 fallback)。"""
    with patch("services.che300_client.settings") as s:
        s.che300_mode = "real"
        s.che300_access_key = ""
        s.che300_access_secret = ""
        assert _should_use_real_che300_api() is True


def test_auto_mode_empty_key_falls_back_to_mock():
    """auto + 空 key → mock(向后兼容老行为)。"""
    with patch("services.che300_client.settings") as s:
        s.che300_mode = "auto"
        s.che300_access_key = ""
        s.che300_access_secret = ""
        assert _should_use_real_che300_api() is False


def test_auto_mode_disabled_for_demo_placeholder_is_recognized_as_mock():
    """auto + disabled_for_demo 占位符 → mock(本次修复的核心场景)。"""
    with patch("services.che300_client.settings") as s:
        s.che300_mode = "auto"
        s.che300_access_key = "disabled_for_demo"
        s.che300_access_secret = "disabled_for_demo"
        assert _should_use_real_che300_api() is False, (
            "disabled_for_demo 是已知占位符,必须走 mock,不能去调真车300 API"
        )


def test_auto_mode_placeholder_keys_all_recognized():
    """所有 _CHE300_MOCK_PLACEHOLDER_KEYS 里的值都应走 mock。"""
    for placeholder in _CHE300_MOCK_PLACEHOLDER_KEYS:
        with patch("services.che300_client.settings") as s:
            s.che300_mode = "auto"
            s.che300_access_key = placeholder
            s.che300_access_secret = "any_secret_non_empty"
            assert _should_use_real_che300_api() is False, (
                f"占位符 {placeholder!r} 应被识别为 mock,但实际判定为 real"
            )


def test_auto_mode_real_key_uses_real_api():
    """auto + 真实合法 key → 真 API。"""
    with patch("services.che300_client.settings") as s:
        s.che300_mode = "auto"
        s.che300_access_key = "wEdHkfL9q3pZc7KvNxM2"  # 看起来像真 key
        s.che300_access_secret = "j8B7K2pQwE5dT3yN6mZ1xL4cR9vH"
        assert _should_use_real_che300_api() is True


def test_auto_mode_uppercase_placeholder_still_recognized():
    """大小写不敏感:DISABLED_FOR_DEMO 也应识别为占位符。"""
    with patch("services.che300_client.settings") as s:
        s.che300_mode = "auto"
        s.che300_access_key = "DISABLED_FOR_DEMO"
        s.che300_access_secret = "any"
        assert _should_use_real_che300_api() is False


def test_auto_mode_whitespace_in_key_handled():
    """key 带空格的边缘 case:strip 后判断。"""
    with patch("services.che300_client.settings") as s:
        s.che300_mode = "auto"
        s.che300_access_key = "  disabled_for_demo  "
        s.che300_access_secret = "  any_secret  "
        assert _should_use_real_che300_api() is False


def test_che300_mode_missing_attr_defaults_to_auto():
    """老配置文件可能没有 che300_mode 字段,getattr fallback 到 auto。"""
    with patch("services.che300_client.settings") as s:
        # 不设 che300_mode 属性,模拟老配置
        del s.che300_mode  # type: ignore
        s.che300_access_key = "disabled_for_demo"
        s.che300_access_secret = "disabled_for_demo"
        # auto + disabled_for_demo → mock
        assert _should_use_real_che300_api() is False
