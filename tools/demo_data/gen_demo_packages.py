"""生成两份演示用资产包 Excel。

输出:
- demo_standard_package.xlsx  (30 台, 18 燃油 + 12 新能源, 数据齐全, 风险低)
- demo_risky_package.xlsx     (30 台, 18 燃油 + 12 新能源, 6 类风险叠加)

设计原则:
- 固定 seed, reproducible
- VIN 用 DEMO 开头, 不冲突真实 VIN 体系
- 数值贴近 2025 不良车贷处置市场典型本金 / 里程 / 残值
- 字段列名与 backend/services/excel_parser.py COLUMN_KEYWORDS 对齐
- 不放销售侧价格列 (挂牌价/拍卖价/底价) —— parser 不识别, 也避免误导

跑法:
  python3 tools/demo_data/gen_demo_packages.py
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

import pandas as pd


OUTPUT_DIR = Path(__file__).parent
SEED_STANDARD = 42
SEED_RISKY = 4242


# 燃油车型 (车型描述, 上牌年份范围, 本金基准万元)
FUEL_VEHICLES: list[tuple[str, tuple[int, int], float]] = [
    ("丰田凯美瑞 2.0G 豪华版",          (2018, 2022), 14),
    ("本田雅阁 1.5T 精英版",            (2019, 2022), 15),
    ("大众帕萨特 330TSI 精英版",        (2018, 2021), 12),
    ("奥迪 A4L 40 TFSI 时尚动感",       (2019, 2022), 22),
    ("宝马 320Li 时尚运动版",           (2019, 2022), 24),
    ("别克君越 GS 28T",                 (2018, 2021), 13),
    ("雪佛兰迈锐宝 530T 锐界版",        (2018, 2020), 10),
    ("福特蒙迪欧 EcoBoost 245",         (2018, 2021), 11),
    ("哈弗 H6 1.5T 自动智尊型",         (2019, 2022), 9),
    ("长安 CS75 PLUS 1.5T 智尚版",      (2019, 2022), 9),
    ("吉利博越 PRO 1.8T 智享型",        (2019, 2022), 8),
    ("奇瑞瑞虎 8 PLUS 1.6T",            (2020, 2022), 9),
    ("广汽传祺 GS4 270T 豪华版",        (2018, 2021), 7),
    ("领克 03 1.5T 劲驾版",             (2020, 2022), 14),
    ("丰田汉兰达 2.0T 四驱豪华",        (2019, 2022), 26),
    ("本田 CR-V 1.5T 净享版",           (2019, 2022), 18),
    ("日产天籁 2.0L 智联豪华版",        (2018, 2021), 15),
    ("马自达阿特兹 2.5L 蓝天豪华版",    (2018, 2020), 16),
]
assert len(FUEL_VEHICLES) == 18

# 新能源车型 (车型描述, 上牌年份范围, 本金基准万元, 标称续航 km, 能源类型 zh)
NEW_ENERGY_VEHICLES: list[tuple[str, tuple[int, int], float, int, str]] = [
    ("比亚迪汉 EV 创世版",                  (2021, 2023), 19, 605,  "纯电"),
    ("比亚迪海豚 时尚版",                   (2022, 2023), 11, 405,  "纯电"),
    ("比亚迪秦 PLUS DM-i 120KM 旗舰版",     (2022, 2023), 13, 1200, "插混"),
    ("比亚迪宋 PLUS EV 旗舰版",             (2021, 2023), 17, 505,  "纯电"),
    ("特斯拉 Model 3 标准续航后驱版",       (2021, 2023), 22, 468,  "纯电"),
    ("特斯拉 Model Y 长续航全轮驱动版",     (2021, 2023), 30, 615,  "纯电"),
    ("蔚来 ES6 75kWh",                      (2020, 2022), 32, 420,  "纯电"),
    ("蔚来 ET5 75kWh",                      (2022, 2023), 35, 550,  "纯电"),
    ("理想 ONE 增程式",                     (2020, 2022), 28, 1080, "增程"),
    ("问界 M5 增程版",                      (2022, 2023), 27, 1195, "增程"),
    ("哪吒 U 智享版",                       (2021, 2023), 13, 500,  "纯电"),
    ("小鹏 P7 鹏翼版",                      (2021, 2023), 25, 670,  "纯电"),
]
assert len(NEW_ENERGY_VEHICLES) == 12


VIN_CHARS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"  # 排除 I/O/Q 同真实 VIN 规则


def gen_vin() -> str:
    """生成 17 位 DEMO 开头的伪 VIN，结构合规但永不与真实 VIN 冲突。"""
    suffix = "".join(random.choices(VIN_CHARS, k=13))
    return f"DEMO{suffix}"


def gen_first_reg(year_range: tuple[int, int]) -> str:
    """上牌日期，格式 YYYY-MM-DD（parser 支持）。"""
    year = random.randint(*year_range)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def gen_mileage_wankm(year_range: tuple[int, int]) -> str:
    """里程按年限走，大概 1.5-2.8 万公里/年。返回中文单位字符串。"""
    year = random.randint(*year_range)
    years_elapsed = max(1, 2026 - year)
    base = years_elapsed * 1.9
    jitter = random.uniform(-0.4, 0.9)
    km = max(1.5, base + jitter)
    return f"{km:.1f}万公里"


def gen_principal_wan(base_wan: float, jitter_pct: float = 0.22) -> str:
    """债权本金，万元为单位，jitter 给真实感。"""
    jitter = random.uniform(1 - jitter_pct, 1 + jitter_pct)
    val = round(base_wan * jitter, 1)
    return f"{val}万"


def _bool_zh(prob_true: float) -> str:
    """按概率给 是/否。"""
    return "是" if random.random() < prob_true else "否"


def _gen_overdue_in_storage(profile: str) -> tuple[int, str, int]:
    """生成 (逾期天数, 是否在库, 在库天数)。profile=standard|risky。

    标准包:多数刚进入处置流程(逾期 90-200 天, 在库 < 30 天)
    问题包:大量长期未处置(逾期 300-700 天, 部分长期在库, 部分根本没收车)
    """
    if profile == "standard":
        overdue = random.choice([90, 120, 150, 180, 210, 240, 270, 300])
        in_storage = random.random() < 0.65   # 65% 已收车
        days_stored = random.randint(3, 35) if in_storage else 0
    else:  # risky
        overdue = random.choice([300, 360, 420, 510, 600, 700, 800, 950, 1100])
        in_storage = random.random() < 0.55   # 55% 已收车（更多未收车）
        days_stored = random.randint(30, 220) if in_storage else 0
    return overdue, "是" if in_storage else "否", days_stored


def gen_standard_package() -> pd.DataFrame:
    """标准包：30 台车，字段齐全，GPS 大部分在线，风险显著低。"""
    random.seed(SEED_STANDARD)
    rows: list[dict] = []

    # 18 台燃油
    for car, year_range, base in FUEL_VEHICLES:
        overdue, in_stor, stored = _gen_overdue_in_storage("standard")
        rows.append({
            "车型":            car,
            "VIN码":           gen_vin(),
            "首次登记日期":    gen_first_reg(year_range),
            "里程":            gen_mileage_wankm(year_range),
            "GPS状态":         "在线" if random.random() < 0.88 else "离线",
            "是否脱保":        _bool_zh(0.08),  # 92% 未脱保
            "是否过户":        _bool_zh(0.05),  # 95% 权属未转
            "债权本金(元)":    gen_principal_wan(base),
            "逾期天数":        overdue,
            "是否在库":        in_stor,
            "在库天数":        stored,
            "能源类型":        "燃油",
            "是否运营车":      _bool_zh(0.05),
            # 新能源专属字段留空, 燃油车不需要
            "电池SOH(%)":      None,
            "三电质保":        None,
            "续航里程(km)":    None,
            "是否网约车":      None,
            "是否电池更换":    None,
        })

    # 12 台新能源
    for car, year_range, base, range_km, energy in NEW_ENERGY_VEHICLES:
        overdue, in_stor, stored = _gen_overdue_in_storage("standard")
        rows.append({
            "车型":            car,
            "VIN码":           gen_vin(),
            "首次登记日期":    gen_first_reg(year_range),
            "里程":            gen_mileage_wankm(year_range),
            "GPS状态":         "在线" if random.random() < 0.90 else "离线",
            "是否脱保":        _bool_zh(0.05),
            "是否过户":        _bool_zh(0.05),
            "债权本金(元)":    gen_principal_wan(base),
            "逾期天数":        overdue,
            "是否在库":        in_stor,
            "在库天数":        stored,
            "能源类型":        energy,
            "是否运营车":      "否",
            "电池SOH(%)":      random.randint(83, 95),
            "三电质保":        _bool_zh(0.85),
            "续航里程(km)":    range_km,
            "是否网约车":      _bool_zh(0.10),
            "是否电池更换":    "否",
        })

    return pd.DataFrame(rows)


def gen_risky_package() -> pd.DataFrame:
    """问题包：30 台车，6 类风险叠加，演示 AI 自动发现问题的能力。

    风险分布(燃油 18):
    - 前 5 台 GPS 离线 (拖车难)
    - 第 6-9 台 (idx 5-8) 脱保
    - 第 10-12 台 (idx 9-11) 权属未转
    - 第 13-15 台 (idx 12-14) 缺本金 (数据完整性问题)
    - 后 3 台 (idx 15-17) 缺 VIN (数据完整性 + parser 友好报错)

    风险分布(新能源 12):
    - 前 8 台 (idx 0-7) 高风险新能源：SOH<80 / 三电质保过期
    - 其中 4 台网约车 (idx 0-3)
    - 其中 4 台有电池更换历史 (idx 2-5)
    - 部分 GPS 离线 / 脱保点缀
    """
    random.seed(SEED_RISKY)
    rows: list[dict] = []

    # 18 台燃油
    for i, (car, year_range, base) in enumerate(FUEL_VEHICLES):
        gps = "离线" if i < 5 else ("在线" if random.random() < 0.80 else "离线")
        lapsed = "是" if 5 <= i < 9 else _bool_zh(0.15)
        transferred = "是" if 9 <= i < 12 else _bool_zh(0.10)
        principal: Optional[str] = None if 12 <= i < 15 else gen_principal_wan(base)
        vin = "" if i >= 15 else gen_vin()
        overdue, in_stor, stored = _gen_overdue_in_storage("risky")
        rows.append({
            "车型":            car,
            "VIN码":           vin,
            "首次登记日期":    gen_first_reg(year_range),
            "里程":            gen_mileage_wankm(year_range),
            "GPS状态":         gps,
            "是否脱保":        lapsed,
            "是否过户":        transferred,
            "债权本金(元)":    principal,
            "逾期天数":        overdue,
            "是否在库":        in_stor,
            "在库天数":        stored,
            "能源类型":        "燃油",
            "是否运营车":      _bool_zh(0.15),
            "电池SOH(%)":      None,
            "三电质保":        None,
            "续航里程(km)":    None,
            "是否网约车":      None,
            "是否电池更换":    None,
        })

    # 12 台新能源
    for i, (car, year_range, base, range_km, energy) in enumerate(NEW_ENERGY_VEHICLES):
        if i < 8:
            soh = random.randint(58, 78)        # 低 SOH
            warranty = "否"                     # 质保过期
            ride_hail = "是" if i < 4 else "否"
            replaced = "是" if 2 <= i < 6 else "否"
            range_actual = max(180, range_km - random.randint(120, 220))  # 续航衰减
        else:
            soh = random.randint(82, 92)
            warranty = "是"
            ride_hail = "否"
            replaced = "否"
            range_actual = range_km - random.randint(0, 60)

        gps = "离线" if i in (1, 5, 9) else "在线"
        overdue, in_stor, stored = _gen_overdue_in_storage("risky")
        rows.append({
            "车型":            car,
            "VIN码":           gen_vin(),
            "首次登记日期":    gen_first_reg(year_range),
            "里程":            gen_mileage_wankm(year_range),
            "GPS状态":         gps,
            "是否脱保":        "是" if i in (0, 7) else "否",
            "是否过户":        "否",
            "债权本金(元)":    gen_principal_wan(base),
            "逾期天数":        overdue,
            "是否在库":        in_stor,
            "在库天数":        stored,
            "能源类型":        energy,
            "是否运营车":      "否",
            "电池SOH(%)":      soh,
            "三电质保":        warranty,
            "续航里程(km)":    range_actual,
            "是否网约车":      ride_hail,
            "是否电池更换":    replaced,
        })

    return pd.DataFrame(rows)


def _summarize(df: pd.DataFrame, name: str) -> None:
    print(f"\n=== {name} ===")
    print(f"行数: {len(df)} / 列数: {len(df.columns)}")
    print(f"列名: {list(df.columns)}")
    print(f"GPS 离线: {(df['GPS状态'] == '离线').sum()} 台")
    print(f"脱保:    {(df['是否脱保'] == '是').sum()} 台")
    print(f"过户:    {(df['是否过户'] == '是').sum()} 台")
    print(f"缺本金:  {df['债权本金(元)'].isna().sum() + (df['债权本金(元)'] == '').sum()} 台")
    print(f"缺 VIN:  {(df['VIN码'] == '').sum()} 台")
    # 不良资产三要素分布
    print(f"逾期 > 365 天: {(df['逾期天数'] > 365).sum()} 台")
    print(f"在库:           {(df['是否在库'] == '是').sum()} 台 / 未收车: {(df['是否在库'] == '否').sum()} 台")
    if (df['是否在库'] == '是').any():
        in_stor_df = df[df['是否在库'] == '是']
        print(f"在库平均天数:    {in_stor_df['在库天数'].mean():.0f} 天")
        print(f"在库 > 90 天:    {(in_stor_df['在库天数'] > 90).sum()} 台")
    if df["电池SOH(%)"].notna().any():
        low_soh = df[df["电池SOH(%)"].notna() & (df["电池SOH(%)"] < 80)].shape[0]
        print(f"电池 SOH < 80:  {low_soh} 台")
        warranty_lapsed = (df["三电质保"] == "否").sum()
        print(f"三电质保已过:    {warranty_lapsed} 台")
        ride_hail = (df["是否网约车"] == "是").sum()
        print(f"网约车:         {ride_hail} 台")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    std = gen_standard_package()
    risky = gen_risky_package()

    std_path = OUTPUT_DIR / "demo_standard_package.xlsx"
    risky_path = OUTPUT_DIR / "demo_risky_package.xlsx"

    std.to_excel(std_path, index=False)
    risky.to_excel(risky_path, index=False)

    _summarize(std, "demo_standard_package.xlsx")
    _summarize(risky, "demo_risky_package.xlsx")

    print(f"\n✅ 输出:")
    print(f"   {std_path}")
    print(f"   {risky_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
