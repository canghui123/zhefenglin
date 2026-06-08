"""B6 — Data masking PII regex scanner tests.

Coverage:
- VIN inside free text gets masked but innocuous 17-char strings near
  word boundaries are protected by the alphabet (I/O/Q excluded).
- Chinese mobile numbers (1[3-9]xxxxxxxx) get masked, but adjacent
  digits don't extend the match.
- Chinese national ID (18-digit, last X) gets masked.
- Email gets masked but version strings like `version@1.2.3` are not
  accidentally treated as emails (TLD must be alpha).
- Mixed text gets all PII types masked in one pass.
- mask_sensitive_payload combines field-name + content scanning.
- mask_sensitive_payload(..., redact_text=False) skips content scan
  for callers that already trust the strings.
"""

from __future__ import annotations

from services.data_masking import (
    _redact_pii_in_text,
    mask_sensitive_payload,
)


# ── VIN ──────────────────────────────────────────────────────────────

def test_vin_inside_free_text_is_masked():
    text = "车辆 VIN LSVCD23F4N1234567 已收车"
    out = _redact_pii_in_text(text)
    assert "LSVCD23F4N1234567" not in out
    # 前 3 + 后 3 保留
    assert "LSV" in out and "567" in out
    assert "*" in out


def test_vin_with_iniq_not_treated_as_vin():
    # VIN 不应含 I/O/Q, 含 I 的 17 位字符串不该被脱敏成 VIN
    text = "commit IIIIIIIIIIIIIIIII passed"
    out = _redact_pii_in_text(text)
    assert "IIIIIIIIIIIIIIIII" in out  # 不被识别为 VIN


def test_multiple_vins_in_one_string():
    text = "车 A VIN LSVCD23F4N1234567 / 车 B VIN LFVDE56G8H9876543"
    out = _redact_pii_in_text(text)
    assert "LSVCD23F4N1234567" not in out
    assert "LFVDE56G8H9876543" not in out
    assert out.count("LSV") == 1
    assert out.count("LFV") == 1


# ── 手机号 ─────────────────────────────────────────────────────────

def test_chinese_mobile_in_text_is_masked():
    text = "请联系 13800138000 处理"
    out = _redact_pii_in_text(text)
    assert "13800138000" not in out
    assert "138" in out and "8000" in out
    assert "****" in out


def test_mobile_adjacent_digits_dont_extend_match():
    # 数字串前后有别的数字时不应该错切
    text = "订单号 991380013800020"
    out = _redact_pii_in_text(text)
    # 这个 15 位串里嵌着 13800138000 但前后有非边界数字, 不该掩
    assert "13800138000" in out or "138001380" in out


def test_non_chinese_mobile_not_treated_as_mobile():
    # 11 位但不是 1[3-9] 开头, 不该被识别
    text = "ZIP 02134567890 area"
    out = _redact_pii_in_text(text)
    assert "02134567890" in out


# ── 身份证 ─────────────────────────────────────────────────────────

def test_id_card_18_digit_is_masked():
    text = "身份证 110101199001011234 备案"
    out = _redact_pii_in_text(text)
    assert "110101199001011234" not in out
    assert "110" in out and "1234" in out


def test_id_card_ending_with_x_is_masked():
    text = "身份证 11010119900101123X 备案"
    out = _redact_pii_in_text(text)
    assert "11010119900101123X" not in out
    assert "123X" in out  # 后 4 含 X 保留


# ── 邮箱 ───────────────────────────────────────────────────────────

def test_email_in_text_is_masked():
    text = "联系人 john.doe@example.com 已通知"
    out = _redact_pii_in_text(text)
    assert "john.doe@example.com" not in out
    assert "@example.com" in out  # 域名保留
    assert "j***" in out  # 邮箱本地首字母 + ***


def test_version_string_with_at_sign_not_treated_as_email():
    # `version@1.2.3` TLD 是数字, 不应识别为邮箱
    text = "use package version@1.2.3 fixed"
    out = _redact_pii_in_text(text)
    assert "version@1.2.3" in out  # 不被脱敏


# ── 混排 ────────────────────────────────────────────────────────────

def test_mixed_pii_all_redacted_in_one_pass():
    text = "客户 zhang@aaa.com 手机 13900139000 VIN LSVCD23F4N1234567 身份证 110101199001011234"
    out = _redact_pii_in_text(text)
    assert "zhang@aaa.com" not in out
    assert "13900139000" not in out
    assert "LSVCD23F4N1234567" not in out
    assert "110101199001011234" not in out


# ── mask_sensitive_payload combined ─────────────────────────────────

def test_payload_field_name_and_content_both_masked():
    """Field name 命中(vin) + Value 内含其他 PII, 两者都被处理。"""
    payload = {
        "vin": "LSVCD23F4N1234567",  # field name 命中, 走 _mask_string
        "description": "联系车主 13800138000 准备拖车",  # field name 不含敏感词, 走 PII 正则
    }
    masked = mask_sensitive_payload(payload)
    # vin 字段:legacy mask_string("LSV" + "*" + "4567")
    assert masked["vin"] != "LSVCD23F4N1234567"
    assert masked["vin"].startswith("LSV") and masked["vin"].endswith("4567")
    # description 字段:正则识别 PII
    assert "13800138000" not in masked["description"]
    assert "138" in masked["description"] and "8000" in masked["description"]


def test_payload_redact_text_false_skips_content_scan():
    payload = {"description": "联系 13800138000"}
    out = mask_sensitive_payload(payload, redact_text=False)
    # redact_text=False 不扫文本, 手机号原样保留
    assert "13800138000" in out["description"]


def test_payload_recursive_into_list_and_dict():
    payload = {
        "sections": [
            {"heading": "车主信息", "body": "VIN LSVCD23F4N1234567"},
            {"heading": "联系方式", "body": "手机 13800138000"},
        ]
    }
    masked = mask_sensitive_payload(payload)
    body0 = masked["sections"][0]["body"]
    body1 = masked["sections"][1]["body"]
    assert "LSVCD23F4N1234567" not in body0
    assert "13800138000" not in body1


def test_payload_non_string_values_preserved():
    payload = {
        "count": 42,
        "ratio": 0.85,
        "flag": True,
        "nothing": None,
        "tags": ["risk", "high"],
    }
    masked = mask_sensitive_payload(payload)
    assert masked["count"] == 42
    assert masked["ratio"] == 0.85
    assert masked["flag"] is True
    assert masked["nothing"] is None
    assert masked["tags"] == ["risk", "high"]
