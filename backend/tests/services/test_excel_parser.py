import os
import tempfile

import pandas as pd

from services.excel_parser import parse_excel


def _write_excel(df: pd.DataFrame) -> str:
    handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    handle.close()
    df.to_excel(handle.name, index=False)
    return handle.name


def test_parse_excel_supports_common_chinese_unit_formats():
    path = _write_excel(
        pd.DataFrame(
            [
                {
                    "车型": "2020 丰田凯美瑞 2.0G",
                    "欠款": "12.3万",
                    "买断价": "5万",
                    "里程": "8.6万公里",
                }
            ]
        )
    )
    try:
        result = parse_excel(path)
    finally:
        os.remove(path)

    assert result.success_rows == 1
    asset = result.assets[0]
    assert asset.loan_principal == 123000
    assert asset.buyout_price is None
    assert asset.mileage == 8.6
    assert result.suggested_strategy == "seller_transfer_analysis"


def test_parse_excel_does_not_treat_sale_price_columns_as_buyout_price():
    path = _write_excel(
        pd.DataFrame(
            [
                {
                    "车型": "2019 本田雅阁 260TURBO",
                    "挂牌价": "8.8万",
                }
            ]
        )
    )
    try:
        result = parse_excel(path)
    finally:
        os.remove(path)

    assert result.success_rows == 1
    assert result.assets[0].buyout_price is None
    assert result.suggested_strategy == "seller_transfer_analysis"


def test_parse_excel_ignores_legacy_buyout_price_columns():
    path = _write_excel(
        pd.DataFrame(
            [
                {
                    "车型": "2021 宝马3系 325Li",
                    "债权本金": 180000,
                    "买断价": 76000,
                    "转让价": 82000,
                }
            ]
        )
    )
    try:
        result = parse_excel(path)
    finally:
        os.remove(path)

    assert result.success_rows == 1
    assert "buyout_price" not in set(result.column_mapping.values())
    assert result.assets[0].loan_principal == 180000
    assert result.assets[0].buyout_price is None
