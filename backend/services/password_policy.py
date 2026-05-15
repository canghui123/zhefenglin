"""注册/改密时的口令强度校验。

规则（MVP，可随合规要求逐步加强）：
- 长度 ≥ 10（与等保二级要求一致）
- 至少包含下列 3 类：大写字母 / 小写字母 / 数字 / 特殊字符
- 不在极简弱密黑名单中（常见 top-N）
- 不包含邮箱前缀 / display_name 作为子串（可选）
"""
from __future__ import annotations

import re
from typing import Optional


MIN_LENGTH = 10

# 非完整但覆盖常见弱密；线上可扩充为 10k+ 的 password file
_COMMON_WEAK = {
    "password",
    "passw0rd",
    "password1",
    "password123",
    "12345678",
    "123456789",
    "1234567890",
    "qwerty",
    "qwerty123",
    "abc123456",
    "admin",
    "admin123",
    "admin1234",
    "admin123!",
    "letmein",
    "welcome",
    "welcome1",
    "iloveyou",
    "passw0rd!",
    "p@ssw0rd",
    "p@ssword",
}


_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SYMBOL = re.compile(r"[^\w\s]")


class WeakPasswordError(ValueError):
    """表示密码未通过强度校验。"""


def validate_password_strength(
    password: str,
    *,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
) -> None:
    """校验失败抛 WeakPasswordError，成功静默返回。"""
    if not isinstance(password, str) or not password:
        raise WeakPasswordError("密码不能为空")

    if len(password) < MIN_LENGTH:
        raise WeakPasswordError(f"密码长度不能少于 {MIN_LENGTH} 位")

    classes = 0
    for pat in (_UPPER, _LOWER, _DIGIT, _SYMBOL):
        if pat.search(password):
            classes += 1
    if classes < 3:
        raise WeakPasswordError("密码需至少包含大写字母、小写字母、数字、符号中的 3 类")

    lowered = password.lower()
    if lowered in _COMMON_WEAK:
        raise WeakPasswordError("密码过于常见，请换一个")

    # 禁止把用户名前缀或显示名明文塞进密码
    if email:
        local = email.split("@", 1)[0].strip().lower()
        if local and len(local) >= 4 and local in lowered:
            raise WeakPasswordError("密码不能直接包含邮箱用户名")
    if display_name:
        dn = display_name.strip().lower()
        if dn and len(dn) >= 4 and dn in lowered:
            raise WeakPasswordError("密码不能直接包含显示名")
