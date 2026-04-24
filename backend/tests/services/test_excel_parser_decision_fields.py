import pandas as pd

from services.excel_parser import parse_excel


def test_excel_parser_detects_province_and_city_columns(tmp_path):
    path = tmp_path / "assets.xlsx"
    pd.DataFrame(
        [
            {
                "车辆描述": "2021 丰田 凯美瑞",
                "省份": "江苏省",
                "所在城市": "南京市",
                "买断价": "12.3万元",
            }
        ]
    ).to_excel(path, index=False)

    result = parse_excel(str(path))

    assert result.success_rows == 1
    asset = result.assets[0]
    assert asset.province == "江苏省"
    assert asset.city == "南京市"
    assert asset.buyout_price == 123000


def test_excel_parser_can_derive_region_from_location_column(tmp_path):
    path = tmp_path / "assets.xlsx"
    pd.DataFrame(
        [
            {
                "车辆描述": "2022 比亚迪 汉EV",
                "资产所在地": "广东省 深圳市",
                "买断价": "18万",
            }
        ]
    ).to_excel(path, index=False)

    result = parse_excel(str(path))

    asset = result.assets[0]
    assert asset.province == "广东省"
    assert asset.city == "深圳市"
    assert asset.buyout_price == 180000
