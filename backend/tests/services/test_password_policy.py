import pytest

from services.password_policy import (
    WeakPasswordError,
    validate_password_strength,
)


def test_password_policy_accepts_strong_password():
    validate_password_strength("Str0ng!Passw0rd")


def test_password_policy_rejects_too_short():
    with pytest.raises(WeakPasswordError):
        validate_password_strength("Aa1!xyz")


def test_password_policy_rejects_one_class_only():
    with pytest.raises(WeakPasswordError):
        validate_password_strength("aaaaaaaaaaaaa")  # 14 chars, single class


def test_password_policy_rejects_common_weak():
    with pytest.raises(WeakPasswordError):
        validate_password_strength("Password123")  # 11 chars but too common prefix
    with pytest.raises(WeakPasswordError):
        validate_password_strength("Admin123!")  # common


def test_password_policy_rejects_email_prefix_in_password():
    with pytest.raises(WeakPasswordError):
        validate_password_strength(
            "Alice1!secret", email="alice@example.com"
        )


def test_password_policy_allows_three_of_four_classes():
    # 只有大小写+符号，没有数字 —— 3 类，通过
    validate_password_strength("StrongSecret!")
