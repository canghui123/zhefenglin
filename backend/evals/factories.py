"""B2 — Eval 测试用工厂函数:构造 PackageContext 给 Agent 直接调用。

为什么有这个模块:
- Agent 函数(_diagnose_asset_package / _operation_planning_agent 等)的入参是
  PackageContext = (package, assets, result),pydantic 模型,不接 DB。
- 用 YAML case 描述输入时,我们需要把 dict 转成 PackageContext。这个文件提供
  统一的工厂函数,case YAML 只关心业务字段,不必关心 ORM 细节。
- 工厂函数同时为现实 Agent 行为做 sanity check:case 构造的对象必须能被
  Agent 真实代码消费,否则 case YAML 就是空中楼阁。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Optional

from db.models.asset_package import Asset as AssetORM
from db.models.asset_package import AssetPackage as AssetPackageORM
from models.asset import PackageCalculationResult, PackageSummary
from services.agent_orchestrator import PackageContext


@dataclass
class _MockPackageRow:
    """伪造 SQLAlchemy AssetPackage row,避免依赖真实 DB。"""

    id: int
    tenant_id: int
    name: Optional[str]
    total_assets: int
    upload_filename: Optional[str] = None
    storage_key: Optional[str] = None
    parameters_json: Optional[str] = None
    results_json: Optional[str] = None
    created_by: Optional[int] = None

    def __getattr__(self, name: str) -> Any:
        # 让访问其他字段返回 None,而不是 AttributeError
        return None


def build_package_context(case_input: dict) -> PackageContext:
    """从 YAML case 的 input 区块构造 PackageContext。

    Case YAML 'input' 格式:
        input:
          package:               # 可选:整个 package 为 None 时省略
            id: 100
            name: "测试包"
            total_assets: 30
          result_summary:        # 可选:省略时 result=None
            total_assets: 30
            recommended_transfer_price_low: 1500000
            recommended_transfer_price_mid: 1700000
            recommended_transfer_price_high: 1900000
            tradeability_level: "B"
            tradeability_score: 75
            m12_plus_count: 19
            ...
    """
    pkg_data = case_input.get("package")
    if pkg_data is None:
        return PackageContext(package=None, assets=[], result=None)

    package = _MockPackageRow(
        id=int(pkg_data.get("id", 1)),
        tenant_id=int(pkg_data.get("tenant_id", 1)),
        name=pkg_data.get("name"),
        total_assets=int(pkg_data.get("total_assets", 0)),
        upload_filename=pkg_data.get("upload_filename"),
        storage_key=pkg_data.get("storage_key"),
        results_json=None,  # 我们用 result 对象代替,不构造 JSON
    )

    # 构造 PackageCalculationResult(可选)
    result: Optional[PackageCalculationResult] = None
    rs = case_input.get("result_summary")
    if rs is not None:
        # 用 PackageSummary 默认值兜底,case YAML 只提供需要的字段
        summary_data = {
            "total_assets": int(rs.get("total_assets", package.total_assets)),
            **rs,
        }
        summary = PackageSummary(**summary_data)
        result = PackageCalculationResult(
            package_id=package.id,
            summary=summary,
            assets=[],  # eval 不验证 per-asset 字段
        )

    # assets 字段(DB ORM):eval 一般不用,留空
    assets: list[AssetORM] = []

    return PackageContext(package=package, assets=assets, result=result)
